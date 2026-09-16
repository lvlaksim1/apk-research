from __future__ import annotations

from apk_research.desktop.network_view_model import (
    action_label,
    build_action_index,
    flow_matches,
    format_flow_details,
    format_host_details,
    group_flows_by_host,
    is_dns_resolution_flow,
    summarize_flows,
    summarize_host_flows,
)


def _flow(
    *,
    flow_id: str,
    host: str,
    confidence: str = "EXACT",
    protocol: str = "tcp",
    outbound: int = 100,
    inbound: int = 200,
    action_ids: list[str] | None = None,
) -> dict:
    return {
        "flow_id": flow_id,
        "protocol": protocol,
        "local_ip": "10.0.2.15",
        "local_port": 40000,
        "remote_ip": "93.184.216.34",
        "remote_port": 443,
        "first_target_utc": "2026-09-16T21:17:01Z",
        "last_target_utc": "2026-09-16T21:17:02Z",
        "duration_seconds": 1.0,
        "packet_count": 3,
        "outbound_packet_count": 1,
        "inbound_packet_count": 2,
        "outbound_bytes": outbound,
        "inbound_bytes": inbound,
        "tls_sni": [host],
        "dns_queries": [],
        "correlated_action_ids": action_ids or [],
        "packet_confidence_counts": {
            "EXACT": 2 if confidence == "EXACT" else 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "UNKNOWN": 1 if confidence == "UNKNOWN" else 0,
        },
        "owner": {
            "package": "com.evrasia",
            "confidence": confidence,
            "evidence": "test-evidence",
            "processes": ["com.evrasia"],
            "pids": [1234],
            "inode": 55,
            "ambiguity": [],
        },
    }


def test_group_flows_by_host_aggregates_connections() -> None:
    first = _flow(
        flow_id="flow-000001",
        host="api.example.test",
        outbound=100,
        inbound=200,
        action_ids=["action-000001"],
    )
    second = _flow(
        flow_id="flow-000002",
        host="api.example.test",
        protocol="udp",
        outbound=50,
        inbound=25,
        action_ids=["action-000002"],
    )

    groups = group_flows_by_host(
        [first, second]
    )

    assert len(groups) == 1
    group = groups[0]
    assert group["host"] == "api.example.test"
    assert group["flow_count"] == 2
    assert group["outbound_bytes"] == 150
    assert group["inbound_bytes"] == 225
    assert group["protocols"] == ["TCP", "UDP"]
    assert group["action_ids"] == [
        "action-000001",
        "action-000002",
    ]


def test_flow_filter_uses_owner_protocol_and_host() -> None:
    flow = _flow(
        flow_id="flow-000001",
        host="evrasia.spb.ru",
    )

    assert flow_matches(
        flow,
        owner_filter="app",
        protocol_filter="tcp",
        query="evrasia.spb.ru",
        package="com.evrasia",
    )
    assert not flow_matches(
        flow,
        owner_filter="unknown",
        protocol_filter="all",
        query="",
        package="com.evrasia",
    )
    assert not flow_matches(
        flow,
        owner_filter="all",
        protocol_filter="udp",
        query="",
        package="com.evrasia",
    )


def test_summary_marks_unknown_owner_mix() -> None:
    known = _flow(
        flow_id="flow-000001",
        host="same.test",
    )
    unknown = _flow(
        flow_id="flow-000002",
        host="same.test",
        confidence="UNKNOWN",
    )

    summary = summarize_flows(
        [known, unknown]
    )

    assert (
        summary["owner_text"]
        == "com.evrasia + Unknown"
    )
    assert summary["best_confidence"] == "EXACT"


def test_details_are_human_readable_and_include_timeline() -> None:
    flow = _flow(
        flow_id="flow-000001",
        host="evrasia.spb.ru",
        action_ids=["action-000001"],
    )
    actions = [
        {
            "action_id": "action-000001",
            "action": "tap",
            "host_utc": "2026-09-16T21:17:03Z",
            "correlation": {
                "target_started_utc_estimate": (
                    "2026-09-16T21:17:03.100Z"
                )
            },
        }
    ]
    action_index = build_action_index(actions)

    label = action_label(
        "action-000001",
        action_index,
    )
    details = format_flow_details(
        flow,
        action_index,
    )

    assert "tap" in label
    assert "Хост: evrasia.spb.ru" in details
    assert "Flow: flow-000001" in details
    assert "Package: com.evrasia" in details
    assert "Связанных действий: 1" in details
    assert "action-000001" in details


def test_host_summary_separates_dns_resolver_from_service() -> None:
    service = _flow(
        flow_id="flow-service",
        host="evrasia.spb.ru",
    )
    service["remote_ip"] = "217.197.238.66"
    service["remote_port"] = 443
    dns = _flow(
        flow_id="flow-dns",
        host="evrasia.spb.ru",
        confidence="UNKNOWN",
        protocol="udp",
    )
    dns["remote_ip"] = "10.0.2.3"
    dns["remote_port"] = 53
    dns["tls_sni"] = []
    dns["dns_queries"] = ["evrasia.spb.ru"]

    assert is_dns_resolution_flow(dns)
    summary = summarize_host_flows(
        [dns, service]
    )
    assert summary["flow_count"] == 2
    assert summary["service_flow_count"] == 1
    assert summary["resolution_flow_count"] == 1
    assert summary["service_remote_ips"] == [
        "217.197.238.66"
    ]
    assert summary["resolver_ips"] == ["10.0.2.3"]
    assert summary["service_ports"] == ["443"]
    assert summary["owner_text"] == "com.evrasia"
    assert summary["confidence_counts"] == {"EXACT": 1}


def test_host_details_explain_resolution_only_evidence() -> None:
    dns = _flow(
        flow_id="flow-dns",
        host="time.google.com",
        confidence="UNKNOWN",
        protocol="udp",
    )
    dns["remote_ip"] = "10.0.2.3"
    dns["remote_port"] = 53
    dns["tls_sni"] = []
    dns["dns_queries"] = ["time.google.com"]

    details = format_host_details(
        "time.google.com",
        [dns],
        {},
    )
    assert "service 0, DNS 1" in details
    assert "Resolver IP: 10.0.2.3" in details
    assert "только DNS-разрешение" in details
