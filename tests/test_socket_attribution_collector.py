from __future__ import annotations

import subprocess
from pathlib import Path
from typing import BinaryIO, Sequence

from mobile_research.collectors import SocketAttributionCollector
from mobile_research.session import SessionManager


RAW = (
    "SNAP|1700000000000000000\n"
    "ROW|tcp|  0: 0F02000A:9C40 22D8B85D:01BB "
    "01 00000000:00000000 02:00000000 00000000 "
    "10234 0 55555 1 0000000000000000 20 4 30 10 -1\n"
    "PROC|4321|10234|com.example.app\n"
    "FD|4321|55555\n"
    "END|1700000000000000000\n"
).encode()


class FakeProcess:
    def __init__(self) -> None:
        self.pid = 123
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        if self.returncode is None:
            raise subprocess.TimeoutExpired("sampler", timeout)
        return self.returncode

    def terminate(self) -> None:
        self.returncode = 0

    def kill(self) -> None:
        self.returncode = -9


class FakeAdb:
    adb_path = Path("adb")

    def __init__(self, process: FakeProcess) -> None:
        self.process = process
        self.signals: list[tuple[int, int]] = []
        self.removed: list[str] = []

    def ensure_ready(self, serial: str) -> None:
        assert serial == "emulator-5554"

    def get_uid(self, serial: str) -> int:
        return 0

    def get_package_uid(
        self,
        serial: str,
        package: str,
    ) -> int:
        assert package == "com.example.app"
        return 10234

    def get_packages_for_uid(
        self,
        serial: str,
        uid: int,
    ) -> list[str]:
        assert uid == 10234
        return ["com.example.app"]

    def make_remote_directory(
        self,
        serial: str,
        path: str,
    ) -> None:
        pass

    def remove_remote_file(
        self,
        serial: str,
        path: str,
    ) -> None:
        self.removed.append(path)

    def shell_output(
        self,
        serial: str,
        *arguments: str,
        timeout: float = 10.0,
    ) -> str:
        assert arguments[0] == "cat"
        return "777\n"

    def send_signal(
        self,
        serial: str,
        process_id: int,
        signal_number: int,
    ) -> None:
        self.signals.append((process_id, signal_number))
        self.process.returncode = 0


class Factory:
    def __init__(self, process: FakeProcess) -> None:
        self.process = process
        self.command: list[str] = []

    def __call__(
        self,
        command: Sequence[str],
        stdout: BinaryIO,
        stderr: BinaryIO,
    ) -> FakeProcess:
        self.command = list(command)
        stdout.write(RAW)
        stdout.flush()
        return self.process


def _session(tmp_path: Path) -> SessionManager:
    session = SessionManager.create(
        tmp_path,
        target={
            "serial": "emulator-5554",
            "kind": "emulator",
        },
        package={"name": "com.example.app"},
        session_id_factory=lambda: "socket-session",
    )
    session.begin_preflight()
    session.mark_ready()
    session.begin_start()
    return session


def test_socket_attribution_collector_normalizes_snapshots(
    tmp_path: Path,
) -> None:
    process = FakeProcess()
    adb = FakeAdb(process)
    factory = Factory(process)
    session = _session(tmp_path)
    collector = SocketAttributionCollector(
        adb,  # type: ignore[arg-type]
        session,
        process_factory=factory,
    )

    preflight = collector.preflight()
    assert preflight.package_uid == 10234
    assert preflight.uid_packages == ("com.example.app",)

    collector.start()
    assert collector.running is True
    assert "APP_UID=10234" in factory.command[-1]
    assert 'echo $$ > "$PID_FILE"' in factory.command[-1]
    assert 'echo $ > "$PID_FILE"' not in factory.command[-1]
    assert "while read -r K V REST; do" in factory.command[-1]
    assert 'IFS=" \\t"' not in factory.command[-1]
    assert "/proc/net/$T" in factory.command[-1]

    session.mark_active()
    session.begin_stop()
    result = collector.stop()

    assert result.status == "completed"
    assert result.snapshot_count == 1
    assert result.socket_observations == 1
    assert adb.signals == [(777, 2)]
    assert (
        session.paths.root
        / "02_normalized/socket-attribution.jsonl"
    ).is_file()
    assert (
        session.manifest["collectors"]["socket_attribution"]["status"]
        == "completed"
    )
