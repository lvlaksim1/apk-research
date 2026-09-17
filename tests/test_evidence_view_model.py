from __future__ import annotations

from apk_research.desktop.evidence_view_model import (
    RAW_PCAP_ARTIFACT,
    RAW_SOCKET_ARTIFACT,
    build_evidence_model,
    format_evidence_details,
    node_search_text,
)


def _flow() -> dict:
    return {
        "flow_id": "flow-000001",
        "protocol": "tcp",
        "local_ip": "10.0.2.15",
        "local_port": 40000,
        "remote_ip": "93.184.216.34",
        "remote_port": 443,
        "first_target_utc": "2026-09-17T00:00:01Z",
        "last_target_utc": "2026-09-17T00:00:02Z",
        "tls_sni": ["api.example.test"],
        "dns_queries": [],
        "correlated_action_ids": ["action-000001"],
        "owner": {
            "package": "com.example.app",
            "uid": 10234,
            "confidence": "EXACT",
            "evidence": "target-process+socket-inode+5-tuple",
            "processes": ["com.example.app"],
            "pids": [4321],
            "inode": 55555,
        },
    }


def _action() -> dict:
    return {
        "action_id": "action-000001",
        "action": "tap",
        "host_utc": "2026-09-17T00:00:00Z",
        "correlation": {
            "type": "temporal-only",
            "causal_claim": False,
            "network": {
                "flow_ids": ["flow-000001"],
            },
        },
    }


def test_evidence_model_builds_forward_and_reverse_paths() -> None:
    model = build_evidence_model(
        [_flow()],
        [_action()],
        package="com.example.app",
    )

    assert model["action_count"] == 1
    assert model["host_count"] == 1
    assert model["flow_count"] == 1

    action = model["actions"][0]
    assert action["action_id"] == "action-000001"
    assert action["causal_claim"] is False
    assert action["correlation_type"] == "temporal-only"
    assert action["hosts"][0]["host"] == "api.example.test"
    assert (
        action["hosts"][0]["flow_nodes"][0]["flow_id"]
        == "flow-000001"
    )

    host = model["hosts"][0]
    assert host["host"] == "api.example.test"
    assert host["action_ids"] == ["action-000001"]
    assert host["flow_nodes"][0]["action_ids"] == [
        "action-000001"
    ]


def test_flow_node_keeps_raw_pcap_and_socket_locators() -> None:
    model = build_evidence_model(
        [_flow()],
        [_action()],
        package="com.example.app",
    )
    node = model["hosts"][0]["flow_nodes"][0]

    assert node["raw_locator"]["artifact"] == RAW_PCAP_ARTIFACT
    assert node["raw_locator"]["flow_id"] == "flow-000001"
    assert node["raw_locator"]["remote_port"] == 443

    process = node["process_nodes"][0]
    assert process["inode"] == 55555
    assert process["pids"] == [4321]
    assert process["confidence"] == "EXACT"
    assert process["raw_locator"]["artifact"] == RAW_SOCKET_ARTIFACT
    assert process["raw_locator"]["inode"] == 55555


def test_details_do_not_turn_temporal_correlation_into_causality() -> None:
    model = build_evidence_model(
        [_flow()],
        [_action()],
    )
    action = model["actions"][0]
    details = format_evidence_details(action)

    assert "Correlation: temporal-only" in details
    assert "Causal claim: no" in details
    assert "не доказанной причинностью" in details


def test_flow_details_expose_reproducible_raw_locator() -> None:
    model = build_evidence_model(
        [_flow()],
        [_action()],
    )
    flow = model["hosts"][0]["flow_nodes"][0]
    details = format_evidence_details(flow)

    assert "Raw PCAP locator" in details
    assert RAW_PCAP_ARTIFACT in details
    assert "flow-000001" in details
    assert "10.0.2.15:40000" in details
    assert "93.184.216.34:443" in details


def test_search_text_spans_host_flow_process_and_protocol() -> None:
    model = build_evidence_model(
        [_flow()],
        [_action()],
    )
    flow = model["hosts"][0]["flow_nodes"][0]
    process = flow["process_nodes"][0]

    flow_text = node_search_text(flow)
    process_text = node_search_text(process)

    assert "api.example.test" in flow_text
    assert "93.184.216.34" in flow_text
    assert "tcp" in flow_text
    assert "action-000001" in flow_text
    assert "com.example.app" in process_text
    assert "4321" in process_text
    assert "55555" not in process_text
