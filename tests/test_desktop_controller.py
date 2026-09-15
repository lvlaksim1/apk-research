from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6.QtCore")

from mobile_research.desktop.controller import DesktopController


class _Result:
    archive = "recovered.research.zip"

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": "session-1",
            "session_root": "session-root",
            "session_status": "partial",
            "archive": self.archive,
            "validation_issues": 0,
        }


class _Orchestrator:
    def __init__(self) -> None:
        self.session = SimpleNamespace(
            status=SimpleNamespace(value="active"),
        )
        self.stop_calls = 0

    def stop_and_export(self) -> _Result:
        self.stop_calls += 1
        return _Result()


def test_salvage_active_research_exports_and_emits_result(
    monkeypatch,
) -> None:
    controller = DesktopController()
    orchestrator = _Orchestrator()
    finished: list[dict] = []
    logs: list[str] = []

    controller.researchFinished.connect(
        finished.append
    )
    controller.log.connect(logs.append)

    monkeypatch.setattr(
        controller,
        "_research_payload",
        lambda result, recovered_error=None: {
            **result.to_dict(),
            "recovered_after_error": recovered_error,
        },
    )

    recovered = controller._salvage_research(
        orchestrator,
        "collector failure",
    )

    assert recovered is True
    assert orchestrator.stop_calls == 1
    assert finished == [
        {
            "session_id": "session-1",
            "session_root": "session-root",
            "session_status": "partial",
            "archive": "recovered.research.zip",
            "validation_issues": 0,
            "recovered_after_error": "collector failure",
        }
    ]
    assert "Аварийное завершение сохранено" in logs[-1]


def test_existing_failed_archive_is_reused_without_second_export(
    tmp_path,
) -> None:
    controller = DesktopController()
    finished: list[dict] = []
    controller.researchFinished.connect(
        finished.append
    )

    session_root = tmp_path / "session"
    orchestrator = SimpleNamespace(
        session=SimpleNamespace(
            status=SimpleNamespace(value="failed"),
            session_id="failed-session",
            paths=SimpleNamespace(root=session_root),
        )
    )

    recovered = controller._salvage_research(
        orchestrator,
        "start failure",
        existing_archive=str(
            tmp_path / "failed.research.zip"
        ),
    )

    assert recovered is True
    assert finished[0]["session_status"] == "failed"
    assert finished[0]["recovered_after_error"] == "start failure"
    assert finished[0]["archive"].endswith(
        "failed.research.zip"
    )


def test_display_ready_callback_starts_boot_frames_without_gating(
    monkeypatch,
) -> None:
    controller = DesktopController()
    calls: list[bool] = []

    monkeypatch.setattr(
        controller,
        "_start_screen_stream",
        lambda *, wait_for_first_frame=False: calls.append(
            wait_for_first_frame
        ),
    )

    controller._display_ready_callback()

    assert calls == [False]
    controller.close()
