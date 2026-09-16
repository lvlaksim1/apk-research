from __future__ import annotations

from apk_research.desktop.evidence_view_model import (
    build_evidence_groups,
    flow_process_socket_text,
    flow_raw_evidence_text,
    format_evidence_chain,
    packet_ranges_text,
)


def _flow(
    flow_id: str,
    *,
    host: str = "api.example.test",
    action_ids: list[str] | None = None,
) -> dict:
    return {
        "flow_id": flow_id,
        "protocol": "tcp",
        "local_ip": "10.0.2.15",
        "local_port": 41000,
        "remote_ip": "203.0.113.10",
        "remote_port": 443,
        "first_target_utc": "2026-09-17T00:00:01Z",
        "last_target_utc": "2026-09-17T00:00:02Z",
        "tls_sni": [host],
        "dns_queries": [],
        "correlated_action_ids": action_ids or [],
        "owner": {
            "package": "com.example",
            "confidence": "EXACT",
            "evidence": "unique-package-uid+socket-inode+5-tuple",
            "processes": ["com.example"],
            "pids": [1234],
            "inode": 5678,
        },
        "raw_evidence": {
            "pcap_artifact": "01_raw/network/traffic.pcap",
            "pcap_packet_ranges": [
                [10, 12],
                [15, 15],
            ],
            "first_pcap_record_offset": 240,
            "last_pcap_record_offset": 1200,
            "socket_snapshot_artifact": (
                "01_raw/network/socket-snapshots.txt"
            ),
            "socket_inode": 5678,
            "socket_first_observed_utc": (
                "2026-09-17T00:00:00.900Z"
            ),
            "socket_last_observed_utc": (
                "2026-09-17T00:00:02.100Z"
            ),
        },
    }


def test_packet_ranges_text_compacts_ranges() -> None:
    assert packet_ranges_text(
        [[1, 1], [3, 7], [9, 9]]
    ) == "1, 3-7, 9"


def test_evidence_groups_keep_action_host_flow_chain() -> None:
    actions = [
        {
            "action_id": "action-000001",
            "action": "tap",
            "host_utc": "2026-09-17T00:00:00Z",
        }
    ]
    linked = _flow(
        "flow-000001",
        action_ids=["action-000001"],
    )
    unlinked = _flow(
        "flow-000002",
        host="background.example.test",
    )

    groups = build_evidence_groups(
        [linked, unlinked],
        actions,
    )

    assert len(groups) == 2
    assert groups[0]["action_id"] == "action-000001"
    assert groups[0]["hosts"][0]["host"] == (
        "api.example.test"
    )
    assert groups[0]["hosts"][0]["flows"][0][
        "flow_id"
    ] == "flow-000001"
    assert groups[1]["action_id"] == ""
    assert groups[1]["flow_count"] == 1


def test_raw_evidence_is_human_readable() -> None:
    flow = _flow(
        "flow-000001",
        action_ids=["action-000001"],
    )

    raw = flow_raw_evidence_text(flow)
    process = flow_process_socket_text(flow)
    chain = format_evidence_chain(
        {
            "action_id": "action-000001",
            "action": "tap",
        },
        "api.example.test",
        flow,
    )

    assert "Packets: 10-12, 15" in raw
    assert "traffic.pcap" in raw
    assert "socket-snapshots.txt" in raw
    assert "inode 5678" in process
    assert "Action: tap • action-000001" in chain
    assert "temporal-only" in chain
