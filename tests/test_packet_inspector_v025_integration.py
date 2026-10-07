from __future__ import annotations

import io
import struct

from apk_research.desktop.packet_inspector import inspect_pcap_flow


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


def _pcap(*frames: bytes) -> bytes:
    value = bytearray(b"\xd4\xc3\xb2\xa1")
    value.extend(struct.pack("<HHIIII", 2, 4, 0, 0, 65535, 1))
    for index, frame in enumerate(frames):
        value.extend(
            struct.pack(
                "<IIII",
                1_700_100_000 + index,
                0,
                len(frame),
                len(frame),
            )
        )
        value.extend(frame)
    return bytes(value)


def _flow() -> dict:
    return {
        "flow_id": "flow-v025-http",
        "protocol": "tcp",
        "endpoint_a": {"ip": "10.0.2.15", "port": 41000},
        "endpoint_b": {"ip": "93.184.216.34", "port": 80},
        "local_ip": "10.0.2.15",
        "local_port": 41000,
        "remote_ip": "93.184.216.34",
        "remote_port": 80,
    }


def test_packet_inspector_emits_capture_bounded_v025_report() -> None:
    local = b"\x0a\x00\x02\x0f"
    remote = b"\x5d\xb8\xd8\x22"
    request = b"GET /status HTTP/1.1\r\nHost: example.com\r\n\r\n"
    response = b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\n\r\n"
    frames = [
        _ipv4_tcp(
            local,
            remote,
            41000,
            80,
            sequence=100,
            acknowledgment=0,
            flags=0x02,
        ),
        _ipv4_tcp(
            remote,
            local,
            80,
            41000,
            sequence=500,
            acknowledgment=101,
            flags=0x12,
        ),
        _ipv4_tcp(
            local,
            remote,
            41000,
            80,
            sequence=101,
            acknowledgment=501,
            flags=0x10,
        ),
        _ipv4_tcp(
            local,
            remote,
            41000,
            80,
            sequence=101,
            acknowledgment=501,
            flags=0x18,
            payload=request,
        ),
        _ipv4_tcp(
            remote,
            local,
            80,
            41000,
            sequence=501,
            acknowledgment=101 + len(request),
            flags=0x18,
            payload=response,
        ),
        _ipv4_tcp(
            local,
            remote,
            41000,
            80,
            sequence=101 + len(request),
            acknowledgment=501 + len(response),
            flags=0x11,
        ),
    ]

    report = inspect_pcap_flow(io.BytesIO(_pcap(*frames)), _flow())
    analysis = report["protocol_analysis"]

    assert analysis["schema_version"] == "0.1"
    assert analysis["scope"] == "selected-flow"
    assert analysis["evidence_basis"] == "captured-packets-only"
    assert analysis["causal_claim"] is False

    transport = analysis["transport"]
    assert transport["capture_start_status"] == "syn-observed"
    assert transport["capture_end_status"] == "fin-observed"
    assert transport["missing_start_possible"] is False
    assert transport["missing_end_possible"] is False

    http = analysis["http"]
    assert http["cleartext_message_count"] == 2
    assert len(http["transactions"]) == 1
    transaction = http["transactions"][0]
    assert transaction["method"] == "GET"
    assert transaction["target"] == "/status"
    assert transaction["status_code"] == 204
    assert transaction["confidence"] == "HIGH"

    request_packet = report["packets"][3]
    response_packet = report["packets"][4]
    assert request_packet["http_method"] == "GET"
    assert request_packet["http_host"] == "example.com"
    assert response_packet["http_status"] == 204
    assert "missing traffic" in analysis["absence_semantics"]
