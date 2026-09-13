from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO, Sequence

import pytest

from mobile_research.collectors import (
    RawNetworkCollector,
    RawNetworkCollectorError,
    inspect_pcap,
)
from mobile_research.session import SessionManager


PCAP_HEADER = (
    b"\xd4\xc3\xb2\xa1"
    b"\x02\x00"
    b"\x04\x00"
    b"\x00\x00\x00\x00"
    b"\x00\x00\x00\x00"
    b"\xff\xff\x00\x00"
    b"\x01\x00\x00\x00"
)
PCAP_PACKET = (
    b"\x01\x00\x00\x00"
    b"\x02\x00\x00\x00"
    b"\x04\x00\x00\x00"
    b"\x04\x00\x00\x00"
    b"TEST"
)


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
        pid: int = 200,
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
            raise subprocess.TimeoutExpired("tcpdump", timeout)
        return self.returncode


class FakeAdb:
    adb_path = Path("adb")

    def __init__(
        self,
        *,
        uid: int = 0,
        tcpdump_available: bool = True,
    ) -> None:
        self.uid = uid
        self.tcpdump_available = tcpdump_available
        self.before_spawn = True
        self.remote_pid = 5000
        self.process: FakeProcess | None = None
        self.signals: list[tuple[int, int]] = []
        self.remote_dirs: list[str] = []
        self.removed: list[str] = []
        self.remote_stderr = (
            b"tcpdump: listening on any, "
            b"link-type LINUX_SLL2\n"
        )

    def ensure_ready(self, serial: str) -> None:
        assert serial == "emulator-5554"

    def get_uid(self, serial: str) -> int:
        return self.uid

    def probe_executable(
        self,
        serial: str,
        candidates: Sequence[str],
        *,
        version_arguments: Sequence[str] = ("--version",),
    ) -> tuple[str, str]:
        if not self.tcpdump_available:
            from mobile_research.targets import AdbError

            raise AdbError("No usable executable found")
        return "tcpdump", "tcpdump version 4.99.5"

    def get_process_ids(
        self,
        serial: str,
        process_name: str,
    ) -> list[int]:
        return [] if self.before_spawn else [self.remote_pid]

    def make_remote_directory(
        self,
        serial: str,
        remote_path: str,
    ) -> None:
        self.remote_dirs.append(remote_path)

    def pull_file(
        self,
        serial: str,
        remote_path: str,
        local_path: Path,
        *,
        timeout: float = 120.0,
    ) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(self.remote_stderr)

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
        process: FakeProcess,
        *,
        data: bytes = PCAP_HEADER + PCAP_PACKET,
        stderr: bytes = b"",
    ) -> None:
        self.adb = adb
        self.process = process
        self.data = data
        self.stderr = stderr
        self.command: list[str] = []

    def __call__(
        self,
        command: Sequence[str],
        stdout: BinaryIO,
        stderr: BinaryIO,
    ) -> FakeProcess:
        self.command = list(command)
        stdout.write(self.data)
        stdout.flush()
        if self.stderr:
            stderr.write(self.stderr)
            stderr.flush()
        self.adb.process = self.process
        self.adb.before_spawn = False
        return self.process


def create_session(
    tmp_path: Path,
    *,
    kind: str = "emulator",
) -> SessionManager:
    manager = SessionManager.create(
        tmp_path,
        target={
            "serial": "emulator-5554",
            "kind": kind,
        },
        package={"name": "com.example.app"},
        clock=TestClock(),
        session_id_factory=lambda: "network-session",
    )
    manager.begin_preflight()
    manager.mark_ready()
    manager.begin_start()
    return manager


def test_raw_network_graceful_stop(tmp_path: Path) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    process = FakeProcess()
    factory = ProcessFactory(adb, process)

    collector = RawNetworkCollector(
        adb,
        session,
        clock=TestClock(),
        process_factory=factory,
    )
    collector.start()

    assert collector.running is True
    assert factory.command == [
        "adb",
        "-s",
        "emulator-5554",
        "exec-out",
        "sh",
        "-c",
        (
            "tcpdump -i any -p -s 0 -U -w - "
            "2>/data/local/tmp/mobile-research/"
            "network-session/tcpdump.stderr.txt"
        ),
    ]

    session.mark_active()
    session.begin_stop()
    result = collector.stop()

    assert result.status == "completed"
    assert result.bytes_captured == len(
        PCAP_HEADER + PCAP_PACKET
    )
    assert result.pcap_format == "pcap-le-microsecond"
    assert adb.signals == [(5000, 2)]
    assert session.degraded is False

    pcap_path = session.paths.raw_network / "traffic.pcap"
    assert pcap_path.read_bytes()[:4] == b"\xd4\xc3\xb2\xa1"

    stderr_path = (
        session.paths.raw_network / "tcpdump.stderr.txt"
    )
    assert stderr_path.read_bytes() == adb.remote_stderr

    state = session.manifest["collectors"]["raw_network"]
    assert state["status"] == "completed"
    assert len(state["artifact_paths"]) == 3


def test_preflight_requires_root(tmp_path: Path) -> None:
    session = create_session(tmp_path)
    collector = RawNetworkCollector(
        FakeAdb(uid=2000),
        session,
    )

    with pytest.raises(
        RawNetworkCollectorError,
        match="requires root ADB",
    ):
        collector.preflight()


def test_preflight_requires_tcpdump(tmp_path: Path) -> None:
    session = create_session(tmp_path)
    collector = RawNetworkCollector(
        FakeAdb(tcpdump_available=False),
        session,
    )

    with pytest.raises(
        RawNetworkCollectorError,
        match="requires tcpdump",
    ):
        collector.preflight()


def test_v01_backend_rejects_physical_target(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path, kind="physical")
    collector = RawNetworkCollector(FakeAdb(), session)

    with pytest.raises(
        RawNetworkCollectorError,
        match="requires AVD-RESEARCH",
    ):
        collector.preflight()


def test_unexpected_exit_preserves_pcap_and_degrades(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    process = FakeProcess()
    collector = RawNetworkCollector(
        adb,
        session,
        clock=TestClock(),
        process_factory=ProcessFactory(adb, process),
    )
    collector.start()
    session.mark_active()

    process.returncode = 7

    assert collector.check_health() is False
    assert session.degraded is True
    pcap = session.paths.raw_network / "traffic.pcap"
    assert pcap.is_file()
    assert pcap.stat().st_size > 24


def test_invalid_pcap_fails_collector(tmp_path: Path) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    process = FakeProcess()
    collector = RawNetworkCollector(
        adb,
        session,
        clock=TestClock(),
        process_factory=ProcessFactory(
            adb,
            process,
            data=b"not-a-pcap",
        ),
    )
    collector.start()
    session.mark_active()
    session.begin_stop()

    result = collector.stop()

    assert result.status == "failed"
    assert result.pcap_format == "unknown"
    assert session.degraded is True


def test_forced_kill_keeps_valid_pcap(tmp_path: Path) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    process = FakeProcess(terminate_exits=False)

    def no_effect_signal(
        serial: str,
        process_id: int,
        signal_number: int,
    ) -> None:
        adb.signals.append((process_id, signal_number))

    adb.send_signal = no_effect_signal  # type: ignore[method-assign]

    collector = RawNetworkCollector(
        adb,
        session,
        clock=TestClock(),
        process_factory=ProcessFactory(adb, process),
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


def test_process_dead_before_stop_is_failure(tmp_path: Path) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    process = FakeProcess()
    collector = RawNetworkCollector(
        adb,
        session,
        clock=TestClock(),
        process_factory=ProcessFactory(adb, process),
    )
    collector.start()
    session.mark_active()

    process.returncode = 9
    session.begin_stop()
    result = collector.stop()

    assert result.status == "failed"
    assert session.degraded is True


def test_inspect_pcap_rejects_bad_magic(tmp_path: Path) -> None:
    path = tmp_path / "bad.pcap"
    path.write_bytes(b"X" * 24)

    with pytest.raises(
        RawNetworkCollectorError,
        match="magic",
    ):
        inspect_pcap(path)


def test_header_only_pcap_is_not_successful_capture(
    tmp_path: Path,
) -> None:
    path = tmp_path / "header-only.pcap"
    path.write_bytes(PCAP_HEADER)

    with pytest.raises(
        RawNetworkCollectorError,
        match="does not contain captured packets",
    ):
        inspect_pcap(path)
