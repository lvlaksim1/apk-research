from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Callable, Protocol, Sequence

from mobile_research.session import SessionManager, SessionStatus
from mobile_research.targets import AdbClient, AdbError

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


class LogcatCollectorError(RuntimeError):
    """Raised when continuous logcat capture cannot be started or maintained."""


@dataclass(frozen=True)
class LogcatResult:
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


class LogcatCollector:
    """Continuous raw Android logcat collector.

    The Android log buffer is never cleared. `-T 1` provides minimal pre-roll
    while preserving the device's existing diagnostic state. Exact session
    boundaries are represented by host timestamps in collector metadata.
    """

    NAME = "logcat"
    BACKEND = "adb-logcat"
    RAW_ARTIFACT = "01_raw/logcat/logcat.txt"
    STDERR_ARTIFACT = "01_raw/logcat/logcat.stderr.txt"
    METADATA_ARTIFACT = "02_normalized/logcat.json"

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

        self._process: ProcessLike | None = None
        self._stdout: BinaryIO | None = None
        self._stderr: BinaryIO | None = None
        self._command: list[str] | None = None
        self._started_utc: str | None = None
        self._stop_requested = False
        self._failure_recorded = False
        self._finished = False

    @property
    def running(self) -> bool:
        return (
            self._process is not None
            and not self._finished
            and self._process.poll() is None
        )

    def start(self) -> None:
        if self._process is not None or self._finished:
            raise LogcatCollectorError("Logcat collector was already started")

        if self.session.status != SessionStatus.STARTING:
            raise LogcatCollectorError(
                "Logcat collector may start only while session status is "
                f"'starting'; current status is {self.session.status.value!r}"
            )

        manifest = self.session.manifest
        serial = str(manifest.get("target", {}).get("serial") or "").strip()
        if not serial:
            raise LogcatCollectorError("Session target serial is missing")

        if self.NAME in manifest.get("collectors", {}):
            raise LogcatCollectorError(
                f"Collector already registered: {self.NAME}"
            )

        try:
            self.adb.ensure_ready(serial)
        except AdbError as exc:
            raise LogcatCollectorError(str(exc)) from exc

        self.session.register_collector(
            self.NAME,
            required=True,
            backend=self.BACKEND,
        )

        raw_path = self.session.paths.root / self.RAW_ARTIFACT
        stderr_path = self.session.paths.root / self.STDERR_ARTIFACT
        metadata_path = self.session.paths.root / self.METADATA_ARTIFACT
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        self._stdout = raw_path.open("wb")
        self._stderr = stderr_path.open("wb")
        self._started_utc = _iso_utc(self.clock())

        self._command = [
            str(self.adb.adb_path),
            "-s",
            serial,
            "logcat",
            "-b",
            "all",
            "-v",
            "epoch",
            "-T",
            "1",
        ]

        for kind, relative_path, raw in (
            ("logcat", self.RAW_ARTIFACT, True),
            ("logcat_stderr", self.STDERR_ARTIFACT, True),
            ("logcat_metadata", self.METADATA_ARTIFACT, False),
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

        self._write_metadata(
            status="starting",
            stopped_utc=None,
            returncode=None,
            forced_kill=False,
            error=None,
        )

        try:
            self._process = self.process_factory(
                self._command,
                self._stdout,
                self._stderr,
            )
        except Exception as exc:
            self._close_files()
            message = str(exc) or exc.__class__.__name__
            self._record_failure(f"Unable to start adb logcat: {message}")
            self._write_metadata(
                status="failed",
                stopped_utc=_iso_utc(self.clock()),
                returncode=None,
                forced_kill=False,
                error=message,
            )
            self._finished = True
            raise LogcatCollectorError(message) from exc

        returncode = self._process.poll()
        if returncode is not None:
            self._close_files()
            message = (
                "adb logcat exited immediately with return code "
                f"{returncode}"
            )
            self._record_failure(message)
            self._write_metadata(
                status="failed",
                stopped_utc=_iso_utc(self.clock()),
                returncode=returncode,
                forced_kill=False,
                error=message,
            )
            self._finished = True
            raise LogcatCollectorError(message)

        self.session.update_collector(self.NAME, "running")
        self._write_metadata(
            status="running",
            stopped_utc=None,
            returncode=None,
            forced_kill=False,
            error=None,
        )

    def check_health(self) -> bool:
        process = self._require_process()
        returncode = process.poll()

        if returncode is None:
            return True

        if self._stop_requested:
            return True

        message = (
            "adb logcat exited unexpectedly with return code "
            f"{returncode}"
        )
        self._close_files()
        self._record_failure(message)
        self._write_metadata(
            status="failed",
            stopped_utc=_iso_utc(self.clock()),
            returncode=returncode,
            forced_kill=False,
            error=message,
        )
        self._finished = True
        return False

    def stop(self, grace_period: float = 3.0) -> LogcatResult:
        if grace_period < 0:
            raise ValueError("grace_period must be non-negative")

        process = self._require_process()
        if self._finished:
            return self._result_from_disk(
                status="failed",
                forced_kill=False,
            )

        if self.session.status not in {
            SessionStatus.STARTING,
            SessionStatus.ACTIVE,
            SessionStatus.STOPPING,
            SessionStatus.FAILED,
        }:
            raise LogcatCollectorError(
                "Logcat collector cannot stop while session status is "
                f"{self.session.status.value!r}"
            )

        self._stop_requested = True
        forced_kill = False
        unexpected_exit = process.poll() is not None

        if not unexpected_exit:
            process.terminate()
            try:
                process.wait(timeout=grace_period)
            except subprocess.TimeoutExpired:
                forced_kill = True
                process.kill()
                try:
                    process.wait(timeout=max(1.0, grace_period))
                except subprocess.TimeoutExpired as exc:
                    self._close_files()
                    message = "adb logcat process did not exit after kill"
                    self._record_failure(message)
                    self._write_metadata(
                        status="failed",
                        stopped_utc=_iso_utc(self.clock()),
                        returncode=process.poll(),
                        forced_kill=True,
                        error=message,
                    )
                    self._finished = True
                    raise LogcatCollectorError(message) from exc

        returncode = process.poll()
        stopped_utc = _iso_utc(self.clock())
        self._close_files()

        raw_path = self.session.paths.root / self.RAW_ARTIFACT
        bytes_captured = raw_path.stat().st_size if raw_path.exists() else 0

        if unexpected_exit:
            message = (
                "adb logcat exited before stop was requested"
                if returncode is None
                else (
                    "adb logcat exited before stop was requested with "
                    f"return code {returncode}"
                )
            )
            self._record_failure(message)
            status = "failed"
            error = message
        elif bytes_captured == 0:
            message = "adb logcat produced an empty raw artifact"
            self._record_failure(message)
            status = "failed"
            error = message
        else:
            status = "completed"
            error = None
            self.session.update_collector(self.NAME, status)

        self._write_metadata(
            status=status,
            stopped_utc=stopped_utc,
            returncode=returncode,
            forced_kill=forced_kill,
            error=error,
        )
        self._finished = True

        return LogcatResult(
            collector=self.NAME,
            status=status,
            raw_artifact=self.RAW_ARTIFACT,
            stderr_artifact=self.STDERR_ARTIFACT,
            metadata_artifact=self.METADATA_ARTIFACT,
            started_utc=self._started_utc or "",
            stopped_utc=stopped_utc,
            returncode=returncode,
            forced_kill=forced_kill,
            bytes_captured=bytes_captured,
        )

    def _require_process(self) -> ProcessLike:
        if self._process is None:
            raise LogcatCollectorError("Logcat collector is not started")
        return self._process

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

    def _write_metadata(
        self,
        *,
        status: str,
        stopped_utc: str | None,
        returncode: int | None,
        forced_kill: bool,
        error: str | None,
    ) -> None:
        metadata_path = self.session.paths.root / self.METADATA_ARTIFACT
        raw_path = self.session.paths.root / self.RAW_ARTIFACT
        stderr_path = self.session.paths.root / self.STDERR_ARTIFACT

        value: dict[str, object] = {
            "schema_version": "0.1",
            "collector": self.NAME,
            "backend": self.BACKEND,
            "status": status,
            "command": list(self._command or []),
            "pid": (
                getattr(self._process, "pid", None)
                if self._process is not None
                else None
            ),
            "started_utc": self._started_utc,
            "stopped_utc": stopped_utc,
            "returncode": returncode,
            "forced_kill": forced_kill,
            "pre_roll": {
                "strategy": "logcat -T 1",
                "buffer_cleared": False,
            },
            "bytes_captured": (
                raw_path.stat().st_size if raw_path.exists() else 0
            ),
            "stderr_bytes": (
                stderr_path.stat().st_size if stderr_path.exists() else 0
            ),
            "error": error,
        }
        _write_json_atomic(metadata_path, value)

    def _result_from_disk(
        self,
        *,
        status: str,
        forced_kill: bool,
    ) -> LogcatResult:
        metadata_path = self.session.paths.root / self.METADATA_ARTIFACT
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return LogcatResult(
            collector=self.NAME,
            status=status,
            raw_artifact=self.RAW_ARTIFACT,
            stderr_artifact=self.STDERR_ARTIFACT,
            metadata_artifact=self.METADATA_ARTIFACT,
            started_utc=str(metadata.get("started_utc") or ""),
            stopped_utc=str(metadata.get("stopped_utc") or ""),
            returncode=metadata.get("returncode"),
            forced_kill=forced_kill,
            bytes_captured=int(metadata.get("bytes_captured") or 0),
        )
