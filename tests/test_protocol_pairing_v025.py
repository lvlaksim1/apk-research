from __future__ import annotations

from apk_research.desktop.protocol_analysis_v025 import FlowProtocolAnalyzer


def _dns_packet(packet_id: str, direction: str, kind: str) -> dict:
    return {
        "packet_id": packet_id,
        "protocol": "udp",
        "direction": direction,
        "src_port": 53000 if direction == "outbound" else 53,
        "dst_port": 53 if direction == "outbound" else 53000,
        "dns_message": {
            "id": 0x1234,
            "kind": kind,
            "questions": (
                [{"name": "example.com", "type": "A", "type_code": 1, "class": 1}]
                if kind == "query"
                else []
            ),
        },
    }


def _http_packet(packet_id: str, direction: str, kind: str) -> dict:
    metadata = {
        "kind": kind,
        "protocol": "http1",
        "complete_headers": True,
    }
    if kind == "request":
        metadata.update({"method": "GET", "target": "/status", "host": "example.com"})
    else:
        metadata.update({"status": 204, "reason": "No Content"})
    return {
        "packet_id": packet_id,
        "protocol": "tcp",
        "direction": direction,
        "src_port": 41000 if direction == "outbound" else 80,
        "dst_port": 80 if direction == "outbound" else 41000,
        "http_metadata": metadata,
    }


def test_dns_response_before_query_is_not_promoted_to_high_confidence_pair() -> None:
    response = _dns_packet("dns-r", "inbound", "response")
    query = _dns_packet("dns-q", "outbound", "query")

    report = FlowProtocolAnalyzer("udp").finalize([response, query])
    transaction = report["dns"]["transactions"][0]

    assert transaction["status"] == "partial-or-ambiguous"
    assert transaction["confidence"] == "LOW"
    assert "capture-ordered" in transaction["basis"]


def test_dns_query_before_response_remains_high_confidence_pair() -> None:
    query = _dns_packet("dns-q", "outbound", "query")
    response = _dns_packet("dns-r", "inbound", "response")

    report = FlowProtocolAnalyzer("udp").finalize([query, response])
    transaction = report["dns"]["transactions"][0]

    assert transaction["status"] == "query-response-observed"
    assert transaction["confidence"] == "HIGH"
    assert transaction["query_packet_id"] == "dns-q"
    assert transaction["response_packet_id"] == "dns-r"


def test_http_response_before_request_is_not_paired() -> None:
    response = _http_packet("http-r", "inbound", "response")
    request = _http_packet("http-q", "outbound", "request")

    report = FlowProtocolAnalyzer("tcp").finalize([response, request])

    assert report["http"]["transactions"] == []


def test_http_request_before_response_remains_high_confidence_pair() -> None:
    request = _http_packet("http-q", "outbound", "request")
    response = _http_packet("http-r", "inbound", "response")

    report = FlowProtocolAnalyzer("tcp").finalize([request, response])
    transactions = report["http"]["transactions"]

    assert len(transactions) == 1
    assert transactions[0]["confidence"] == "HIGH"
    assert transactions[0]["request_packet_id"] == "http-q"
    assert transactions[0]["response_packet_id"] == "http-r"
    assert "request-before-response" in transactions[0]["basis"]
