from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from apk_research.session import (
    InvalidArtifactPath,
    InvalidSessionTransition,
    SessionManager,
    SessionStatus,
)


class TestClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def create_manager(tmp_path: Path) -> SessionManager:
    return SessionManager.create(
        tmp_path,
        target={
            "serial": "emulator-5554",
            "kind": "emulator",
            "android_release": "15",
        },
        package={"name": "com.example.app"},
        clock=TestClock(),
        session_id_factory=lambda: "test-session",
    )


def advance_to_active(manager: SessionManager) -> None:
    manager.begin_preflight()
    manager.mark_ready()
    manager.begin_start()
    manager.mark_active()


def test_create_session_writes_required_layout_and_manifest(
    tmp_path: Path,
) -> None:
    manager = create_manager(tmp_path)

    assert manager.status == SessionStatus.CREATED
    assert manager.paths.manifest.is_file()
    assert manager.paths.raw_logcat.is_dir()
    assert manager.paths.raw_screen.is_dir()
    assert manager.paths.raw_network.is_dir()
    assert manager.paths.raw_device.is_dir()
    assert manager.paths.normalized_dir.is_dir()

    manifest = json.loads(manager.paths.manifest.read_text(encoding="utf-8"))
    assert manifest["session_id"] == "test-session"
    assert manifest["status"] == "created"
    assert manifest["target"]["serial"] == "emulator-5554"
    assert manifest["package"]["name"] == "com.example.app"
    assert manifest["degraded"] is False


def test_happy_path_finishes_complete(tmp_path: Path) -> None:
    manager = create_manager(tmp_path)

    advance_to_active(manager)
    manager.begin_stop()
    result = manager.finish()

    assert result == SessionStatus.COMPLETE
    assert manager.status == SessionStatus.COMPLETE
    assert manager.manifest["timestamps"]["started"] is not None
    assert manager.manifest["timestamps"]["stopped"] is not None

    transitions = [
        item["to"] for item in manager.manifest["state_history"]
    ]
    assert transitions == [
        "created",
        "preflight",
        "ready",
        "starting",
        "active",
        "stopping",
        "complete",
    ]


def test_nonfatal_error_during_active_finishes_partial(
    tmp_path: Path,
) -> None:
    manager = create_manager(tmp_path)
    advance_to_active(manager)

    manager.record_error(
        "collector:screen",
        "screen recorder stopped unexpectedly",
    )

    assert manager.status == SessionStatus.ACTIVE
    assert manager.degraded is True

    manager.begin_stop()
    result = manager.finish()

    assert result == SessionStatus.PARTIAL
    assert manager.status == SessionStatus.PARTIAL
    assert manager.manifest["errors"][0]["fatal"] is False


def test_fatal_error_moves_nonterminal_session_to_failed(
    tmp_path: Path,
) -> None:
    manager = create_manager(tmp_path)
    manager.begin_preflight()

    manager.fail("preflight", "raw network capture unavailable")

    assert manager.status == SessionStatus.FAILED
    assert manager.manifest["errors"][-1]["fatal"] is True
    assert manager.manifest["timestamps"]["stopped"] is not None


def test_invalid_transition_is_rejected(tmp_path: Path) -> None:
    manager = create_manager(tmp_path)

    with pytest.raises(InvalidSessionTransition):
        manager.mark_active()

    assert manager.status == SessionStatus.CREATED


def test_session_can_be_reloaded_from_disk(tmp_path: Path) -> None:
    manager = create_manager(tmp_path)
    manager.begin_preflight()
    manager.mark_ready()

    loaded = SessionManager.load(manager.paths.root, clock=TestClock())

    assert loaded.session_id == "test-session"
    assert loaded.status == SessionStatus.READY
    assert loaded.manifest == manager.manifest


def test_collector_and_artifact_metadata_are_persisted(
    tmp_path: Path,
) -> None:
    manager = create_manager(tmp_path)

    manager.register_collector(
        "logcat",
        required=True,
        backend="adb-logcat",
    )
    manager.update_collector(
        "logcat",
        "running",
        artifact_path="01_raw/logcat/logcat.txt",
    )
    manager.register_artifact(
        kind="logcat",
        relative_path="01_raw/logcat/logcat.txt",
        source="logcat",
        raw=True,
    )

    reloaded = SessionManager.load(manager.paths.root)

    collector = reloaded.manifest["collectors"]["logcat"]
    assert collector["status"] == "running"
    assert collector["artifact_paths"] == [
        "01_raw/logcat/logcat.txt"
    ]
    assert reloaded.manifest["artifacts"][0]["raw"] is True


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../outside.txt",
        "01_raw/../../outside.txt",
        "/absolute/file.txt",
        "C:\\outside\\file.txt",
    ],
)
def test_artifact_path_cannot_escape_session(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    manager = create_manager(tmp_path)

    with pytest.raises(InvalidArtifactPath):
        manager.register_artifact(
            kind="test",
            relative_path=unsafe_path,
            source="test",
        )


def test_duplicate_session_directory_is_rejected(tmp_path: Path) -> None:
    create_manager(tmp_path)

    with pytest.raises(Exception, match="already exists"):
        create_manager(tmp_path)
