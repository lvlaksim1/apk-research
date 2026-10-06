from __future__ import annotations

import io
import struct

from apk_research.desktop.packet_inspector import (
    RAW_PCAP_ARTIFACT,
    correlate_packets_with_timeline,
    flow_connection_key,
    format_packet_details,
    inspect_pcap_flow,
    packet_action_label,
    packet_search_text,
    packet_transport_label,
)


def _ipv4_udp(
    src: bytes,
    dst: bytes,
    src_port: int,
    dst_port: int,
    payload: bytes,
) -> bytes:
    udp_length = 8 + len(payload)
    udp = struct.pack(
        "!HHHH",
        src_port,
        dst_port,
        udp_length,
        0,
    ) + payload
    total_length = 20 + len(udp)
    ip = (
        bytes([0x45, 0])
        + struct.pack("!H", total_length)
        + b"\x00\x00\x00\x00"
        + bytes([64, 17])
        + b"\x00\x00"
        + src
        + dst
    )
    ethernet = (
        b"\x00\x11\x22\x33\x44\x55"
        + b"\x66\x77\x88\x99\xaa\xbb"
        + b"\x08\x00"
    )
    return ethernet + ip + udp


def _ipv4_tcp(
    src: bytes,
    dst: bytes,
    src_port: int,
    dst_port: int,
    *,
    sequence: int,
    acknowledgment: int,
    flags: int,
    payload: bytes = b"",
) -> bytes:
    tcp = struct.pack(
        "!HHIIBBHHH",
        src_port,
        dst_port,
        sequence,
        acknowledgment,
        0x50,
        flags,
        64240,
        0,
        0,
    ) + payload
    total_length = 20 + len(tcp)
    ip = (
        bytes([0x45, 0])
        + struct.pack("!H", total_length)
        + b"\x00\x00\x00\x00"
        + bytes([64, 6])
        + b"\x00\x00"
        + src
        + dst
    )
    ethernet = (
        b"\x00\x11\x22\x33\x44\x55"
        + b"\x66\x77\x88\x99\xaa\xbb"
        + b"\x08\x00"
    )
    return ethernet + ip + tcp


def _tcp_flow() -> dict:
    return {
        "flow_id": "flow-tcp-000001",
        "protocol": "tcp",
        "endpoint_a": {
            "ip": "10.0.2.15",
            "port": 40000,
        },
        "endpoint_b": {
            "ip": "93.184.216.34",
            "port": 443,
        },
        "local_ip": "10.0.2.15",
        "local_port": 40000,
        "remote_ip": "93.184.216.34",
        "remote_port": 443,
    }


def _dns_query(name: str) -> bytes:
    labels = b"".join(
        bytes([len(label)]) + label.encode("ascii")
        for label in name.split(".")
    ) + b"\x00"
    return (
        b"\x12\x34"
        + b"\x01\x00"
        + b"\x00\x01"
        + b"\x00\x00\x00\x00\x00\x00"
        + labels
        + b"\x00\x01\x00\x01"
    )


def _pcap(*frames: bytes) -> bytes:
    value = bytearray()
    value.extend(b"\xd4\xc3\xb2\xa1")
    value.extend(
        struct.pack(
            "<HHIIII",
            2,
            4,
            0,
            0,
            65535,
            1,
        )
    )
    for index, frame in enumerate(frames):
        value.extend(
            struct.pack(
                "<IIII",
                1_700_000_000 + index,
                123_456,
                len(frame),
                len(frame),
            )
        )
        value.extend(frame)
    return bytes(value)


def _flow() -> dict:
    return {
        "flow_id": "flow-000001",
        "protocol": "udp",
        "endpoint_a": {
            "ip": "10.0.2.15",
            "port": 53000,
        },
        "endpoint_b": {
            "ip": "8.8.8.8",
            "port": 53,
        },
        "local_ip": "10.0.2.15",
        "local_port": 53000,
        "remote_ip": "8.8.8.8",
        "remote_port": 53,
    }


def test_flow_connection_key_is_bidirectional() -> None:
    key = flow_connection_key(_flow())
    assert key == (
        "udp",
        ("10.0.2.15", 53000),
        ("8.8.8.8", 53),
    )


def test_packet_inspector_matches_only_selected_bidirectional_flow() -> None:
    query = _ipv4_udp(
        b"\x0a\x00\x02\x0f",
        b"\x08\x08\x08\x08",
        53000,
        53,
        _dns_query("api.example.test"),
    )
    response = _ipv4_udp(
        b"\x08\x08\x08\x08",
        b"\x0a\x00\x02\x0f",
        53,
        53000,
        b"\x12\x34\x81\x80" + b"\x00" * 20,
    )
    unrelated = _ipv4_udp(
        b"\x0a\x00\x02\x0f",
        b"\x01\x01\x01\x01",
        40000,
        443,
        b"not-this-flow",
    )

    report = inspect_pcap_flow(
        io.BytesIO(
            _pcap(query, unrelated, response)
        ),
        _flow(),
        hex_preview_bytes=32,
    )

    assert report["total_packet_count"] == 3
    assert report["selected_packet_count"] == 2
    assert [
        packet["packet_index"]
        for packet in report["packets"]
    ] == [1, 3]

    first, second = report["packets"]
    assert first["direction"] == "outbound"
    assert second["direction"] == "inbound"
    assert first["dns_query"] == "api.example.test"
    assert first["pcap_record_offset"] == 24
    assert first["pcap_frame_offset"] == 40
    assert first["hex_preview_bytes"] == 32
    assert first["hex_preview_truncated"] is True


def test_packet_details_preserve_raw_locator_and_encryption_boundary() -> None:
    frame = _ipv4_udp(
        b"\x0a\x00\x02\x0f",
        b"\x08\x08\x08\x08",
        53000,
        53,
        _dns_query("api.example.test"),
    )
    packet = inspect_pcap_flow(
        io.BytesIO(_pcap(frame)),
        _flow(),
        hex_preview_bytes=64,
    )["packets"][0]

    details = format_packet_details(packet)

    assert RAW_PCAP_ARTIFACT in details
    assert "packet index: 1" in details
    assert "record byte offset: 24" in details
    assert "frame byte offset: 40" in details
    assert "Encrypted payload is not presented as plaintext" in details
    assert "api.example.test" in packet_search_text(packet)



def _timeline_for_flow(flow_id: str = "flow-000001") -> dict:
    return {
        "schema_version": "0.4",
        "user_actions": [
            {
                "action_id": "action-000001",
                "action": "tap",
                "correlation": {
                    "target_started_utc_estimate": "2023-11-14T22:13:20.000000Z",
                    "target_finished_utc_estimate": "2023-11-14T22:13:20.100000Z",
                    "window": {
                        "actual_after_seconds": 0.5,
                        "exclusive_until_next_action": True,
                    },
                    "causal_confidence": "medium",
                    "causal_claim": False,
                    "attribution": "temporal-only",
                    "network": {
                        "flow_ids": [flow_id],
                    },
                },
            }
        ],
    }


def test_packet_action_correlation_uses_exported_timeline_window_only() -> None:
    first = _ipv4_udp(
        b"\x0a\x00\x02\x0f",
        b"\x08\x08\x08\x08",
        53000,
        53,
        _dns_query("api.example.test"),
    )
    second = _ipv4_udp(
        b"\x08\x08\x08\x08",
        b"\x0a\x00\x02\x0f",
        53,
        53000,
        b"response",
    )
    report = inspect_pcap_flow(
        io.BytesIO(_pcap(first, second)),
        _flow(),
    )

    correlated = correlate_packets_with_timeline(
        report,
        _timeline_for_flow(),
    )

    assert correlated["correlation_type"] == "temporal-only"
    assert correlated["causal_claim"] is False
    assert correlated["timeline_action_window_count"] == 1
    assert correlated["packet_action_match_count"] == 1

    first_packet, second_packet = correlated["packets"]
    assert first_packet["temporal_action_ids"] == [
        "action-000001"
    ]
    assert first_packet["temporal_relation"] == "inside-action-window"
    assert first_packet["causal_claim"] is False
    assert "action-000001" in packet_action_label(first_packet)
    assert "action-000001" in packet_search_text(first_packet)

    assert second_packet["temporal_action_ids"] == []
    assert second_packet["temporal_relation"] == "none"


def test_packet_action_correlation_requires_same_flow_reference() -> None:
    frame = _ipv4_udp(
        b"\x0a\x00\x02\x0f",
        b"\x08\x08\x08\x08",
        53000,
        53,
        _dns_query("api.example.test"),
    )
    report = inspect_pcap_flow(
        io.BytesIO(_pcap(frame)),
        _flow(),
    )

    correlated = correlate_packets_with_timeline(
        report,
        _timeline_for_flow("flow-other"),
    )

    assert correlated["timeline_action_window_count"] == 0
    assert correlated["packet_action_match_count"] == 0
    assert correlated["packets"][0]["temporal_action_ids"] == []



def test_tcp_transport_metadata_and_three_way_handshake_evidence() -> None:
    local = b"\x0a\x00\x02\x0f"
    remote = b"\x5d\xb8\xd8\x22"
    frames = [
        _ipv4_tcp(
            local,
            remote,
            40000,
            443,
            sequence=100,
            acknowledgment=0,
            flags=0x02,
        ),
        _ipv4_tcp(
            remote,
            local,
            443,
            40000,
            sequence=900,
            acknowledgment=101,
            flags=0x12,
        ),
        _ipv4_tcp(
            local,
            remote,
            40000,
            443,
            sequence=101,
            acknowledgment=901,
            flags=0x10,
        ),
        _ipv4_tcp(
            local,
            remote,
            40000,
            443,
            sequence=101,
            acknowledgment=901,
            flags=0x18,
            payload=b"hello",
        ),
        _ipv4_tcp(
            remote,
            local,
            443,
            40000,
            sequence=901,
            acknowledgment=106,
            flags=0x11,
        ),
    ]

    report = inspect_pcap_flow(
        io.BytesIO(_pcap(*frames)),
        _tcp_flow(),
    )

    assert report["selected_packet_count"] == 5
    first, second, third, fourth, fifth = report["packets"]

    assert first["direction"] == "outbound"
    assert first["tcp_flags"] == ["SYN"]
    assert first["tcp_sequence"] == 100
    assert first["tcp_acknowledgment"] == 0
    assert first["tcp_header_length"] == 20
    assert first["tcp_payload_length"] == 0

    assert second["direction"] == "inbound"
    assert second["tcp_flags"] == ["ACK", "SYN"]
    assert third["tcp_flags"] == ["ACK"]
    assert fourth["tcp_flags"] == ["ACK", "PSH"]
    assert fourth["tcp_payload_length"] == 5
    assert fifth["tcp_flags"] == ["ACK", "FIN"]

    session = report["transport_session"]
    assert session["applicable"] is True
    assert session["handshake_observed"] is True
    assert session["handshake_status"] == "complete-three-way-observed"
    assert session["handshake_packet_ids"] == [
        first["packet_id"],
        second["packet_id"],
        third["packet_id"],
    ]
    assert session["termination_status"] == "fin-observed"
    assert session["termination_packet_ids"] == [
        fifth["packet_id"]
    ]

    assert packet_transport_label(first) == "TCP:SYN"
    assert "SYN" in packet_search_text(first)
    details = format_packet_details(fourth)
    assert "TCP flags: ACK, PSH" in details
    assert "Sequence / ACK: 101 / 901" in details


def test_tcp_session_absence_is_not_interpreted_as_non_occurrence() -> None:
    frame = _ipv4_tcp(
        b"\x0a\x00\x02\x0f",
        b"\x5d\xb8\xd8\x22",
        40000,
        443,
        sequence=500,
        acknowledgment=700,
        flags=0x10,
        payload=b"midstream",
    )
    report = inspect_pcap_flow(
        io.BytesIO(_pcap(frame)),
        _tcp_flow(),
    )

    session = report["transport_session"]
    assert session["handshake_observed"] is False
    assert (
        session["handshake_status"]
        == "partial-or-not-observed-in-capture"
    )
    assert (
        session["termination_status"]
        == "not-observed-in-capture"
    )
    assert "does not prove" in session["absence_semantics"]
