from __future__ import annotations

import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mobile_research.export import (
    ExportError,
    export_research_zip,
    validate_session,
    verify_research_zip,
)
from mobile_research.session import SessionManager, SessionStatus


class FixedClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 13, 19, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def create_terminal_session(
    tmp_path: Path,
    *,
    partial: bool = False,
) -> SessionManager:
    manager = SessionManager.create(
        tmp_path,
        target={"serial": "emulator-5554", "kind": "emulator"},
        package={"name": "com.example.app"},
        clock=FixedClock(),
        session_id_factory=lambda: "export-session",
    )

    for name in (
        "device_metadata",
        "logcat",
        "screen_recording",
        "raw_network",
    ):
        manager.register_collector(
            name,
            required=True,
            backend="test",
        )

    files = {
        "01_raw/device/getprop.txt": b"props\n",
        "01_raw/device/package.txt": b"package\n",
        "01_raw/device/package-paths.txt": b"paths\n",
        "01_raw/device/system.txt": b"system\n",
        "01_raw/device/clock.txt": b"clock\n",
        "01_raw/logcat/logcat.txt": b"logcat\n",
        "01_raw/logcat/logcat.stderr.txt": b"diagnostic\n",
        "01_raw/screen/screen-0001.mp4": b"mp4-data",
        "01_raw/network/traffic.pcap": b"pcap-data-for-export",
        "02_normalized/target.json": b"{}\n",
    }

    source_for = {
        "01_raw/device/getprop.txt": "device_metadata",
        "01_raw/device/package.txt": "device_metadata",
        "01_raw/device/package-paths.txt": "device_metadata",
        "01_raw/device/system.txt": "device_metadata",
        "01_raw/device/clock.txt": "device_metadata",
        "01_raw/logcat/logcat.txt": "logcat",
        "01_raw/logcat/logcat.stderr.txt": "logcat",
        "01_raw/screen/screen-0001.mp4": "screen_recording",
        "01_raw/network/traffic.pcap": "raw_network",
        "02_normalized/target.json": "device_metadata",
    }

    for relative, data in files.items():
        _write(manager.paths.root / relative, data)
        manager.register_artifact(
            kind="test",
            relative_path=relative,
            source=source_for[relative],
            raw=relative.startswith("01_raw/"),
        )

    for name in (
        "device_metadata",
        "logcat",
        "screen_recording",
        "raw_network",
    ):
        manager.update_collector(name, "completed")

    manager.begin_preflight()
    manager.mark_ready()
    manager.begin_start()
    manager.mark_active()

    if partial:
        manager.record_error(
            "collector:test",
            "synthetic degraded evidence",
        )

    manager.begin_stop()
    final = manager.finish()
    assert final == (
        SessionStatus.PARTIAL if partial else SessionStatus.COMPLETE
    )
    return manager


def test_complete_session_exports_and_verifies(tmp_path: Path) -> None:
    session = create_terminal_session(tmp_path)
    output = tmp_path / "result.research.zip"

    result = export_research_zip(session, output)

    assert result.session_status == "complete"
    assert result.validation.valid_for_complete is True
    assert result.checksum_entries == result.file_count - 1
    assert output.is_file()

    verification = verify_research_zip(output)
    assert verification.valid is True
    assert verification.session_id == "export-session"
    assert verification.session_status == "complete"

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "00_manifest/session.json" in names
        assert "00_manifest/checksums.sha256" in names
        assert "01_raw/network/traffic.pcap" in names
        assert "01_raw/screen/screen-0001.mp4" in names


def test_complete_session_missing_required_evidence_is_rejected(
    tmp_path: Path,
) -> None:
    session = create_terminal_session(tmp_path)
    (session.paths.raw_logcat / "logcat.txt").unlink()

    validation = validate_session(session)
    assert validation.valid_for_complete is False

    with pytest.raises(
        ExportError,
        match="failed evidence validation",
    ):
        export_research_zip(
            session,
            tmp_path / "invalid.zip",
        )


def test_partial_session_can_export_with_warnings(
    tmp_path: Path,
) -> None:
    session = create_terminal_session(tmp_path, partial=True)
    (session.paths.raw_logcat / "logcat.txt").unlink()

    result = export_research_zip(
        session,
        tmp_path / "partial.zip",
    )

    assert result.session_status == "partial"
    assert result.validation.issues
    assert all(
        issue.severity == "warning"
        for issue in result.validation.issues
    )
    assert verify_research_zip(result.archive).valid is True


def test_nonterminal_session_cannot_export(tmp_path: Path) -> None:
    session = SessionManager.create(
        tmp_path,
        target={"serial": "emulator-5554"},
        package={"name": "com.example.app"},
        clock=FixedClock(),
        session_id_factory=lambda: "active-session",
    )

    with pytest.raises(ExportError, match="terminal"):
        export_research_zip(
            session,
            tmp_path / "active.zip",
        )


def test_output_cannot_be_inside_session_directory(
    tmp_path: Path,
) -> None:
    session = create_terminal_session(tmp_path)

    with pytest.raises(ExportError, match="outside"):
        export_research_zip(
            session,
            session.paths.root / "result.zip",
        )


def test_existing_output_requires_overwrite(tmp_path: Path) -> None:
    session = create_terminal_session(tmp_path)
    output = tmp_path / "result.zip"
    output.write_bytes(b"existing")

    with pytest.raises(ExportError, match="already exists"):
        export_research_zip(session, output)

    result = export_research_zip(
        session,
        output,
        overwrite=True,
    )
    assert verify_research_zip(result.archive).valid is True


def test_zip_tampering_is_detected(tmp_path: Path) -> None:
    session = create_terminal_session(tmp_path)
    original = tmp_path / "original.zip"
    export_research_zip(session, original)

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(original, "r") as source:
        with zipfile.ZipFile(tampered, "w") as destination:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == "01_raw/logcat/logcat.txt":
                    data = b"tampered\n"
                destination.writestr(info, data)

    with pytest.raises(ExportError, match="SHA-256 mismatch"):
        verify_research_zip(tampered)


def test_unregistered_partial_file_is_preserved_and_hashed(
    tmp_path: Path,
) -> None:
    session = create_terminal_session(tmp_path, partial=True)
    orphan = session.paths.raw_network / "partial-tail.bin"
    orphan.write_bytes(b"partial evidence")

    output = tmp_path / "partial-extra.zip"
    result = export_research_zip(session, output)

    with zipfile.ZipFile(output) as archive:
        assert "01_raw/network/partial-tail.bin" in archive.namelist()
        checksums = archive.read(
            "00_manifest/checksums.sha256"
        ).decode("utf-8")
        assert "01_raw/network/partial-tail.bin" in checksums

    assert result.validation.session_status == "partial"
