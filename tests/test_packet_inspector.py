from __future__ import annotations

import io
import struct

from apk_research.desktop.packet_inspector import (
    RAW_PCAP_ARTIFACT,
    flow_connection_key,
    format_packet_details,
    inspect_pcap_flow,
    packet_search_text,
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
