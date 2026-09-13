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
    [Sequence[str], BinaryIO],
    ProcessLike,
]


class ScreenRecordingCollectorError(RuntimeError):
    """Raised when screen recording cannot be started or preserved."""


@dataclass(frozen=True)
class ScreenRecordingResult:
    collector: str
    status: str
    chunks: tuple[str, ...]
    metadata_artifact: str
    started_utc: str
    stopped_utc: str
    forced_kill: bool
    bytes_captured: int

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["chunks"] = list(self.chunks)
        return result


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
    diagnostic: BinaryIO,
) -> ProcessLike:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        list(command),
        stdin=subprocess.DEVNULL,
        stdout=diagnostic,
        stderr=subprocess.STDOUT,
        creationflags=creation_flags,
    )


class ScreenRecordingCollector:
    """Chunked Android screenrecord collector.

    Chunk rotation is cooperative: the session orchestrator calls check_health()
    regularly. A completed time-limited chunk is pulled immediately and the next
    chunk starts before the target application continues for long without video.
    """

    NAME = "screen_recording"
    BACKEND = "adb-screenrecord"
    METADATA_ARTIFACT = "02_normalized/screen.json"
    DEFAULT_CHUNK_SECONDS = 170
    REMOTE_ROOT = "/data/local/tmp/mobile-research"

    def __init__(
        self,
        adb: AdbClient,
        session: SessionManager,
        *,
        chunk_seconds: int = DEFAULT_CHUNK_SECONDS,
        clock: Clock = _utc_now,
        process_factory: ProcessFactory = _default_process_factory,
    ) -> None:
        if not 1 <= chunk_seconds <= 180:
            raise ValueError("chunk_seconds must be between 1 and 180")

        self.adb = adb
        self.session = session
        self.chunk_seconds = chunk_seconds
        self.clock = clock
        self.process_factory = process_factory

        self._serial: str | None = None
        self._remote_dir: str | None = None
        self._process: ProcessLike | None = None
        self._diagnostic: BinaryIO | None = None
        self._remote_pid: int | None = None
        self._chunk_index = 0
        self._current_chunk: dict[str, object] | None = None
        self._chunks: list[dict[str, object]] = []
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

    def start(self) -> None:
        if self._process is not None or self._finished:
            raise ScreenRecordingCollectorError(
                "Screen recording collector was already started"
            )
        if self.session.status != SessionStatus.STARTING:
            raise ScreenRecordingCollectorError(
                "Screen recording collector may start only while session "
                f"status is 'starting'; current status is "
                f"{self.session.status.value!r}"
            )

        manifest = self.session.manifest
        serial = str(manifest.get("target", {}).get("serial") or "").strip()
        if not serial:
            raise ScreenRecordingCollectorError(
                "Session target serial is missing"
            )
        if self.NAME in manifest.get("collectors", {}):
            raise ScreenRecordingCollectorError(
                f"Collector already registered: {self.NAME}"
            )

        try:
            self.adb.ensure_ready(serial)
        except AdbError as exc:
            raise ScreenRecordingCollectorError(str(exc)) from exc

        self._serial = serial
        self._remote_dir = (
            f"{self.REMOTE_ROOT}/{self.session.session_id}"
        )

        try:
            self.adb.make_remote_directory(serial, self._remote_dir)
        except AdbError as exc:
            raise ScreenRecordingCollectorError(
                f"Unable to create remote screen directory: {exc}"
            ) from exc

        self.session.register_collector(
            self.NAME,
            required=True,
            backend=self.BACKEND,
        )
        self.session.register_artifact(
            kind="screen_metadata",
            relative_path=self.METADATA_ARTIFACT,
            source=self.NAME,
            raw=False,
        )
        self.session.update_collector(
            self.NAME,
            "starting",
            artifact_path=self.METADATA_ARTIFACT,
        )

        self._started_utc = _iso_utc(self.clock())
        self._write_metadata(status="starting", error=None)

        try:
            self._start_next_chunk()
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            self._record_failure(message)
            self._write_metadata(status="failed", error=message)
            self._finished = True
            if isinstance(exc, ScreenRecordingCollectorError):
                raise
            raise ScreenRecordingCollectorError(message) from exc

        self.session.update_collector(self.NAME, "running")
        self._write_metadata(status="running", error=None)

    def check_health(self) -> bool:
        process = self._require_process()
        returncode = process.poll()

        if returncode is None:
            return True

        if self._stop_requested:
            return True

        if not self._finalize_current_chunk(
            expected_stop=False,
            returncode=returncode,
        ):
            self._finished = True
            self._write_metadata(
                status="failed",
                error="Screen recording chunk failed",
            )
            return False

        try:
            self._start_next_chunk()
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            self._record_failure(message)
            self._write_metadata(status="failed", error=message)
            self._finished = True
            return False

        self._write_metadata(status="running", error=None)
        return True

    def stop(
        self,
        grace_period: float = 5.0,
    ) -> ScreenRecordingResult:
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
            raise ScreenRecordingCollectorError(
                "Screen recording collector cannot stop while session "
                f"status is {self.session.status.value!r}"
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
                        self._close_diagnostic()
                        message = (
                            "screenrecord process did not exit after kill"
                        )
                        self._record_failure(message)
                        self._stopped_utc = _iso_utc(self.clock())
                        self._write_metadata(
                            status="failed",
                            error=message,
                        )
                        self._finished = True
                        raise ScreenRecordingCollectorError(
                            message
                        ) from exc

        success = self._finalize_current_chunk(
            expected_stop=process_was_running,
            returncode=returncode,
        )
        self._stopped_utc = _iso_utc(self.clock())

        if success and self._chunks:
            status = "completed"
            error = None
            self.session.update_collector(self.NAME, status)
        else:
            status = "failed"
            error = "No valid screen recording chunk was preserved"
            self._record_failure(error)

        self._write_metadata(status=status, error=error)
        self._finished = True
        return self._result_from_metadata()

    def _start_next_chunk(self) -> None:
        if self._serial is None or self._remote_dir is None:
            raise ScreenRecordingCollectorError(
                "Screen recording collector is not initialized"
            )

        self._close_diagnostic()
        self._chunk_index += 1
        name = f"screen-{self._chunk_index:04d}"
        local_video = f"01_raw/screen/{name}.mp4"
        diagnostic_path = f"01_raw/screen/{name}.screenrecord.txt"
        remote_video = f"{self._remote_dir}/{name}.mp4"

        diagnostic_file = self.session.paths.root / diagnostic_path
        diagnostic_file.parent.mkdir(parents=True, exist_ok=True)
        self._diagnostic = diagnostic_file.open("wb")

        self.session.register_artifact(
            kind="screenrecord_diagnostic",
            relative_path=diagnostic_path,
            source=self.NAME,
            raw=True,
        )
        self.session.update_collector(
            self.NAME,
            "running",
            artifact_path=diagnostic_path,
        )

        existing_pids: set[int]
        try:
            existing_pids = set(
                self.adb.get_process_ids(
                    self._serial,
                    "screenrecord",
                )
            )
        except AdbError:
            existing_pids = set()

        command = [
            str(self.adb.adb_path),
            "-s",
            self._serial,
            "shell",
            "screenrecord",
            "--verbose",
            "--time-limit",
            str(self.chunk_seconds),
            remote_video,
        ]

        started_utc = _iso_utc(self.clock())
        try:
            process = self.process_factory(
                command,
                self._diagnostic,
            )
        except Exception:
            self._close_diagnostic()
            raise

        if process.poll() is not None:
            self._close_diagnostic()
            raise ScreenRecordingCollectorError(
                "screenrecord exited immediately with return code "
                f"{process.poll()}"
            )

        self._process = process
        self._remote_pid = None

        try:
            current_pids = set(
                self.adb.get_process_ids(
                    self._serial,
                    "screenrecord",
                )
            )
            new_pids = sorted(current_pids - existing_pids)
            if len(new_pids) == 1:
                self._remote_pid = new_pids[0]
        except AdbError:
            self._remote_pid = None

        self._current_chunk = {
            "index": self._chunk_index,
            "local_video": local_video,
            "diagnostic": diagnostic_path,
            "remote_video": remote_video,
            "command": command,
            "host_started_utc": started_utc,
            "host_finished_utc": None,
            "returncode": None,
            "remote_pid": self._remote_pid,
            "bytes": 0,
            "status": "recording",
            "error": None,
        }

    def _finalize_current_chunk(
        self,
        *,
        expected_stop: bool,
        returncode: int | None,
    ) -> bool:
        if (
            self._current_chunk is None
            or self._serial is None
        ):
            raise ScreenRecordingCollectorError(
                "No active screen recording chunk"
            )

        self._close_diagnostic()
        chunk = self._current_chunk
        chunk["host_finished_utc"] = _iso_utc(self.clock())
        chunk["returncode"] = returncode

        local_relative = str(chunk["local_video"])
        local_path = self.session.paths.root / local_relative
        remote_path = str(chunk["remote_video"])

        pull_error: str | None = None
        try:
            self.adb.pull_file(
                self._serial,
                remote_path,
                local_path,
            )
        except AdbError as exc:
            pull_error = str(exc)
        finally:
            try:
                self.adb.remove_remote_file(
                    self._serial,
                    remote_path,
                )
            except AdbError:
                pass

        size = local_path.stat().st_size if local_path.exists() else 0
        chunk["bytes"] = size

        valid_video = size > 0
        valid_exit = expected_stop or returncode == 0

        if valid_video:
            self.session.register_artifact(
                kind="screen_video",
                relative_path=local_relative,
                source=self.NAME,
                raw=True,
            )
            self.session.update_collector(
                self.NAME,
                "running",
                artifact_path=local_relative,
            )

        if pull_error is not None:
            chunk["status"] = "failed"
            chunk["error"] = f"Unable to pull screen chunk: {pull_error}"
        elif not valid_video:
            chunk["status"] = "failed"
            chunk["error"] = "Screen recording chunk is empty or missing"
        elif not valid_exit:
            chunk["status"] = "failed"
            chunk["error"] = (
                "screenrecord exited unexpectedly with return code "
                f"{returncode}"
            )
        else:
            chunk["status"] = "completed"
            chunk["error"] = None

        self._chunks.append(dict(chunk))
        self._current_chunk = None
        self._process = None
        self._remote_pid = None

        if chunk["status"] != "completed":
            self._record_failure(str(chunk["error"]))
            return False

        return True

    def _request_graceful_stop(self) -> None:
        if (
            self._serial is None
            or self._remote_pid is None
        ):
            return
        try:
            self.adb.send_signal(
                self._serial,
                self._remote_pid,
                2,
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

    def _close_diagnostic(self) -> None:
        if self._diagnostic is not None and not self._diagnostic.closed:
            self._diagnostic.flush()
            self._diagnostic.close()

    def _require_process(self) -> ProcessLike:
        if self._process is None:
            raise ScreenRecordingCollectorError(
                "Screen recording collector is not started"
            )
        return self._process

    def _write_metadata(
        self,
        *,
        status: str,
        error: str | None,
    ) -> None:
        current = (
            dict(self._current_chunk)
            if self._current_chunk is not None
            else None
        )
        value: dict[str, object] = {
            "schema_version": "0.1",
            "collector": self.NAME,
            "backend": self.BACKEND,
            "status": status,
            "chunk_seconds": self.chunk_seconds,
            "started_utc": self._started_utc,
            "stopped_utc": self._stopped_utc,
            "forced_kill": self._forced_kill,
            "completed_chunks": list(self._chunks),
            "current_chunk": current,
            "bytes_captured": sum(
                int(chunk.get("bytes") or 0)
                for chunk in self._chunks
            ),
            "error": error,
        }
        _write_json_atomic(
            self.session.paths.root / self.METADATA_ARTIFACT,
            value,
        )

    def _result_from_metadata(self) -> ScreenRecordingResult:
        metadata = json.loads(
            (
                self.session.paths.root / self.METADATA_ARTIFACT
            ).read_text(encoding="utf-8")
        )
        chunk_paths = tuple(
            str(chunk["local_video"])
            for chunk in metadata.get("completed_chunks", [])
            if chunk.get("status") == "completed"
        )
        return ScreenRecordingResult(
            collector=self.NAME,
            status=str(metadata.get("status") or "failed"),
            chunks=chunk_paths,
            metadata_artifact=self.METADATA_ARTIFACT,
            started_utc=str(metadata.get("started_utc") or ""),
            stopped_utc=str(metadata.get("stopped_utc") or ""),
            forced_kill=bool(metadata.get("forced_kill", False)),
            bytes_captured=int(metadata.get("bytes_captured") or 0),
        )
