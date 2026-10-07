from __future__ import annotations

from apk_research.desktop.screen_evidence import build_screen_evidence_index
from apk_research.desktop.unified_session_model import (
    build_unified_session_model,
    rows_near_target,
)


def _screen_index() -> dict:
    return build_screen_evidence_index(
        {
            "status": "completed",
            "first_pts_us": 2_000_000,
            "target_started_utc": "2026-01-01T00:00:01Z",
        },
        {
            "completed_chunks": [
                {
                    "index": 1,
                    "local_video": "01_raw/screen/screen-0001.mp4",
                    "frame_timing": {
                        "first_frame_utc": "2026-01-01T00:00:01Z",
                        "last_frame_utc": "2026-01-01T00:00:05Z",
                        "frame_count": 100,
                        "realtime_to_elapsed_offset_ns": 1_767_225_600_000_000_000,
                    },
                }
            ]
        },
        [
            {
                "sequence": 1,
                "pts_us": 2_000_000,
                "size": 100,
                "raw_offset": 0,
                "codec_config": False,
                "key_frame": True,
                "end_of_stream": False,
            },
            {
                "sequence": 2,
                "pts_us": 3_000_000,
                "size": 50,
                "raw_offset": 100,
                "codec_config": False,
                "key_frame": False,
                "end_of_stream": False,
            },
        ],
    )


def _flow() -> dict:
    return {
        "flow_id": "flow-1",
        "protocol": "tcp",
        "packet_count": 8,
        "remote_ip": "203.0.113.10",
        "remote_port": 443,
        "owner": {
            "package": "com.example.app",
            "processes": ["com.example.app"],
            "pids": [1234],
            "inode": 777,
            "confidence": "EXACT",
        },
    }


def _timeline() -> dict:
    return {
        "user_actions": [
            {
                "action_id": "action-1",
                "action": "tap",
                "correlation": {
                    "type": "temporal-only",
                    "causal_claim": False,
                    "network": {"flow_ids": ["flow-1"]},
                },
            }
        ],
        "events": [
            {
                "kind": "user_action",
                "name": "tap",
                "action_id": "action-1",
                "target_utc": "2026-01-01T00:00:02Z",
            },
            {
                "kind": "network_flow",
                "name": "tcp flow",
                "flow_id": "flow-1",
                "target_utc": "2026-01-01T00:00:02.500000Z",
            },
        ],
    }


def test_unified_model_preserves_temporal_relation_and_screen_locator() -> None:
    model = build_unified_session_model(
        timeline=_timeline(),
        flows=[_flow()],
        screen_index=_screen_index(),
        package="com.example.app",
    )

    assert model["row_count"] == 2
    action = model["rows"][0]
    assert action["action_id"] == "action-1"
    assert action["flow_ids"] == ["flow-1"]
    assert action["packet_count"] == 8
    assert action["relation_type"] == "temporal-only"
    assert action["causal_claim"] is False
    assert action["screen"]["continuous"]["sequence"] == 1
    assert "inode=777" in action["owners"][0]


def test_network_row_is_direct_observation_not_causal_claim() -> None:
    model = build_unified_session_model(
        timeline=_timeline(),
        flows=[_flow()],
        screen_index=_screen_index(),
    )
    network = model["rows"][1]
    assert network["flow_ids"] == ["flow-1"]
    assert network["relation_type"] == "observed-normalized-flow"
    assert network["relation_strength"] == "direct-observation"
    assert network["causal_claim"] is False


def test_rows_near_target_returns_time_bounded_navigation() -> None:
    model = build_unified_session_model(
        timeline=_timeline(),
        flows=[_flow()],
        screen_index=_screen_index(),
    )
    nearby = rows_near_target(
        model,
        "2026-01-01T00:00:02.250000Z",
        radius_seconds=0.4,
    )
    assert len(nearby) == 2
    assert {row["kind"] for row in nearby} == {"user_action", "network_flow"}
