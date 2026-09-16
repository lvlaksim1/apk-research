from __future__ import annotations

import json
import os
import shlex
import struct
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Callable, Protocol, Sequence

from apk_research.session import SessionManager, SessionStatus
from apk_research.targets import AdbClient, AdbError

Clock = Callable[[], datetime]


class ProcessLike(Protocol):
    pid: int
    returncode: int | None

    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...


ProcessFactory = Callable[
    [Sequence[str], BinaryIO, BinaryIO],
    ProcessLike,
]


class RawNetworkCollectorError(RuntimeError):
    """Raised when mandatory raw packet capture cannot be maintained."""


@dataclass(frozen=True)
class RawNetworkPreflight:
    serial: str
    root: bool
    tcpdump_path: str
    tcpdump_version: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RawNetworkResult:
    collector: str
    status: str
    raw_artifact: str
    stderr_artifact: str
    metadata_artifact: str
    started_utc: str
    stopped_utc: str
    returncode: int | None
    forced_kill: bool
    bytes_captured: int
    pcap_format: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json_atomic(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                value,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _default_process_factory(
    command: Sequence[str],
    stdout: BinaryIO,
    stderr: BinaryIO,
) -> ProcessLike:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        list(command),
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        creationflags=creation_flags,
    )


_PCAP_MAGICS = {
    b"\xd4\xc3\xb2\xa1": "pcap-le-microsecond",
    b"\xa1\xb2\xc3\xd4": "pcap-be-microsecond",
    b"\x4d\x3c\xb2\xa1": "pcap-le-nanosecond",
    b"\xa1\xb2\x3c\x4d": "pcap-be-nanosecond",
}


def inspect_pcap(path: Path) -> tuple[str, int]:
    """Validate a classic PCAP file and return format plus byte size."""

    size = path.stat().st_size if path.exists() else 0
    if size < 24:
        raise RawNetworkCollectorError(
            f"PCAP artifact is too small: {size} bytes"
        )

    with path.open("rb") as handle:
        header = handle.read(24)

    pcap_format = _PCAP_MAGICS.get(header[:4])
    if pcap_format is None:
        raise RawNetworkCollectorError(
            "PCAP artifact has an unsupported or invalid magic number"
        )

    endian = "<" if "le-" in pcap_format else ">"
    major, minor = struct.unpack(
        f"{endian}HH",
        header[4:8],
    )
    if major != 2 or minor != 4:
        raise RawNetworkCollectorError(
            f"Unexpected PCAP version: {major}.{minor}"
        )

    if size == 24:
        raise RawNetworkCollectorError(
            "PCAP artifact does not contain captured packets: "
            f"{size} bytes"
        )

    return pcap_format, size


class RawNetworkCollector:
    """Mandatory raw packet capture for AVD-RESEARCH.

    v0.1 streams tcpdump output directly to Windows through adb exec-out:
    tcpdump -i any -p -s 0 -U -w -
    """

    NAME = "raw_network"
    BACKEND = "adb-tcpdump"
    RAW_ARTIFACT = "01_raw/network/traffic.pcap"
    STDERR_ARTIFACT = "01_raw/network/tcpdump.stderr.txt"
    METADATA_ARTIFACT = "02_normalized/network.json"
    TCPDUMP_CANDIDATES = (
        "tcpdump",
        "/system/bin/tcpdump",
        "/system/xbin/tcpdump",
        "/data/local/tmp/tcpdump",
    )

    def __init__(
        self,
        adb: AdbClient,
        session: SessionManager,
        *,
        clock: Clock = _utc_now,
        process_factory: ProcessFactory = _default_process_factory,
    ) -> None:
        self.adb = adb
        self.session = session
        self.clock = clock
        self.process_factory = process_factory

        self._preflight: RawNetworkPreflight | None = None
        self._process: ProcessLike | None = None
        self._stdout: BinaryIO | None = None
        self._stderr: BinaryIO | None = None
        self._command: list[str] | None = None
        self._remote_pid: int | None = None
        self._remote_dir: str | None = None
        self._remote_stderr_path: str | None = None
        self._started_utc: str | None = None
        self._stopped_utc: str | None = None
        self._stop_requested = False
        self._failure_recorded = False
        self._finished = False
        self._forced_kill = False

    @property
    def running(self) -> bool:
        return (
            self._process is not None
            and not self._finished
            and self._process.poll() is None
        )

    def preflight(self) -> RawNetworkPreflight:
        manifest = self.session.manifest
        target = manifest.get("target", {})
        serial = str(target.get("serial") or "").strip()
        kind = str(target.get("kind") or "").strip()

        if not serial:
            raise RawNetworkCollectorError(
                "Session target serial is missing"
            )
        if kind and kind != "emulator":
            raise RawNetworkCollectorError(
                "adb-tcpdump backend in v0.1 requires AVD-RESEARCH; "
                f"target kind is {kind!r}"
            )

        try:
            self.adb.ensure_ready(serial)
            uid = self.adb.get_uid(serial)
        except AdbError as exc:
            raise RawNetworkCollectorError(str(exc)) from exc

        if uid != 0:
            raise RawNetworkCollectorError(
                "Raw network capture requires root ADB on AVD-RESEARCH. "
                "Run the AOSP research image with adb root before capture."
            )

        try:
            tcpdump_path, tcpdump_version = self.adb.probe_executable(
                serial,
                self.TCPDUMP_CANDIDATES,
            )
        except AdbError as exc:
            raise RawNetworkCollectorError(
                "Raw network capture requires tcpdump on AVD-RESEARCH: "
                f"{exc}"
            ) from exc

        result = RawNetworkPreflight(
            serial=serial,
            root=True,
            tcpdump_path=tcpdump_path,
            tcpdump_version=tcpdump_version,
        )
        self._preflight = result
        return result

    def start(self) -> None:
        if self._process is not None or self._finished:
            raise RawNetworkCollectorError(
                "Raw network collector was already started"
            )
        if self.session.status != SessionStatus.STARTING:
            raise RawNetworkCollectorError(
                "Raw network collector may start only while session status "
                f"is 'starting'; current status is "
                f"{self.session.status.value!r}"
            )

        manifest = self.session.manifest
        if self.NAME in manifest.get("collectors", {}):
            raise RawNetworkCollectorError(
                f"Collector already registered: {self.NAME}"
            )

        preflight = self.preflight()
        serial = preflight.serial

        self.session.register_collector(
            self.NAME,
            required=True,
            backend=self.BACKEND,
        )

        for kind, relative_path, raw in (
            ("network_pcap", self.RAW_ARTIFACT, True),
            ("network_stderr", self.STDERR_ARTIFACT, True),
            ("network_metadata", self.METADATA_ARTIFACT, False),
        ):
            self.session.register_artifact(
                kind=kind,
                relative_path=relative_path,
                source=self.NAME,
                raw=raw,
            )
            self.session.update_collector(
                self.NAME,
                "starting",
                artifact_path=relative_path,
            )

        raw_path = self.session.paths.root / self.RAW_ARTIFACT
        stderr_path = self.session.paths.root / self.STDERR_ARTIFACT
        raw_path.parent.mkdir(parents=True, exist_ok=True)

        self._stdout = raw_path.open("wb")
        self._stderr = stderr_path.open("wb")
        self._started_utc = _iso_utc(self.clock())

        try:
            existing_pids = set(
                self.adb.get_process_ids(serial, "tcpdump")
            )
        except AdbError:
            existing_pids = set()

        self._remote_dir = (
            f"/data/local/tmp/apk-research/{self.session.session_id}"
        )
        self._remote_stderr_path = (
            f"{self._remote_dir}/tcpdump.stderr.txt"
        )
        try:
            self.adb.make_remote_directory(
                serial,
                self._remote_dir,
            )
            try:
                self.adb.remove_remote_file(
                    serial,
                    self._remote_stderr_path,
                )
            except AdbError:
                pass
        except AdbError as exc:
            self._close_files()
            message = (
                "Unable to prepare tcpdump diagnostic path: "
                f"{exc}"
            )
            self._record_failure(message)
            self._stopped_utc = _iso_utc(self.clock())
            self._write_metadata(
                status="failed",
                error=message,
                returncode=None,
                pcap_format=None,
            )
            self._finished = True
            raise RawNetworkCollectorError(message) from exc

        tcpdump_arguments = [
            preflight.tcpdump_path,
            "-i",
            "any",
            "-p",
            "-s",
            "0",
            "-U",
            "-w",
            "-",
        ]
        shell_command = (
            shlex.join(tcpdump_arguments)
            + " 2>"
            + shlex.quote(self._remote_stderr_path)
        )
        self._command = [
            str(self.adb.adb_path),
            "-s",
            serial,
            "exec-out",
            "sh",
            "-c",
            shell_command,
        ]

        self._write_metadata(
            status="starting",
            error=None,
            returncode=None,
            pcap_format=None,
        )

        try:
            self._process = self.process_factory(
                self._command,
                self._stdout,
                self._stderr,
            )
        except Exception as exc:
            self._close_files()
            self._collect_remote_stderr()
            message = str(exc) or exc.__class__.__name__
            self._record_failure(message)
            self._stopped_utc = _iso_utc(self.clock())
            self._write_metadata(
                status="failed",
                error=message,
                returncode=None,
                pcap_format=None,
            )
            self._finished = True
            raise RawNetworkCollectorError(message) from exc

        returncode = self._process.poll()
        if returncode is not None:
            self._close_files()
            self._collect_remote_stderr()
            message = (
                "tcpdump exited immediately with return code "
                f"{returncode}"
            )
            self._record_failure(message)
            self._stopped_utc = _iso_utc(self.clock())
            self._write_metadata(
                status="failed",
                error=message,
                returncode=returncode,
                pcap_format=None,
            )
            self._finished = True
            raise RawNetworkCollectorError(message)

        self._remote_pid = None
        try:
            current_pids = set(
                self.adb.get_process_ids(serial, "tcpdump")
            )
            new_pids = sorted(current_pids - existing_pids)
            if len(new_pids) == 1:
                self._remote_pid = new_pids[0]
        except AdbError:
            self._remote_pid = None

        self.session.update_collector(self.NAME, "running")
        self._write_metadata(
            status="running",
            error=None,
            returncode=None,
            pcap_format=None,
        )

    def check_health(self) -> bool:
        process = self._require_process()
        returncode = process.poll()
        if returncode is None:
            return True
        if self._stop_requested:
            return True

        self._close_files()
        self._collect_remote_stderr()
        message = (
            "tcpdump exited unexpectedly with return code "
            f"{returncode}"
        )

        pcap_format: str | None = None
        try:
            pcap_format, _ = inspect_pcap(
                self.session.paths.root / self.RAW_ARTIFACT
            )
        except RawNetworkCollectorError:
            pass

        self._record_failure(message)
        self._stopped_utc = _iso_utc(self.clock())
        self._write_metadata(
            status="failed",
            error=message,
            returncode=returncode,
            pcap_format=pcap_format,
        )
        self._finished = True
        return False

    def stop(
        self,
        grace_period: float = 3.0,
    ) -> RawNetworkResult:
        if grace_period < 0:
            raise ValueError("grace_period must be non-negative")

        if self._finished:
            return self._result_from_metadata()

        process = self._require_process()
        if self.session.status not in {
            SessionStatus.STARTING,
            SessionStatus.ACTIVE,
            SessionStatus.STOPPING,
            SessionStatus.FAILED,
        }:
            raise RawNetworkCollectorError(
                "Raw network collector cannot stop while session status "
                f"is {self.session.status.value!r}"
            )

        self._stop_requested = True
        returncode = process.poll()
        process_was_running = returncode is None

        if process_was_running:
            self._request_graceful_stop()
            try:
                returncode = process.wait(timeout=grace_period)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    returncode = process.wait(timeout=grace_period)
                except subprocess.TimeoutExpired:
                    self._forced_kill = True
                    process.kill()
                    try:
                        returncode = process.wait(
                            timeout=max(1.0, grace_period)
                        )
                    except subprocess.TimeoutExpired as exc:
                        self._close_files()
                        message = (
                            "tcpdump process did not exit after kill"
                        )
                        self._record_failure(message)
                        self._stopped_utc = _iso_utc(self.clock())
                        self._write_metadata(
                            status="failed",
                            error=message,
                            returncode=process.poll(),
                            pcap_format=None,
                        )
                        self._finished = True
                        raise RawNetworkCollectorError(
                            message
                        ) from exc

        self._close_files()
        self._collect_remote_stderr()
        self._stopped_utc = _iso_utc(self.clock())

        pcap_format: str | None = None
        bytes_captured = 0
        validation_error: str | None = None
        try:
            pcap_format, bytes_captured = inspect_pcap(
                self.session.paths.root / self.RAW_ARTIFACT
            )
        except RawNetworkCollectorError as exc:
            validation_error = str(exc)

        if not process_was_running:
            error = (
                "tcpdump exited before stop was requested"
                + (
                    f" with return code {returncode}"
                    if returncode is not None
                    else ""
                )
            )
            self._record_failure(error)
            status = "failed"
        elif validation_error is not None:
            error = validation_error
            self._record_failure(error)
            status = "failed"
        else:
            error = None
            status = "completed"
            self.session.update_collector(self.NAME, status)

        self._write_metadata(
            status=status,
            error=error,
            returncode=returncode,
            pcap_format=pcap_format,
        )
        self._finished = True

        return RawNetworkResult(
            collector=self.NAME,
            status=status,
            raw_artifact=self.RAW_ARTIFACT,
            stderr_artifact=self.STDERR_ARTIFACT,
            metadata_artifact=self.METADATA_ARTIFACT,
            started_utc=self._started_utc or "",
            stopped_utc=self._stopped_utc,
            returncode=returncode,
            forced_kill=self._forced_kill,
            bytes_captured=bytes_captured,
            pcap_format=pcap_format or "unknown",
        )

    def _request_graceful_stop(self) -> None:
        if self._preflight is None or self._remote_pid is None:
            return
        try:
            self.adb.send_signal(
                self._preflight.serial,
                self._remote_pid,
                2,
            )
        except AdbError:
            pass

    def _collect_remote_stderr(self) -> None:
        if (
            self._preflight is None
            or self._remote_stderr_path is None
        ):
            return

        local_path = (
            self.session.paths.root / self.STDERR_ARTIFACT
        )
        temporary = local_path.with_name(
            local_path.name + ".remote.tmp"
        )

        try:
            self.adb.pull_file(
                self._preflight.serial,
                self._remote_stderr_path,
                temporary,
                timeout=30.0,
            )
        except AdbError as exc:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            with local_path.open("ab") as handle:
                handle.write(
                    (
                        "[apk-research] unable to retrieve "
                        f"remote tcpdump stderr: {exc}\n"
                    ).encode("utf-8", errors="replace")
                )
        else:
            if temporary.exists():
                with local_path.open("ab") as destination:
                    destination.write(temporary.read_bytes())
        finally:
            temporary.unlink(missing_ok=True)
            try:
                self.adb.remove_remote_file(
                    self._preflight.serial,
                    self._remote_stderr_path,
                )
            except AdbError:
                pass

    def _record_failure(self, message: str) -> None:
        if self._failure_recorded:
            return
        self.session.update_collector(
            self.NAME,
            "failed",
            error=message,
        )
        self._failure_recorded = True

    def _close_files(self) -> None:
        for handle in (self._stdout, self._stderr):
            if handle is not None and not handle.closed:
                handle.flush()
                handle.close()

    def _require_process(self) -> ProcessLike:
        if self._process is None:
            raise RawNetworkCollectorError(
                "Raw network collector is not started"
            )
        return self._process

    def _write_metadata(
        self,
        *,
        status: str,
        error: str | None,
        returncode: int | None,
        pcap_format: str | None,
    ) -> None:
        raw_path = self.session.paths.root / self.RAW_ARTIFACT
        stderr_path = self.session.paths.root / self.STDERR_ARTIFACT
        preflight = (
            self._preflight.to_dict()
            if self._preflight is not None
            else None
        )

        value: dict[str, object] = {
            "schema_version": "0.1",
            "collector": self.NAME,
            "backend": self.BACKEND,
            "status": status,
            "preflight": preflight,
            "command": list(self._command or []),
            "pid": (
                getattr(self._process, "pid", None)
                if self._process is not None
                else None
            ),
            "remote_pid": self._remote_pid,
            "interface": "any",
            "snaplen": 0,
            "packet_buffering": "immediate (-U)",
            "started_utc": self._started_utc,
            "stopped_utc": self._stopped_utc,
            "returncode": returncode,
            "forced_kill": self._forced_kill,
            "pcap_format": pcap_format,
            "bytes_captured": (
                raw_path.stat().st_size if raw_path.exists() else 0
            ),
            "stderr_bytes": (
                stderr_path.stat().st_size
                if stderr_path.exists()
                else 0
            ),
            "error": error,
        }

        _write_json_atomic(
            self.session.paths.root / self.METADATA_ARTIFACT,
            value,
        )

    def _result_from_metadata(self) -> RawNetworkResult:
        metadata = json.loads(
            (
                self.session.paths.root / self.METADATA_ARTIFACT
            ).read_text(encoding="utf-8")
        )
        return RawNetworkResult(
            collector=self.NAME,
            status=str(metadata.get("status") or "failed"),
            raw_artifact=self.RAW_ARTIFACT,
            stderr_artifact=self.STDERR_ARTIFACT,
            metadata_artifact=self.METADATA_ARTIFACT,
            started_utc=str(metadata.get("started_utc") or ""),
            stopped_utc=str(metadata.get("stopped_utc") or ""),
            returncode=metadata.get("returncode"),
            forced_kill=bool(metadata.get("forced_kill", False)),
            bytes_captured=int(metadata.get("bytes_captured") or 0),
            pcap_format=str(metadata.get("pcap_format") or "unknown"),
        )
