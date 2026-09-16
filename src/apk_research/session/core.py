from __future__ import annotations

import json
import os
import platform
import re
import socket
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

from apk_research import __version__

Clock = Callable[[], datetime]
SessionIdFactory = Callable[[], str]


class SessionError(RuntimeError):
    """Base exception for research session lifecycle errors."""


class InvalidSessionTransition(SessionError):
    """Raised when a lifecycle transition is not permitted."""


class InvalidArtifactPath(SessionError):
    """Raised when an artifact path escapes the session root."""


class SessionStatus(str, Enum):
    CREATED = "created"
    PREFLIGHT = "preflight"
    READY = "ready"
    STARTING = "starting"
    ACTIVE = "active"
    STOPPING = "stopping"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


TERMINAL_STATUSES = {
    SessionStatus.COMPLETE,
    SessionStatus.PARTIAL,
    SessionStatus.FAILED,
}

_ALLOWED_TRANSITIONS: dict[SessionStatus, set[SessionStatus]] = {
    SessionStatus.CREATED: {SessionStatus.PREFLIGHT, SessionStatus.FAILED},
    SessionStatus.PREFLIGHT: {SessionStatus.READY, SessionStatus.FAILED},
    SessionStatus.READY: {SessionStatus.STARTING, SessionStatus.FAILED},
    SessionStatus.STARTING: {SessionStatus.ACTIVE, SessionStatus.FAILED},
    SessionStatus.ACTIVE: {SessionStatus.STOPPING, SessionStatus.FAILED},
    SessionStatus.STOPPING: {
        SessionStatus.COMPLETE,
        SessionStatus.PARTIAL,
        SessionStatus.FAILED,
    },
    SessionStatus.COMPLETE: set(),
    SessionStatus.PARTIAL: set(),
    SessionStatus.FAILED: set(),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_session_id() -> str:
    timestamp = utc_now().strftime("%Y%m%dT%H%M%S.%fZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def default_runtime_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "apk-research" / "sessions"
    return Path.home() / ".apk-research" / "sessions"


@dataclass(frozen=True)
class SessionPaths:
    root: Path
    manifest_dir: Path
    manifest: Path
    checksums: Path
    raw_dir: Path
    raw_logcat: Path
    raw_screen: Path
    raw_network: Path
    raw_device: Path
    normalized_dir: Path

    @classmethod
    def for_root(cls, root: Path) -> "SessionPaths":
        manifest_dir = root / "00_manifest"
        raw_dir = root / "01_raw"
        return cls(
            root=root,
            manifest_dir=manifest_dir,
            manifest=manifest_dir / "session.json",
            checksums=manifest_dir / "checksums.sha256",
            raw_dir=raw_dir,
            raw_logcat=raw_dir / "logcat",
            raw_screen=raw_dir / "screen",
            raw_network=raw_dir / "network",
            raw_device=raw_dir / "device",
            normalized_dir=root / "02_normalized",
        )

    def create_layout(self) -> None:
        for directory in (
            self.root,
            self.manifest_dir,
            self.raw_logcat,
            self.raw_screen,
            self.raw_network,
            self.raw_device,
            self.normalized_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


class SessionManager:
    """Owns one research session manifest and its lifecycle."""

    SCHEMA_VERSION = "0.1"

    def __init__(
        self,
        paths: SessionPaths,
        manifest: dict[str, Any],
        *,
        clock: Clock = utc_now,
    ) -> None:
        self.paths = paths
        self._manifest = manifest
        self._clock = clock

    @classmethod
    def create(
        cls,
        runtime_root: str | os.PathLike[str] | None,
        *,
        target: Mapping[str, Any],
        package: Mapping[str, Any],
        clock: Clock = utc_now,
        session_id_factory: SessionIdFactory = generate_session_id,
    ) -> "SessionManager":
        base_root = (
            Path(runtime_root)
            if runtime_root is not None
            else default_runtime_root()
        )
        base_root = base_root.expanduser().resolve()
        session_id = session_id_factory().strip()

        if not session_id:
            raise SessionError("Session ID factory returned an empty value")
        if Path(session_id).name != session_id or session_id in {".", ".."}:
            raise SessionError(f"Unsafe session ID: {session_id!r}")

        session_root = base_root / session_id
        if session_root.exists():
            raise SessionError(f"Session directory already exists: {session_root}")

        paths = SessionPaths.for_root(session_root)
        paths.create_layout()

        now = iso_utc(clock())
        manifest: dict[str, Any] = {
            "schema_version": cls.SCHEMA_VERSION,
            "session_id": session_id,
            "apk_research_version": __version__,
            "status": SessionStatus.CREATED.value,
            "degraded": False,
            "host": {
                "hostname": socket.gethostname(),
                "platform": platform.platform(),
                "python": platform.python_version(),
            },
            "target": deepcopy(dict(target)),
            "package": deepcopy(dict(package)),
            "timestamps": {
                "created": now,
                "updated": now,
                "started": None,
                "stopped": None,
            },
            "collectors": {},
            "artifacts": [],
            "errors": [],
            "state_history": [
                {
                    "from": None,
                    "to": SessionStatus.CREATED.value,
                    "timestamp": now,
                    "reason": "session created",
                }
            ],
        }

        manager = cls(paths, manifest, clock=clock)
        manager._write_manifest()
        return manager

    @classmethod
    def load(
        cls,
        session_root: str | os.PathLike[str],
        *,
        clock: Clock = utc_now,
    ) -> "SessionManager":
        paths = SessionPaths.for_root(Path(session_root).expanduser().resolve())
        try:
            manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SessionError(
                f"Session manifest not found: {paths.manifest}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise SessionError(
                f"Session manifest is not valid JSON: {paths.manifest}"
            ) from exc

        if manifest.get("schema_version") != cls.SCHEMA_VERSION:
            raise SessionError(
                "Unsupported session manifest schema: "
                f"{manifest.get('schema_version')!r}"
            )

        try:
            SessionStatus(manifest["status"])
        except (KeyError, ValueError) as exc:
            raise SessionError("Session manifest has invalid status") from exc

        return cls(paths, manifest, clock=clock)

    @property
    def manifest(self) -> dict[str, Any]:
        return deepcopy(self._manifest)

    @property
    def session_id(self) -> str:
        return str(self._manifest["session_id"])

    @property
    def status(self) -> SessionStatus:
        return SessionStatus(self._manifest["status"])

    @property
    def degraded(self) -> bool:
        return bool(self._manifest.get("degraded", False))

    def transition(
        self,
        new_status: SessionStatus | str,
        *,
        reason: str | None = None,
    ) -> None:
        destination = SessionStatus(new_status)
        current = self.status

        if destination == current:
            raise InvalidSessionTransition(
                f"Session is already in state {current.value}"
            )
        if destination not in _ALLOWED_TRANSITIONS[current]:
            raise InvalidSessionTransition(
                f"Invalid session transition: "
                f"{current.value} -> {destination.value}"
            )

        now = iso_utc(self._clock())
        self._manifest["status"] = destination.value
        self._manifest["timestamps"]["updated"] = now

        if destination == SessionStatus.ACTIVE:
            self._manifest["timestamps"]["started"] = now
        elif destination in TERMINAL_STATUSES:
            self._manifest["timestamps"]["stopped"] = now

        self._manifest["state_history"].append(
            {
                "from": current.value,
                "to": destination.value,
                "timestamp": now,
                "reason": reason,
            }
        )
        self._write_manifest()

    def record_error(
        self,
        source: str,
        message: str,
        *,
        fatal: bool = False,
    ) -> None:
        now = iso_utc(self._clock())
        self._manifest["errors"].append(
            {
                "timestamp": now,
                "source": source,
                "message": message,
                "fatal": fatal,
            }
        )
        self._manifest["timestamps"]["updated"] = now

        if fatal:
            if self.status in TERMINAL_STATUSES:
                self._write_manifest()
                return
            self._manifest["degraded"] = True
            self._write_manifest()
            self.transition(
                SessionStatus.FAILED,
                reason=f"fatal error from {source}",
            )
            return

        self._manifest["degraded"] = True
        self._write_manifest()

    def register_collector(
        self,
        name: str,
        *,
        required: bool,
        backend: str | None = None,
    ) -> None:
        normalized_name = name.strip()
        if not normalized_name:
            raise SessionError("Collector name cannot be empty")

        collectors = self._manifest["collectors"]
        if normalized_name in collectors:
            raise SessionError(f"Collector already registered: {normalized_name}")

        now = iso_utc(self._clock())
        collectors[normalized_name] = {
            "required": required,
            "backend": backend,
            "status": "registered",
            "updated": now,
            "artifact_paths": [],
            "error": None,
        }
        self._manifest["timestamps"]["updated"] = now
        self._write_manifest()

    def update_collector(
        self,
        name: str,
        status: str,
        *,
        artifact_path: str | None = None,
        error: str | None = None,
    ) -> None:
        try:
            collector = self._manifest["collectors"][name]
        except KeyError as exc:
            raise SessionError(f"Unknown collector: {name}") from exc

        now = iso_utc(self._clock())
        collector["status"] = status
        collector["updated"] = now

        if artifact_path is not None:
            relative_path = self._validate_relative_artifact_path(artifact_path)
            if relative_path not in collector["artifact_paths"]:
                collector["artifact_paths"].append(relative_path)

        if error is not None:
            collector["error"] = error
            self._manifest["degraded"] = True
            self._manifest["errors"].append(
                {
                    "timestamp": now,
                    "source": f"collector:{name}",
                    "message": error,
                    "fatal": False,
                }
            )

        self._manifest["timestamps"]["updated"] = now
        self._write_manifest()

    def register_artifact(
        self,
        *,
        kind: str,
        relative_path: str,
        source: str,
        raw: bool = True,
    ) -> None:
        safe_path = self._validate_relative_artifact_path(relative_path)
        now = iso_utc(self._clock())

        if any(
            artifact["path"] == safe_path
            for artifact in self._manifest["artifacts"]
        ):
            raise SessionError(f"Artifact already registered: {safe_path}")

        self._manifest["artifacts"].append(
            {
                "kind": kind,
                "path": safe_path,
                "source": source,
                "raw": raw,
                "registered": now,
            }
        )
        self._manifest["timestamps"]["updated"] = now
        self._write_manifest()

    def begin_preflight(self) -> None:
        self.transition(SessionStatus.PREFLIGHT, reason="preflight started")

    def mark_ready(self) -> None:
        self.transition(SessionStatus.READY, reason="preflight completed")

    def begin_start(self) -> None:
        self.transition(SessionStatus.STARTING, reason="collectors starting")

    def mark_active(self) -> None:
        self.transition(SessionStatus.ACTIVE, reason="capture active")

    def begin_stop(self) -> None:
        self.transition(SessionStatus.STOPPING, reason="stop requested")

    def finish(self) -> SessionStatus:
        if self.status != SessionStatus.STOPPING:
            raise InvalidSessionTransition(
                f"Cannot finish session from state {self.status.value}"
            )

        final_status = (
            SessionStatus.PARTIAL
            if self.degraded
            else SessionStatus.COMPLETE
        )
        self.transition(
            final_status,
            reason=(
                "session finished with degraded evidence"
                if final_status == SessionStatus.PARTIAL
                else "session finished successfully"
            ),
        )
        return final_status

    def fail(self, source: str, message: str) -> None:
        self.record_error(source, message, fatal=True)

    def _validate_relative_artifact_path(self, value: str) -> str:
        normalized = value.replace("\\", "/")
        path = PurePosixPath(normalized)
        windows_absolute = bool(re.match(r"^[A-Za-z]:/", normalized))

        if (
            not normalized
            or path.is_absolute()
            or windows_absolute
            or ".." in path.parts
            or "." in path.parts
        ):
            raise InvalidArtifactPath(
                f"Artifact path must remain inside session root: {value!r}"
            )

        return path.as_posix()

    def _write_manifest(self) -> None:
        self.paths.manifest_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.paths.manifest.with_suffix(".json.tmp")

        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    self._manifest,
                    handle,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temporary, self.paths.manifest)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)
