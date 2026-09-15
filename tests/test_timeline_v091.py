from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import mobile_research.orchestrator as orchestrator_module
from mobile_research.orchestrator import ResearchOrchestrator
from mobile_research.session import SessionManager
from mobile_research.targets import AdbClient
from mobile_research.timeline_engine import build_research_timeline


def _active_session(tmp_path: Path) -> SessionManager:
    session = SessionManager.create(
        tmp_path,
        target={"serial": "emulator-5554"},
        package={"name": "com.example.app"},
        session_id_factory=lambda: "v091-session",
    )
    session.begin_preflight()
    session.mark_ready()
    session.begin_start()
    session.mark_active()
    return session


def test_user_actions_are_gated_until_package_launch(
    tmp_path: Path,
) -> None:
    orchestrator = ResearchOrchestrator(
        object(),  # type: ignore[arg-type]
        "emulator-5554",
        "com.example.app",
        runtime_root=tmp_path,
    )
    orchestrator.session = _active_session(tmp_path)
    orchestrator._ensure_user_action_log()

    assert (
        orchestrator.record_user_action(
            "tap",
            details={"x": 1, "y": 2},
        )
        is False
    )

    orchestrator._user_actions_enabled = True
    assert (
        orchestrator.record_user_action(
            "tap",
            details={"x": 1, "y": 2},
        )
        is True
    )

    lines = (
        orchestrator.session.paths.root
        / orchestrator.USER_ACTIONS_ARTIFACT
    ).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_ntp_style_clock_calibration_uses_midpoint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    base = 1_700_000_000_000_000_000
    state = {
        "sample": 0,
        "host": base,
        "mono_calls": 0,
    }

    def fake_time_ns() -> int:
        value = base + state["sample"] * 100_000_000
        state["host"] = value
        return value

    def fake_monotonic_ns() -> int:
        pair = state["mono_calls"] // 2
        second = state["mono_calls"] % 2
        state["mono_calls"] += 1
        value = pair * 10_000_000 + second * 2_000_000
        if second:
            state["sample"] += 1
        return value

    class FakeAdb:
        def get_unix_time_ns(self, serial: str) -> int:
            assert serial == "emulator-5554"
            return (
                state["host"]
                + 1_000_000
                + 50_000_000
            )

    monkeypatch.setattr(
        orchestrator_module.time,
        "time_ns",
        fake_time_ns,
    )
    monkeypatch.setattr(
        orchestrator_module.time,
        "monotonic_ns",
        fake_monotonic_ns,
    )

    orchestrator = ResearchOrchestrator(
        FakeAdb(),  # type: ignore[arg-type]
        "emulator-5554",
        "com.example.app",
        runtime_root=tmp_path,
    )
    orchestrator.session = _active_session(tmp_path)
    orchestrator._ensure_event_log()
    orchestrator._calibrate_clock()

    calibration = json.loads(
        (
            orchestrator.session.paths.root
            / orchestrator.CLOCK_CALIBRATION_ARTIFACT
        ).read_text(encoding="utf-8")
    )
    assert calibration["method"] == "adb-ntp-midpoint"
    assert calibration["selected_count"] == 5
    assert calibration[
        "target_minus_host_seconds"
    ] == pytest.approx(0.05)
    assert calibration[
        "estimated_uncertainty_ns"
    ] == 1_000_000


def test_refined_timeline_uses_calibration_and_exclusive_windows(
    tmp_path: Path,
) -> None:
    session = SessionManager.create(
        tmp_path,
        target={"serial": "emulator-5554"},
        package={"name": "com.example.app"},
        session_id_factory=lambda: "timeline-v091",
    )
    root = session.paths.root

    (
        root
        / "02_normalized"
        / "session-events.jsonl"
    ).write_text(
        json.dumps(
            {
                "event": "package_launched",
                "host_utc": "2026-09-15T12:00:01Z",
                "target_utc": "2026-09-15T12:00:01.050Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    actions = [
        {
            "action_id": "action-000001",
            "sequence": 1,
            "action": "tap",
            "host_started_utc": "2026-09-15T12:00:02.000000Z",
            "host_utc": "2026-09-15T12:00:02Z",
            "details": {},
        },
        {
            "action_id": "action-000002",
            "sequence": 2,
            "action": "tap",
            "host_started_utc": "2026-09-15T12:00:02.500000Z",
            "host_utc": "2026-09-15T12:00:02.500Z",
            "details": {},
        },
    ]
    (
        root
        / "02_normalized"
        / "user-actions.jsonl"
    ).write_text(
        "\n".join(
            json.dumps(item)
            for item in actions
        )
        + "\n",
        encoding="utf-8",
    )
    (
        root
        / "02_normalized"
        / "clock-calibration.json"
    ).write_text(
        json.dumps(
            {
                "method": "adb-ntp-midpoint",
                "sample_count": 9,
                "selected_count": 5,
                "target_minus_host_seconds": 0.05,
                "estimated_uncertainty_ns": 2_000_000,
                "samples": [],
            }
        ),
        encoding="utf-8",
    )

    timeline = build_research_timeline(session)

    assert timeline["schema_version"] == "0.2"
    assert (
        timeline["clock_alignment"]["method"]
        == "adb-ntp-midpoint"
    )
    first = timeline["user_actions"][0]["correlation"]
    second = timeline["user_actions"][1]["correlation"]
    assert (
        first["window"]["truncated_by_next_action"]
        is True
    )
    assert first["window"][
        "exclusive_until_next_action"
    ] is True
    assert first["window"][
        "actual_after_seconds"
    ] == pytest.approx(0.499, abs=0.002)
    assert second["window"][
        "actual_after_seconds"
    ] == pytest.approx(2.0)
    assert first["causal_claim"] is False
    assert first["attribution"] == "temporal-only"


def test_adb_nanosecond_clock_parsing() -> None:
    def runner(
        arguments,
        timeout,
    ):
        key = tuple(arguments)
        if key == ("devices", "-l"):
            return subprocess.CompletedProcess(
                arguments,
                0,
                (
                    "List of devices attached\n"
                    "emulator-5554 device model:test transport_id:1\n"
                ),
                "",
            )
        if key == (
            "-s",
            "emulator-5554",
            "shell",
            "date",
            "+%s%N",
        ):
            return subprocess.CompletedProcess(
                arguments,
                0,
                "1700000000123456789\n",
                "",
            )
        raise AssertionError(key)

    client = AdbClient(
        Path("adb"),
        runner=runner,
    )
    assert client.get_unix_time_ns(
        "emulator-5554"
    ) == 1_700_000_000_123_456_789
