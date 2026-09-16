from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO, Sequence

import pytest

from apk_research.collectors import (
    ScreenRecordingCollector,
    ScreenRecordingCollectorError,
    inspect_screenrecord_timing,
)
from apk_research.session import SessionManager


class TestClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


class FakeProcess:
    def __init__(
        self,
        *,
        pid: int,
        returncode: int | None = None,
        terminate_exits: bool = True,
    ) -> None:
        self.pid = pid
        self.returncode = returncode
        self.terminate_exits = terminate_exits
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        if self.terminate_exits:
            self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        if self.returncode is None:
            raise subprocess.TimeoutExpired("screenrecord", timeout)
        return self.returncode


class FakeAdb:
    adb_path = Path("adb")

    def __init__(self) -> None:
        self.process: FakeProcess | None = None
        self.remote_pid = 4000
        self.before_spawn = True
        self.pull_bytes = b"fake-mp4-data"
        self.signals: list[tuple[int, int]] = []
        self.removed: list[str] = []
        self.remote_dirs: list[str] = []

    def get_utc_time(self, serial: str) -> str:
        assert serial == "emulator-5554"
        return "2026-09-13T18:00:00Z"

    def ensure_ready(self, serial: str) -> None:
        assert serial == "emulator-5554"

    def make_remote_directory(
        self,
        serial: str,
        remote_path: str,
    ) -> None:
        self.remote_dirs.append(remote_path)

    def get_process_ids(
        self,
        serial: str,
        process_name: str,
    ) -> list[int]:
        if self.before_spawn:
            return []
        return [self.remote_pid]

    def pull_file(
        self,
        serial: str,
        remote_path: str,
        local_path: Path,
        *,
        timeout: float = 120.0,
    ) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(self.pull_bytes)

    def remove_remote_file(
        self,
        serial: str,
        remote_path: str,
    ) -> None:
        self.removed.append(remote_path)

    def send_signal(
        self,
        serial: str,
        process_id: int,
        signal_number: int,
    ) -> None:
        self.signals.append((process_id, signal_number))
        if self.process is not None:
            self.process.returncode = 0


class ProcessFactory:
    def __init__(
        self,
        adb: FakeAdb,
        processes: list[FakeProcess],
    ) -> None:
        self.adb = adb
        self.processes = list(processes)
        self.commands: list[list[str]] = []

    def __call__(
        self,
        command: Sequence[str],
        diagnostic: BinaryIO,
    ) -> FakeProcess:
        process = self.processes.pop(0)
        self.commands.append(list(command))
        diagnostic.write(b"screenrecord verbose output\n")
        diagnostic.flush()
        self.adb.process = process
        self.adb.before_spawn = False
        return process


def create_session(tmp_path: Path) -> SessionManager:
    manager = SessionManager.create(
        tmp_path,
        target={"serial": "emulator-5554", "kind": "emulator"},
        package={"name": "com.example.app"},
        clock=TestClock(),
        session_id_factory=lambda: "screen-session",
    )
    manager.begin_preflight()
    manager.mark_ready()
    manager.begin_start()
    return manager


def test_screen_recording_graceful_stop_preserves_video(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    process = FakeProcess(pid=100)
    factory = ProcessFactory(adb, [process])

    collector = ScreenRecordingCollector(
        adb,
        session,
        clock=TestClock(),
        process_factory=factory,
    )
    collector.start()

    assert collector.running is True
    assert factory.commands[0][-4:] == [
        "--verbose",
        "--time-limit",
        "170",
        (
            "/data/local/tmp/apk-research/"
            "screen-session/screen-0001.mp4"
        ),
    ]

    session.mark_active()
    session.begin_stop()
    result = collector.stop()

    assert result.status == "completed"
    assert result.chunks == (
        "01_raw/screen/screen-0001.mp4",
    )
    assert result.bytes_captured == len(adb.pull_bytes)
    assert adb.signals == [(4000, 2)]
    assert process.terminated is False
    assert session.degraded is False

    video = session.paths.root / result.chunks[0]
    assert video.read_bytes() == adb.pull_bytes

    metadata = __import__("json").loads(
        (
            session.paths.root
            / ScreenRecordingCollector.METADATA_ARTIFACT
        ).read_text(encoding="utf-8")
    )
    chunk = metadata["completed_chunks"][0]
    assert chunk["target_started_utc"] == "2026-09-13T18:00:00Z"
    assert chunk["target_finished_utc"] == "2026-09-13T18:00:00Z"
    assert chunk["capture_span_seconds"] >= 0
    assert "media_duration_note" in metadata["timing_model"]


def test_natural_chunk_completion_rotates_to_next_chunk(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    first = FakeProcess(pid=101)
    second = FakeProcess(pid=102)
    factory = ProcessFactory(adb, [first, second])

    collector = ScreenRecordingCollector(
        adb,
        session,
        clock=TestClock(),
        process_factory=factory,
    )
    collector.start()
    session.mark_active()

    first.returncode = 0
    adb.before_spawn = True

    assert collector.check_health() is True
    assert collector.running is True
    assert len(factory.commands) == 2

    session.begin_stop()
    result = collector.stop()

    assert result.status == "completed"
    assert result.chunks == (
        "01_raw/screen/screen-0001.mp4",
        "01_raw/screen/screen-0002.mp4",
    )
    assert session.degraded is False


def test_unexpected_chunk_exit_preserves_chunk_but_degrades_session(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    process = FakeProcess(pid=103)
    collector = ScreenRecordingCollector(
        adb,
        session,
        clock=TestClock(),
        process_factory=ProcessFactory(adb, [process]),
    )
    collector.start()
    session.mark_active()

    process.returncode = 7

    assert collector.check_health() is False
    assert session.degraded is True
    assert (
        session.paths.raw_screen / "screen-0001.mp4"
    ).is_file()
    assert session.manifest["collectors"]["screen_recording"][
        "status"
    ] == "failed"


def test_empty_screen_chunk_is_failure(tmp_path: Path) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    adb.pull_bytes = b""
    process = FakeProcess(pid=104)

    collector = ScreenRecordingCollector(
        adb,
        session,
        clock=TestClock(),
        process_factory=ProcessFactory(adb, [process]),
    )
    collector.start()
    session.mark_active()
    session.begin_stop()

    result = collector.stop()

    assert result.status == "failed"
    assert result.chunks == ()
    assert session.degraded is True


def test_screen_recording_falls_back_to_force_kill(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    process = FakeProcess(
        pid=105,
        terminate_exits=False,
    )

    def no_effect_signal(
        serial: str,
        process_id: int,
        signal_number: int,
    ) -> None:
        adb.signals.append((process_id, signal_number))

    adb.send_signal = no_effect_signal  # type: ignore[method-assign]

    collector = ScreenRecordingCollector(
        adb,
        session,
        clock=TestClock(),
        process_factory=ProcessFactory(adb, [process]),
    )
    collector.start()
    session.mark_active()
    session.begin_stop()

    result = collector.stop(grace_period=0.01)

    assert result.status == "completed"
    assert result.forced_kill is True
    assert process.terminated is True
    assert process.killed is True
    assert session.degraded is False


def test_screen_recording_requires_starting_state(
    tmp_path: Path,
) -> None:
    session = SessionManager.create(
        tmp_path,
        target={"serial": "emulator-5554"},
        package={"name": "com.example.app"},
        clock=TestClock(),
        session_id_factory=lambda: "screen-wrong-state",
    )
    adb = FakeAdb()

    collector = ScreenRecordingCollector(
        adb,
        session,
        clock=TestClock(),
        process_factory=ProcessFactory(
            adb,
            [FakeProcess(pid=106)],
        ),
    )

    with pytest.raises(
        ScreenRecordingCollectorError,
        match="only while session",
    ):
        collector.start()


def test_chunk_seconds_limit_is_enforced(tmp_path: Path) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()

    with pytest.raises(ValueError, match="between 1 and 180"):
        ScreenRecordingCollector(
            adb,
            session,
            chunk_seconds=181,
        )


def test_stop_detects_process_that_failed_before_stop(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    process = FakeProcess(pid=107)
    collector = ScreenRecordingCollector(
        adb,
        session,
        clock=TestClock(),
        process_factory=ProcessFactory(adb, [process]),
    )
    collector.start()
    session.mark_active()

    process.returncode = 9
    session.begin_stop()
    result = collector.stop()

    assert result.status == "failed"
    assert session.degraded is True
    assert (
        session.paths.raw_screen / "screen-0001.mp4"
    ).is_file()



def test_winscope_v2_timing_is_extracted(tmp_path: Path) -> None:
    path = tmp_path / "screen.mp4"
    magic = b"#VV1NSC0PET1ME2#"
    version = (2).to_bytes(4, "little")
    realtime_to_elapsed = (
        1_700_000_000_000_000_000
    ).to_bytes(8, "little", signed=True)
    frame_count = (3).to_bytes(4, "little")
    frames = b"".join(
        value.to_bytes(8, "little")
        for value in (
            10_000_000_000,
            10_500_000_000,
            12_000_000_000,
        )
    )
    path.write_bytes(
        b"fake-mp4-prefix"
        + magic
        + version
        + realtime_to_elapsed
        + frame_count
        + frames
    )

    timing = inspect_screenrecord_timing(path)

    assert timing is not None
    assert timing["source"] == "winscope-v2"
    assert timing["version"] == 2
    assert timing["frame_count"] == 3
    assert timing["frame_span_seconds"] == 2.0
    assert timing["presentation_span_seconds"] == 2.0
    assert timing["clock_domain"] == (
        "device-realtime-derived-from-elapsed"
    )
    assert timing["realtime_to_elapsed_offset_ns"] == (
        1_700_000_000_000_000_000
    )
    assert timing["first_frame_utc"].endswith("Z")
    assert timing["last_frame_utc"].endswith("Z")


def test_winscope_timing_absent_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "screen.mp4"
    path.write_bytes(b"not-a-screenrecord-file" * 4)

    assert inspect_screenrecord_timing(path) is None
