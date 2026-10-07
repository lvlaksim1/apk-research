from __future__ import annotations

from apk_research.desktop.evidence_v024_model import build_evidence_model_v024


def _flow(flow_id: str, remote_ip: str, action_id: str) -> dict:
    return {
        "flow_id": flow_id,
        "protocol": "tcp",
        "local_ip": "10.0.2.15",
        "local_port": 40000 if flow_id.endswith("1") else 40001,
        "remote_ip": remote_ip,
        "remote_port": 443,
        "first_target_utc": "2026-01-01T00:00:01Z",
        "last_target_utc": "2026-01-01T00:00:02Z",
        "correlated_action_ids": [action_id],
        "owner": {
            "package": "com.example.app",
            "uid": 10123,
            "processes": ["com.example.app"],
            "pids": [2222],
            "inode": 999,
            "confidence": "EXACT",
            "evidence": "target-process+socket-inode+5-tuple",
        },
    }


def _action(action_id: str, flow_id: str) -> dict:
    return {
        "action_id": action_id,
        "action": "tap",
        "correlation": {
            "type": "temporal-only",
            "causal_claim": False,
            "network": {"flow_ids": [flow_id]},
        },
    }


def test_reverse_process_socket_index_collects_all_related_flows() -> None:
    model = build_evidence_model_v024(
        [
            _flow("flow-1", "203.0.113.1", "action-1"),
            _flow("flow-2", "203.0.113.2", "action-2"),
        ],
        [
            _action("action-1", "flow-1"),
            _action("action-2", "flow-2"),
        ],
        package="com.example.app",
    )

    assert model["process_count"] == 1
    process = model["processes"][0]
    assert process["inode"] == 999
    assert process["pids"] == [2222]
    assert process["confidence"] == "EXACT"
    assert process["flow_ids"] == ["flow-1", "flow-2"]
    assert process["relation_type"] == "socket-attribution"
    assert process["causal_claim"] is False


def test_v024_relation_policy_keeps_causal_upgrade_disabled() -> None:
    model = build_evidence_model_v024(
        [_flow("flow-1", "203.0.113.1", "action-1")],
        [_action("action-1", "flow-1")],
    )
    assert model["relation_policy"]["action_flow"] == "temporal-only"
    assert model["relation_policy"]["causal_upgrade"] is False
