from __future__ import annotations

from apk_research.desktop.protocol_analysis_v025 import (
    FlowProtocolAnalyzer,
    parse_dns_message,
    parse_http_message,
    parse_tls_records,
)


def _dns_name(name: str) -> bytes:
    return b"".join(
        bytes([len(label)]) + label.encode("ascii")
        for label in name.split(".")
    ) + b"\x00"


def _dns_query() -> bytes:
    return (
        b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
        + _dns_name("example.com")
        + b"\x00\x01\x00\x01"
    )


def _dns_response() -> bytes:
    return (
        b"\x12\x34\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00"
        + _dns_name("example.com")
        + b"\x00\x01\x00\x01"
        + b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04"
        + b"\x5d\xb8\xd8\x22"
    )


def _extension(kind: int, payload: bytes) -> bytes:
    return kind.to_bytes(2, "big") + len(payload).to_bytes(2, "big") + payload


def _tls_client_hello() -> bytes:
    host = b"example.com"
    sni = (
        (3 + len(host)).to_bytes(2, "big")
        + b"\x00"
        + len(host).to_bytes(2, "big")
        + host
    )
    alpn_value = b"h2"
    alpn = (1 + len(alpn_value)).to_bytes(2, "big") + bytes([len(alpn_value)]) + alpn_value
    versions = b"\x04\x03\x04\x03\x03"
    extensions = (
        _extension(0, sni)
        + _extension(16, alpn)
        + _extension(43, versions)
    )
    body = (
        b"\x03\x03"
        + b"\x00" * 32
        + b"\x00"
        + b"\x00\x02\x13\x01"
        + b"\x01\x00"
        + len(extensions).to_bytes(2, "big")
        + extensions
    )
    handshake = b"\x01" + len(body).to_bytes(3, "big") + body
    return b"\x16\x03\x01" + len(handshake).to_bytes(2, "big") + handshake


def _packet(
    packet_id: str,
    *,
    direction: str,
    sequence: int,
    acknowledgment: int,
    payload_length: int,
    flags: list[str],
    window: int = 4096,
) -> dict:
    return {
        "packet_id": packet_id,
        "protocol": "tcp",
        "direction": direction,
        "src_port": 12345 if direction == "outbound" else 443,
        "dst_port": 443 if direction == "outbound" else 12345,
        "tcp_header_valid": True,
        "tcp_sequence": sequence,
        "tcp_acknowledgment": acknowledgment,
        "tcp_payload_length": payload_length,
        "tcp_flags": flags,
        "tcp_window": window,
    }


def test_dns_query_response_parsing_and_transaction_grouping() -> None:
    query = parse_dns_message(_dns_query())
    response = parse_dns_message(_dns_response())
    assert query is not None
    assert response is not None
    assert query["kind"] == "query"
    assert query["questions"][0]["name"] == "example.com"
    assert response["kind"] == "response"
    assert response["answers"][0]["data"] == "93.184.216.34"

    analyzer = FlowProtocolAnalyzer("udp")
    packets = [
        {
            "packet_id": "q",
            "protocol": "udp",
            "direction": "outbound",
            "src_port": 53000,
            "dst_port": 53,
        },
        {
            "packet_id": "r",
            "protocol": "udp",
            "direction": "inbound",
            "src_port": 53,
            "dst_port": 53000,
        },
    ]
    analyzer.observe(packets[0], _dns_query())
    analyzer.observe(packets[1], _dns_response())
    report = analyzer.finalize(packets)
    assert report["dns"]["message_count"] == 2
    assert report["dns"]["transactions"][0]["status"] == "query-response-observed"
    assert report["dns"]["transactions"][0]["confidence"] == "HIGH"


def test_tls_client_hello_exposes_only_observed_metadata() -> None:
    value = parse_tls_records(_tls_client_hello())
    assert value is not None
    client = value["client_hello"]
    assert client["sni"] == "example.com"
    assert client["alpn"] == ["h2"]
    assert "TLS1.3" in client["supported_versions"]
    assert value["complete_record_count"] == 1


def test_cleartext_http_request_and_response_are_bounded() -> None:
    request = parse_http_message(
        b"GET /status?x=1 HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n"
    )
    response = parse_http_message(
        b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\n\r\n"
    )
    assert request is not None
    assert request["kind"] == "request"
    assert request["method"] == "GET"
    assert request["target"] == "/status?x=1"
    assert request["host"] == "example.com"
    assert response is not None
    assert response["kind"] == "response"
    assert response["status"] == 204
    assert parse_http_message(b"encrypted-or-partial") is None


def test_tcp_analysis_marks_capture_observations_without_loss_claim() -> None:
    packets = [
        _packet(
            "syn",
            direction="outbound",
            sequence=100,
            acknowledgment=0,
            payload_length=0,
            flags=["SYN"],
        ),
        _packet(
            "synack",
            direction="inbound",
            sequence=500,
            acknowledgment=101,
            payload_length=0,
            flags=["SYN", "ACK"],
        ),
        _packet(
            "ack",
            direction="outbound",
            sequence=101,
            acknowledgment=501,
            payload_length=0,
            flags=["ACK"],
        ),
        _packet(
            "data1",
            direction="outbound",
            sequence=101,
            acknowledgment=501,
            payload_length=10,
            flags=["PSH", "ACK"],
        ),
        _packet(
            "repeat",
            direction="outbound",
            sequence=101,
            acknowledgment=501,
            payload_length=10,
            flags=["PSH", "ACK"],
        ),
        _packet(
            "gap-after",
            direction="outbound",
            sequence=121,
            acknowledgment=501,
            payload_length=5,
            flags=["PSH", "ACK"],
        ),
        _packet(
            "fin",
            direction="outbound",
            sequence=126,
            acknowledgment=501,
            payload_length=0,
            flags=["FIN", "ACK"],
        ),
    ]
    analyzer = FlowProtocolAnalyzer("tcp")
    report = analyzer.finalize(packets)
    tcp = report["transport"]
    assert tcp["capture_start_status"] == "syn-observed"
    assert tcp["capture_end_status"] == "fin-observed"
    assert tcp["repeated_sequence_range_count"] == 1
    assert tcp["sequence_gap_observation_count"] == 1
    assert "repeated-sequence-range" in packets[4]["tcp_analysis_flags"]
    assert "sequence-gap-after-previous-observed-data" in packets[5]["tcp_analysis_flags"]
    assert "do not by themselves prove packet loss" in tcp["evidence_semantics"]


def test_quic_http3_aggregation_uses_existing_observed_metadata() -> None:
    packet = {
        "packet_id": "quic-1",
        "protocol": "udp",
        "direction": "outbound",
        "src_port": 40000,
        "dst_port": 443,
        "quic_version": "v1",
        "quic_packet_type": "initial",
        "quic_sni": "example.com",
        "quic_alpn": ["h3"],
        "application_protocol": "http3",
    }
    analyzer = FlowProtocolAnalyzer("udp")
    report = analyzer.finalize([packet])
    assert report["quic"]["observed"] is True
    assert report["quic"]["versions"] == ["v1"]
    assert report["quic"]["http3_observed_via_alpn"] is True
    assert report["quic"]["application_payload_visibility"] == "encrypted-metadata-only"
