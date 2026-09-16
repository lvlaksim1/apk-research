from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO, Callable, Protocol, Sequence

from mobile_research.network_attribution import (
    SNAPSHOTS_ARTIFACT,
    SUMMARY_ARTIFACT,
    parse_socket_snapshot_stream,
    summarize_snapshots,
    write_normalized_attribution,
)
from mobile_research.session import SessionManager, SessionStatus
from mobile_research.targets import AdbClient, AdbError

ProcessFactory = Callable[
    [Sequence[str], BinaryIO, BinaryIO],
    "ProcessLike",
]


class ProcessLike(Protocol):
    pid: int
    returncode: int | None

    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...


class SocketAttributionCollectorError(RuntimeError):
    """Raised when socket-attribution evidence cannot be collected."""


@dataclass(frozen=True)
class SocketAttributionPreflight:
    serial: str
    package: str
    package_uid: int
    uid_packages: tuple[str, ...]
    sample_interval_seconds: float

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["uid_packages"] = list(self.uid_packages)
        return value


@dataclass(frozen=True)
class SocketAttributionResult:
    collector: str
    status: str
    raw_artifact: str
    normalized_artifact: str
    summary_artifact: str
    snapshot_count: int
    socket_observations: int
    package_uid: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


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


class SocketAttributionCollector:
    """Samples Android process/socket ownership while the session is active."""

    NAME = "socket_attribution"
    BACKEND = "android-proc-socket-snapshots"
    RAW_ARTIFACT = "01_raw/network/socket-snapshots.txt"
    STDERR_ARTIFACT = "01_raw/network/socket-attribution.stderr.txt"
    SAMPLE_INTERVAL_SECONDS = 0.20

    def __init__(
        self,
        adb: AdbClient,
        session: SessionManager,
        *,
        process_factory: ProcessFactory = _default_process_factory,
        sample_interval_seconds: float = SAMPLE_INTERVAL_SECONDS,
    ) -> None:
        if sample_interval_seconds <= 0:
            raise ValueError("sample_interval_seconds must be positive")
        self.adb = adb
        self.session = session
        self.process_factory = process_factory
        self.sample_interval_seconds = sample_interval_seconds
        self._preflight: SocketAttributionPreflight | None = None
        self._process: ProcessLike | None = None
        self._stdout: BinaryIO | None = None
        self._stderr: BinaryIO | None = None
        self._finished = False
        self._stop_requested = False
        self._forced_kill = False
        self._remote_pid_file: str | None = None

    @property
    def running(self) -> bool:
        return (
            self._process is not None
            and not self._finished
            and self._process.poll() is None
        )

    def preflight(self) -> SocketAttributionPreflight:
        if self._preflight is not None:
            return self._preflight
        manifest = self.session.manifest
        target = manifest.get("target") or {}
        package_value = manifest.get("package") or {}
        serial = str(target.get("serial") or "").strip()
        package = str(package_value.get("name") or "").strip()
        if not serial:
            raise SocketAttributionCollectorError(
                "Session target serial is missing"
            )
        if not package:
            raise SocketAttributionCollectorError(
                "Session package name is missing"
            )
        try:
            self.adb.ensure_ready(serial)
            if self.adb.get_uid(serial) != 0:
                raise SocketAttributionCollectorError(
                    "Socket attribution requires root ADB on AVD-RESEARCH"
                )
            package_uid = self.adb.get_package_uid(serial, package)
            uid_packages = tuple(
                self.adb.get_packages_for_uid(serial, package_uid)
            )
        except AdbError as exc:
            raise SocketAttributionCollectorError(str(exc)) from exc
        if package not in uid_packages:
            uid_packages = tuple(
                sorted({*uid_packages, package})
            )
        self._preflight = SocketAttributionPreflight(
            serial=serial,
            package=package,
            package_uid=package_uid,
            uid_packages=uid_packages,
            sample_interval_seconds=self.sample_interval_seconds,
        )
        return self._preflight

    def start(self) -> None:
        if self._process is not None or self._finished:
            raise SocketAttributionCollectorError(
                "Socket attribution collector was already started"
            )
        if self.session.status != SessionStatus.STARTING:
            raise SocketAttributionCollectorError(
                "Socket attribution collector may start only while "
                f"session status is 'starting'; current status is "
                f"{self.session.status.value!r}"
            )

        preflight = self.preflight()
        self.session.register_collector(
            self.NAME,
            required=False,
            backend=self.BACKEND,
        )
        for kind, relative_path, raw in (
            ("socket_snapshots_raw", self.RAW_ARTIFACT, True),
            ("socket_attribution_stderr", self.STDERR_ARTIFACT, True),
            ("socket_snapshots", SNAPSHOTS_ARTIFACT, False),
            ("socket_attribution_summary", SUMMARY_ARTIFACT, False),
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

        remote_dir = (
            f"/data/local/tmp/mobile-research/{self.session.session_id}"
        )
        self._remote_pid_file = (
            f"{remote_dir}/socket-attribution.pid"
        )
        try:
            self.adb.make_remote_directory(
                preflight.serial,
                remote_dir,
            )
            try:
                self.adb.remove_remote_file(
                    preflight.serial,
                    self._remote_pid_file,
                )
            except AdbError:
                pass
        except AdbError as exc:
            self._close_files()
            self._mark_failed(str(exc))
            raise SocketAttributionCollectorError(str(exc)) from exc

        script = self._remote_script(preflight)
        command = [
            str(self.adb.adb_path),
            "-s",
            preflight.serial,
            "exec-out",
            "sh",
            "-c",
            script,
        ]
        try:
            self._process = self.process_factory(
                command,
                self._stdout,
                self._stderr,
            )
        except Exception as exc:
            self._close_files()
            self._mark_failed(str(exc) or exc.__class__.__name__)
            raise SocketAttributionCollectorError(
                str(exc) or exc.__class__.__name__
            ) from exc

        returncode = self._process.poll()
        if returncode is not None:
            self._close_files()
            message = (
                "Socket attribution sampler exited immediately with "
                f"return code {returncode}"
            )
            self._mark_failed(message)
            self._finished = True
            raise SocketAttributionCollectorError(message)

        self.session.update_collector(self.NAME, "running")

    def check_health(self) -> bool:
        process = self._require_process()
        returncode = process.poll()
        if returncode is None or self._stop_requested:
            return True
        self._close_files()
        self._normalize_best_effort()
        self.session.update_collector(
            self.NAME,
            "failed",
        )
        self._finished = True
        return False

    def stop(
        self,
        grace_period: float = 3.0,
    ) -> SocketAttributionResult:
        if grace_period < 0:
            raise ValueError("grace_period must be non-negative")
        if self._finished:
            return self._result_from_files()

        process = self._require_process()
        self._stop_requested = True
        returncode = process.poll()
        if returncode is None:
            remote_pid = self._resolve_remote_pid()
            if remote_pid is not None and self._preflight is not None:
                try:
                    self.adb.send_signal(
                        self._preflight.serial,
                        remote_pid,
                        2,
                    )
                except AdbError:
                    pass
            try:
                process.wait(timeout=grace_period)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=grace_period)
                except subprocess.TimeoutExpired:
                    self._forced_kill = True
                    process.kill()
                    process.wait(timeout=max(1.0, grace_period))

        self._close_files()
        summary = self._normalize_best_effort()
        if summary.get("snapshot_count", 0) > 0:
            self.session.update_collector(
                self.NAME,
                "completed",
            )
            status = "completed"
        else:
            self.session.update_collector(
                self.NAME,
                "failed",
            )
            status = "failed"

        self._cleanup_remote_pid_file()
        self._finished = True
        return SocketAttributionResult(
            collector=self.NAME,
            status=status,
            raw_artifact=self.RAW_ARTIFACT,
            normalized_artifact=SNAPSHOTS_ARTIFACT,
            summary_artifact=SUMMARY_ARTIFACT,
            snapshot_count=int(summary.get("snapshot_count") or 0),
            socket_observations=int(
                summary.get("socket_observations") or 0
            ),
            package_uid=int(summary.get("package_uid") or 0),
        )

    def _remote_script(
        self,
        preflight: SocketAttributionPreflight,
    ) -> str:
        pid_file = shlex.quote(self._remote_pid_file or "")
        interval = f"{self.sample_interval_seconds:.3f}"
        uid = preflight.package_uid
        package = shlex.quote(preflight.package)
        return (
            f"APP_UID={uid}; APP_PACKAGE={package}; PID_FILE={pid_file}; "
            'echo $$ > "$PID_FILE"; '
            'trap \'rm -f "$PID_FILE"; exit 0\' INT TERM HUP; '
            "while :; do "
            'TS=$(date +%s%N); echo "SNAP|$TS"; '
            "for T in tcp tcp6 udp udp6; do "
            'if [ -r "/proc/net/$T" ]; then '
            'while IFS= read -r L; do echo "ROW|$T|$L"; '
            'done < "/proc/net/$T"; fi; done; '
            "for P in /proc/[0-9]*; do "
            '[ -r "$P/status" ] || continue; '
            'U=""; '
            'while read -r K V REST; do '
            'case "$K" in Uid:) U="$V"; break;; esac; '
            'done < "$P/status"; '
            '[ "$U" = "$APP_UID" ] || continue; '
            'PID=${P##*/}; '
            'N=$(tr "\\000" " " < "$P/cmdline" 2>/dev/null); '
            'N=${N%% *}; '
            'echo "PROC|$PID|$U|$N"; '
            'case "$N" in "$APP_PACKAGE"|"$APP_PACKAGE":*) '
            'for F in "$P"/fd/*; do '
            'R=$(readlink "$F" 2>/dev/null) || continue; '
            'case "$R" in socket:\\[*\\]) '
            'I=${R#socket:[}; I=${I%]}; echo "FD|$PID|$I";; esac; '
            'done;; esac; '
            "done; "
            'echo "END|$TS"; '
            f"sleep {interval}; "
            "done"
        )

    def _resolve_remote_pid(self) -> int | None:
        if self._preflight is None or self._remote_pid_file is None:
            return None
        try:
            value = self.adb.shell_output(
                self._preflight.serial,
                "cat",
                self._remote_pid_file,
                timeout=3.0,
            ).strip()
        except AdbError:
            return None
        try:
            pid = int(value)
        except ValueError:
            return None
        return pid if pid > 0 else None

    def _normalize_best_effort(self) -> dict[str, object]:
        preflight = self._preflight
        if preflight is None:
            return {}
        raw_path = self.session.paths.root / self.RAW_ARTIFACT
        try:
            text = raw_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            text = ""
        snapshots = parse_socket_snapshot_stream(
            text,
            package=preflight.package,
            package_uid=preflight.package_uid,
            uid_packages=list(preflight.uid_packages),
        )
        summary = summarize_snapshots(
            snapshots,
            package=preflight.package,
            package_uid=preflight.package_uid,
            uid_packages=list(preflight.uid_packages),
            sample_interval_seconds=preflight.sample_interval_seconds,
        )
        write_normalized_attribution(
            self.session.paths.root,
            snapshots,
            summary,
        )
        return summary

    def _result_from_files(self) -> SocketAttributionResult:
        preflight = self.preflight()
        try:
            summary = json.loads(
                (
                    self.session.paths.root / SUMMARY_ARTIFACT
                ).read_text(encoding="utf-8")
            )
        except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError):
            summary = {}
        status = str(
            self.session.manifest.get("collectors", {})
            .get(self.NAME, {})
            .get("status")
            or "failed"
        )
        return SocketAttributionResult(
            collector=self.NAME,
            status=status,
            raw_artifact=self.RAW_ARTIFACT,
            normalized_artifact=SNAPSHOTS_ARTIFACT,
            summary_artifact=SUMMARY_ARTIFACT,
            snapshot_count=int(summary.get("snapshot_count") or 0),
            socket_observations=int(
                summary.get("socket_observations") or 0
            ),
            package_uid=preflight.package_uid,
        )

    def _mark_failed(self, message: str) -> None:
        try:
            self._normalize_best_effort()
        except Exception:
            pass
        try:
            self.session.update_collector(
                self.NAME,
                "failed",
            )
        except Exception:
            pass
        path = self.session.paths.root / self.STDERR_ARTIFACT
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as handle:
            handle.write(
                ("[mobile-research] " + message + "\n").encode(
                    "utf-8",
                    errors="replace",
                )
            )

    def _cleanup_remote_pid_file(self) -> None:
        if self._preflight is None or self._remote_pid_file is None:
            return
        try:
            self.adb.remove_remote_file(
                self._preflight.serial,
                self._remote_pid_file,
            )
        except AdbError:
            pass

    def _close_files(self) -> None:
        for handle in (self._stdout, self._stderr):
            if handle is not None and not handle.closed:
                handle.flush()
                os.fsync(handle.fileno())
                handle.close()

    def _require_process(self) -> ProcessLike:
        if self._process is None:
            raise SocketAttributionCollectorError(
                "Socket attribution sampler was not started"
            )
        return self._process
