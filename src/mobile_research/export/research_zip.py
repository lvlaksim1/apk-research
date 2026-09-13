from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from mobile_research.session import (
    SessionManager,
    SessionStatus,
    TERMINAL_STATUSES,
)

_CHECKSUM_RE = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_COLLECTORS = (
    "device_metadata",
    "logcat",
    "screen_recording",
    "raw_network",
)
_REQUIRED_FIXED_FILES = (
    "00_manifest/session.json",
    "01_raw/device/getprop.txt",
    "01_raw/device/package.txt",
    "01_raw/device/package-paths.txt",
    "01_raw/device/system.txt",
    "01_raw/device/clock.txt",
    "01_raw/logcat/logcat.txt",
    "01_raw/network/traffic.pcap",
)


class ExportError(RuntimeError):
    """Raised when a Research ZIP cannot be created or verified."""


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: str | None = None
    severity: str = "error"

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(frozen=True)
class SessionValidation:
    session_status: str
    valid_for_complete: bool
    issues: tuple[ValidationIssue, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "session_status": self.session_status,
            "valid_for_complete": self.valid_for_complete,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class ExportResult:
    archive: str
    session_id: str
    session_status: str
    file_count: int
    total_uncompressed_bytes: int
    checksum_entries: int
    validation: SessionValidation

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["validation"] = self.validation.to_dict()
        return result


@dataclass(frozen=True)
class ZipVerification:
    archive: str
    valid: bool
    file_count: int
    checksum_entries: int
    session_id: str
    session_status: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_stream(handle, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = handle.read(chunk_size)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def _safe_archive_name(value: str) -> str:
    if "\n" in value or "\r" in value or "\\" in value:
        raise ExportError(f"Unsafe archive path: {value!r}")

    path = PurePosixPath(value)
    normalized = path.as_posix()
    if (
        not value
        or path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or normalized != value
    ):
        raise ExportError(f"Unsafe archive path: {value!r}")

    return normalized


def _relative_path(root: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ExportError(
            f"File escapes session root: {path}"
        ) from exc
    return _safe_archive_name(relative.as_posix())


def _iter_session_files(root: Path, checksums_path: Path) -> list[Path]:
    files: list[Path] = []
    checksums_resolved = checksums_path.resolve()

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == checksums_resolved:
            continue
        if path.name.endswith(".tmp"):
            continue
        files.append(path)

    files.sort(key=lambda item: _relative_path(root, item))
    return files


def _is_nonempty(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def validate_session(session: SessionManager) -> SessionValidation:
    manifest = session.manifest
    status = session.status
    strict = status == SessionStatus.COMPLETE
    severity = "error" if strict else "warning"
    issues: list[ValidationIssue] = []

    if status not in TERMINAL_STATUSES:
        issues.append(
            ValidationIssue(
                code="session_not_terminal",
                message=(
                    "Session must be complete, partial, or failed before export"
                ),
                severity="error",
            )
        )
        return SessionValidation(
            session_status=status.value,
            valid_for_complete=False,
            issues=tuple(issues),
        )

    collectors = manifest.get("collectors", {})
    for name in _REQUIRED_COLLECTORS:
        collector = collectors.get(name)
        if collector is None:
            issues.append(
                ValidationIssue(
                    code="required_collector_missing",
                    message=f"Required collector is missing: {name}",
                    severity=severity,
                )
            )
            continue

        collector_status = str(collector.get("status") or "")
        if collector_status != "completed":
            issues.append(
                ValidationIssue(
                    code="required_collector_not_completed",
                    message=(
                        f"Required collector {name} has status "
                        f"{collector_status!r}"
                    ),
                    severity=severity,
                )
            )

    for relative in _REQUIRED_FIXED_FILES:
        path = session.paths.root / Path(relative)
        if not _is_nonempty(path):
            issues.append(
                ValidationIssue(
                    code="required_evidence_missing_or_empty",
                    message=(
                        "Required evidence file is missing or empty: "
                        f"{relative}"
                    ),
                    path=relative,
                    severity=severity,
                )
            )

    screen_files = sorted(
        session.paths.raw_screen.glob("screen-*.mp4")
    )
    if not any(_is_nonempty(path) for path in screen_files):
        issues.append(
            ValidationIssue(
                code="screen_evidence_missing",
                message=(
                    "No non-empty screen recording chunk is available"
                ),
                path="01_raw/screen/",
                severity=severity,
            )
        )

    for artifact in manifest.get("artifacts", []):
        relative = str(artifact.get("path") or "")
        if not relative:
            continue
        try:
            safe = _safe_archive_name(relative)
        except ExportError as exc:
            issues.append(
                ValidationIssue(
                    code="registered_artifact_path_invalid",
                    message=str(exc),
                    path=relative,
                    severity=severity,
                )
            )
            continue

        path = session.paths.root / Path(safe)
        if not path.is_file():
            issues.append(
                ValidationIssue(
                    code="registered_artifact_missing",
                    message=(
                        "Registered artifact is missing from session: "
                        f"{safe}"
                    ),
                    path=safe,
                    severity=severity,
                )
            )

    valid_for_complete = not any(
        issue.severity == "error" for issue in issues
    )
    return SessionValidation(
        session_status=status.value,
        valid_for_complete=valid_for_complete,
        issues=tuple(issues),
    )


def _write_checksums(
    session: SessionManager,
    files: Iterable[Path],
) -> dict[str, str]:
    checksums: dict[str, str] = {}

    for path in files:
        relative = _relative_path(session.paths.root, path)
        checksums[relative] = sha256_file(path)

    temporary = session.paths.checksums.with_name(
        session.paths.checksums.name + ".tmp"
    )
    session.paths.checksums.parent.mkdir(parents=True, exist_ok=True)

    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            for relative, digest in sorted(checksums.items()):
                handle.write(f"{digest}  {relative}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, session.paths.checksums)
    finally:
        temporary.unlink(missing_ok=True)

    return checksums


def _parse_checksums(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line:
            continue
        try:
            digest, relative = raw_line.split("  ", 1)
        except ValueError as exc:
            raise ExportError(
                f"Invalid checksum line {line_number}"
            ) from exc

        if not _CHECKSUM_RE.fullmatch(digest):
            raise ExportError(
                f"Invalid SHA-256 digest on line {line_number}"
            )

        relative = _safe_archive_name(relative)
        if relative in entries:
            raise ExportError(
                f"Duplicate checksum path: {relative}"
            )
        entries[relative] = digest

    if not entries:
        raise ExportError("Checksum file is empty")

    return entries


def _default_output_path(session: SessionManager) -> Path:
    return (
        session.paths.root.parent
        / f"{session.session_id}.research.zip"
    )


def _ensure_output_outside_session(
    session: SessionManager,
    output: Path,
) -> None:
    root = session.paths.root.resolve()
    resolved = output.resolve()

    try:
        resolved.relative_to(root)
    except ValueError:
        return

    raise ExportError(
        "Research ZIP output must be outside the runtime session directory"
    )


def export_research_zip(
    session: SessionManager,
    output_path: str | os.PathLike[str] | None = None,
    *,
    overwrite: bool = False,
) -> ExportResult:
    validation = validate_session(session)

    if session.status not in TERMINAL_STATUSES:
        raise ExportError(
            "Session must be terminal before export: "
            f"{session.status.value}"
        )

    if (
        session.status == SessionStatus.COMPLETE
        and not validation.valid_for_complete
    ):
        details = "; ".join(
            issue.message
            for issue in validation.issues
            if issue.severity == "error"
        )
        raise ExportError(
            "Complete session failed evidence validation: " + details
        )

    output = (
        Path(output_path).expanduser().resolve()
        if output_path is not None
        else _default_output_path(session).resolve()
    )
    _ensure_output_outside_session(session, output)

    if output.exists() and not overwrite:
        raise ExportError(
            f"Research ZIP already exists: {output}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)

    files = _iter_session_files(
        session.paths.root,
        session.paths.checksums,
    )
    if session.paths.manifest not in files:
        raise ExportError(
            f"Session manifest is missing: {session.paths.manifest}"
        )

    checksums = _write_checksums(session, files)
    archive_files = files + [session.paths.checksums]
    archive_files.sort(
        key=lambda item: _relative_path(session.paths.root, item)
    )

    temporary = output.with_name(output.name + ".tmp")
    temporary.unlink(missing_ok=True)

    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=1,
            allowZip64=True,
        ) as archive:
            for path in archive_files:
                archive.write(
                    path,
                    arcname=_relative_path(session.paths.root, path),
                )

        verification = verify_research_zip(temporary)
        if verification.session_id != session.session_id:
            raise ExportError(
                "ZIP verification returned unexpected session ID"
            )
        if verification.session_status != session.status.value:
            raise ExportError(
                "ZIP verification returned unexpected session status"
            )

        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)

    total_bytes = sum(path.stat().st_size for path in archive_files)

    return ExportResult(
        archive=str(output),
        session_id=session.session_id,
        session_status=session.status.value,
        file_count=len(archive_files),
        total_uncompressed_bytes=total_bytes,
        checksum_entries=len(checksums),
        validation=validation,
    )


def verify_research_zip(
    archive_path: str | os.PathLike[str],
) -> ZipVerification:
    path = Path(archive_path).expanduser().resolve()
    if not path.is_file():
        raise ExportError(f"Research ZIP not found: {path}")

    try:
        archive = zipfile.ZipFile(path, mode="r")
    except zipfile.BadZipFile as exc:
        raise ExportError(f"Invalid Research ZIP: {path}") from exc

    with archive:
        bad_file = archive.testzip()
        if bad_file is not None:
            raise ExportError(
                f"ZIP CRC verification failed: {bad_file}"
            )

        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ExportError("Research ZIP contains duplicate entries")

        safe_names = [_safe_archive_name(name) for name in names]
        if len(safe_names) != len(set(safe_names)):
            raise ExportError(
                "Research ZIP contains ambiguous normalized paths"
            )

        required = {
            "00_manifest/session.json",
            "00_manifest/checksums.sha256",
        }
        missing = sorted(required - set(safe_names))
        if missing:
            raise ExportError(
                "Research ZIP is missing required entries: "
                + ", ".join(missing)
            )

        try:
            checksum_text = archive.read(
                "00_manifest/checksums.sha256"
            ).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ExportError(
                "Checksum file is not valid UTF-8"
            ) from exc
        checksums = _parse_checksums(checksum_text)

        expected_files = (
            set(safe_names)
            - {"00_manifest/checksums.sha256"}
        )
        if set(checksums) != expected_files:
            missing_hashes = sorted(
                expected_files - set(checksums)
            )
            unknown_hashes = sorted(
                set(checksums) - expected_files
            )
            details: list[str] = []
            if missing_hashes:
                details.append(
                    "missing checksum entries: "
                    + ", ".join(missing_hashes)
                )
            if unknown_hashes:
                details.append(
                    "checksums for absent files: "
                    + ", ".join(unknown_hashes)
                )
            raise ExportError(
                "Checksum coverage mismatch: " + "; ".join(details)
            )

        for relative, expected in checksums.items():
            with archive.open(relative, mode="r") as handle:
                actual = _sha256_stream(handle)
            if actual != expected:
                raise ExportError(
                    f"SHA-256 mismatch for ZIP entry: {relative}"
                )

        try:
            manifest = json.loads(
                archive.read(
                    "00_manifest/session.json"
                ).decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExportError(
                "Archived session manifest is invalid JSON"
            ) from exc

        session_id = str(manifest.get("session_id") or "")
        session_status = str(manifest.get("status") or "")
        if not session_id:
            raise ExportError(
                "Archived session manifest has no session_id"
            )
        if session_status not in {
            status.value for status in TERMINAL_STATUSES
        }:
            raise ExportError(
                "Archived session has non-terminal status: "
                f"{session_status!r}"
            )

        return ZipVerification(
            archive=str(path),
            valid=True,
            file_count=len(safe_names),
            checksum_entries=len(checksums),
            session_id=session_id,
            session_status=session_status,
        )
