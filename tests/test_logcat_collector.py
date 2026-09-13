from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO, Sequence

import pytest

from mobile_research.collectors import (
    LogcatCollector,
    LogcatCollectorError,
)
from mobile_research.session import SessionManager


class TestClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


class FakeAdb:
    adb_path = Path("adb")

    def ensure_ready(self, serial: str) -> None:
        assert serial == "emulator-5554"


class FakeProcess:
    def __init__(
        self,
        *,
        pid: int = 1234,
        terminate_exits: bool = True,
        initial_returncode: int | None = None,
    ) -> None:
        self.pid = pid
        self.returncode = initial_returncode
        self.terminate_exits = terminate_exits
        self.terminated = False
        self.killed = False
        self.wait_calls: list[float | None] = []

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
        self.wait_calls.append(timeout)
        if self.returncode is None:
            raise subprocess.TimeoutExpired("adb logcat", timeout)
        return self.returncode


def create_session(tmp_path: Path) -> SessionManager:
    manager = SessionManager.create(
        tmp_path,
        target={"serial": "emulator-5554", "kind": "emulator"},
        package={"name": "com.example.app"},
        clock=TestClock(),
        session_id_factory=lambda: "logcat-session",
    )
    manager.begin_preflight()
    manager.mark_ready()
    manager.begin_start()
    return manager


def process_factory(
    process: FakeProcess,
    *,
    write_log: bool = True,
    stderr_text: bytes = b"",
):
    def factory(
        command: Sequence[str],
        stdout: BinaryIO,
        stderr: BinaryIO,
    ) -> FakeProcess:
        assert command[-8:] == [
            "-s",
            "emulator-5554",
            "logcat",
            "-b",
            "all",
            "-v",
            "epoch",
            "-T",
        ][-8:] or "-T" in command
        if write_log:
            stdout.write(
                b"1757786400.123  1000  1000 I ActivityManager: test\n"
            )
            stdout.flush()
        if stderr_text:
            stderr.write(stderr_text)
            stderr.flush()
        return process

    return factory


def test_logcat_start_and_graceful_stop(tmp_path: Path) -> None:
    session = create_session(tmp_path)
    process = FakeProcess()
    captured_command: list[str] = []

    def factory(
        command: Sequence[str],
        stdout: BinaryIO,
        stderr: BinaryIO,
    ) -> FakeProcess:
        captured_command.extend(command)
        stdout.write(b"1757786400.123 1 1 I Test: hello\n")
        stdout.flush()
        return process

    collector = LogcatCollector(
        FakeAdb(),
        session,
        clock=TestClock(),
        process_factory=factory,
    )
    collector.start()

    assert collector.running is True
    assert captured_command == [
        "adb",
        "-s",
        "emulator-5554",
        "logcat",
        "-b",
        "all",
        "-v",
        "epoch",
        "-T",
        "1",
    ]

    session.mark_active()
    session.begin_stop()
    result = collector.stop()

    assert result.status == "completed"
    assert result.forced_kill is False
    assert result.bytes_captured > 0
    assert process.terminated is True
    assert session.degraded is False

    manifest = session.manifest
    state = manifest["collectors"]["logcat"]
    assert state["status"] == "completed"
    assert len(state["artifact_paths"]) == 3

    metadata = json.loads(
        (session.paths.root / result.metadata_artifact).read_text(
            encoding="utf-8"
        )
    )
    assert metadata["pre_roll"]["buffer_cleared"] is False
    assert metadata["pre_roll"]["strategy"] == "logcat -T 1"
    assert metadata["bytes_captured"] > 0


def test_logcat_forced_kill_after_grace_period(tmp_path: Path) -> None:
    session = create_session(tmp_path)
    process = FakeProcess(terminate_exits=False)

    collector = LogcatCollector(
        FakeAdb(),
        session,
        clock=TestClock(),
        process_factory=process_factory(process),
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


def test_unexpected_logcat_exit_marks_session_degraded(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    process = FakeProcess()

    collector = LogcatCollector(
        FakeAdb(),
        session,
        clock=TestClock(),
        process_factory=process_factory(
            process,
            stderr_text=b"transport closed\n",
        ),
    )
    collector.start()
    session.mark_active()

    process.returncode = 7

    assert collector.check_health() is False
    assert session.degraded is True
    assert session.manifest["collectors"]["logcat"]["status"] == "failed"

    session.begin_stop()
    result = collector.stop()

    assert result.status == "failed"
    assert result.bytes_captured > 0


def test_empty_logcat_artifact_is_failure(tmp_path: Path) -> None:
    session = create_session(tmp_path)
    process = FakeProcess()

    collector = LogcatCollector(
        FakeAdb(),
        session,
        clock=TestClock(),
        process_factory=process_factory(process, write_log=False),
    )
    collector.start()
    session.mark_active()
    session.begin_stop()

    result = collector.stop()

    assert result.status == "failed"
    assert result.bytes_captured == 0
    assert session.degraded is True


def test_logcat_must_start_in_starting_state(tmp_path: Path) -> None:
    session = SessionManager.create(
        tmp_path,
        target={"serial": "emulator-5554"},
        package={"name": "com.example.app"},
        clock=TestClock(),
        session_id_factory=lambda: "wrong-state",
    )

    collector = LogcatCollector(
        FakeAdb(),
        session,
        clock=TestClock(),
        process_factory=process_factory(FakeProcess()),
    )

    with pytest.raises(LogcatCollectorError, match="only while session"):
        collector.start()

    assert "logcat" not in session.manifest["collectors"]


def test_immediate_process_exit_fails_start(tmp_path: Path) -> None:
    session = create_session(tmp_path)
    process = FakeProcess(initial_returncode=2)

    collector = LogcatCollector(
        FakeAdb(),
        session,
        clock=TestClock(),
        process_factory=process_factory(process, write_log=False),
    )

    with pytest.raises(LogcatCollectorError, match="exited immediately"):
        collector.start()

    assert session.degraded is True
    assert session.manifest["collectors"]["logcat"]["status"] == "failed"
