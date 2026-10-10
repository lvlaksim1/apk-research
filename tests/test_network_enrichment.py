from __future__ import annotations

import ipaddress
import json
import struct
from pathlib import Path

from apk_research.network_enrichment import (
    derive_network_evidence, _dns, _tls_hello, _packets,
)


def _ip_udp(payload: bytes, *, src_port: int = 50000, dst_port: int = 53) -> bytes:
    udp = struct.pack("!HHHH", src_port, dst_port, 8 + len(payload), 0) + payload
    ip = struct.pack("!BBHHHBBH4s4s",
        0x45, 0, 20 + len(udp), 1, 0, 64, 17, 0,
        ipaddress.IPv4Address("10.0.2.15").packed,
        ipaddress.IPv4Address("8.8.8.8").packed,
    )
    return struct.pack("!HHH8sH", 0, 1, 6, b"\0" * 8, 0x0800) + ip + udp


def _ip_tcp(payload: bytes) -> bytes:
    tcp = struct.pack("!HHIIHHHH", 51000, 443, 0, 0, 5 << 12, 65535, 0, 0) + payload
    ip = struct.pack("!BBHHHBBH4s4s",
        0x45, 0, 20 + len(tcp), 1, 0, 64, 6, 0,
        ipaddress.IPv4Address("10.0.2.15").packed,
        ipaddress.IPv4Address("93.184.215.14").packed,
    )
    return struct.pack("!HHH8sH", 0, 1, 6, b"\0" * 8, 0x0800) + ip + tcp


def _client_hello() -> bytes:
    server_name = b"evrasia.spb.ru"
    sni = b"\x00" + len(server_name).to_bytes(2, "big") + server_name
    sni_ext = len(sni).to_bytes(2, "big") + sni
    alpn = b"\x02h2"
    alpn_ext = len(alpn).to_bytes(2, "big") + alpn
    supported = b"\x02\x03\x04"
    extensions = (
        b"\x00\x00" + len(sni_ext).to_bytes(2, "big") + sni_ext
        + b"\x00\x10" + len(alpn_ext).to_bytes(2, "big") + alpn_ext
        + b"\x00\x2b" + len(supported).to_bytes(2, "big") + supported
    )
    body = (
        b"\x03\x03" + b"\x01" * 32 + b"\x00"
        + b"\x00\x02\x13\x01" + b"\x01\x00"
        + len(extensions).to_bytes(2, "big") + extensions
    )
    handshake = b"\x01" + len(body).to_bytes(3, "big") + body
    return b"\x16\x03\x01" + len(handshake).to_bytes(2, "big") + handshake


def _dns_query() -> bytes:
    qname = b"\x07evrasia\x03spb\x02ru\x00"
    return struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0) + qname + b"\x00\x01\x00\x01"


def _make_pcap(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = [_ip_udp(_dns_query()), _ip_tcp(_client_hello())]
    with path.open("wb") as output:
        output.write(b"\xd4\xc3\xb2\xa1")
        output.write(struct.pack("<HHiiii", 2, 4, 0, 0, 65535, 113))
        for idx, frame in enumerate(frames):
            output.write(struct.pack("<IIII", 1000 + idx, 0, len(frame), len(frame)))
            output.write(frame)


def test_dns_and_tls_are_parsed_without_guessing():
    packet = _dns(_dns_query(), 1.0, "a", "b", "udp")
    assert packet["questions"] == [{"name": "evrasia.spb.ru", "type": 1, "class": 1}]
    assert packet["response"] is False
    hello = _tls_hello(_client_hello())
    assert hello["sni"] == "evrasia.spb.ru"
    assert hello["alpn"] == ["h2"]
    assert hello["tls_versions"] == ["0x0304"]
    assert _tls_hello(_client_hello()[:25]) is None


def test_research_zip_derivation_preserves_sources(tmp_path: Path):
    pcap = tmp_path / "01_raw/network/traffic.pcap"
    _make_pcap(pcap)
    original = pcap.read_bytes()
    http = tmp_path / "02_normalized/http-transactions.jsonl"
    http.parent.mkdir(parents=True, exist_ok=True)
    http.write_text(
        json.dumps({
            "transaction_id": "http-1", "url": "https://evrasia.spb.ru/menu/",
            "timestamp_start": 1001.0, "timestamp_end": 1001.3,
            "request": {"body": {"size": 0}},
            "response": {"status_code": 200, "body": {"size": 315}},
        }) + "\n",
        encoding="utf-8",
    )
    actions = tmp_path / "02_normalized/user-actions.jsonl"
    actions.write_text(json.dumps({
        "action_id": "action-000001", "action": "tap",
        "host_utc": "1970-01-01T00:16:40+00:00",
    }) + "\n", encoding="utf-8")
    result = derive_network_evidence(tmp_path)
    assert result["packets_scanned"] == 2
    assert result["dns_records"] == 1
    assert result["tls_hellos"] == 1
    assert result["http_timings"] == 1
    assert result["action_links"] == 1
    assert pcap.read_bytes() == original
    dns = json.loads((tmp_path / "02_normalized/dns.jsonl").read_text().splitlines()[0])
    tls = json.loads((tmp_path / "02_normalized/tls-sessions.jsonl").read_text().splitlines()[0])
    link = json.loads((tmp_path / "02_normalized/action-network-links.jsonl").read_text().splitlines()[0])
    assert dns["questions"][0]["name"] == "evrasia.spb.ru"
    assert tls["sni"] == "evrasia.spb.ru"
    assert link["relationship"] == "temporal_candidate"
    assert link["delta_ms"] == 1000.0


def test_missing_pcap_produces_explainable_empty_evidence(tmp_path: Path):
    summary = derive_network_evidence(tmp_path)
    assert summary["packets_scanned"] == 0
    assert summary["tls_hellos"] == 0
    assert (tmp_path / "02_normalized/network-enrichment.json").is_file()
