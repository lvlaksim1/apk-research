from __future__ import annotations

import json
import socket
import struct
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from apk_research.network_enrichment import (
    build_network_enrichment, DNS_PATH, TLS_PATH, LINKS_PATH, SCREEN_PATH,
)


class _Session:
    def __init__(self, root):
        self.paths = SimpleNamespace(root=root)
        self.artifacts = []

    def register_artifact(self, *, kind, relative_path, source, raw):
        self.artifacts.append((relative_path, raw, kind))


def _packet(src, dst, sport, dport, data: bytes) -> bytes:
    udp = struct.pack("!HHHH", sport, dport, len(data) + 8, 0) + data
    ip = bytearray(20)
    ip[0] = 0x45
    ip[2:4] = struct.pack("!H", 20 + len(udp))
    ip[8] = 64
    ip[9] = 17
    ip[12:16] = socket.inet_aton(src)
    ip[16:20] = socket.inet_aton(dst)
    return bytes(ip) + udp


def _pcap(path: Path, frames: list[tuple[float, bytes]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        stream.write(b"\xd4\xc3\xb2\xa1")
        stream.write(struct.pack("<HHiiii", 2, 4, 0, 0, 65535, 101))
        for epoch, packet in frames:
            seconds = int(epoch)
            micros = int(round((epoch - seconds) * 1000000))
            stream.write(struct.pack(
                "<IIII", seconds, micros, len(packet), len(packet)
            ))
            stream.write(packet)


def _dns(name: bytes, response=False):
    flags = b"\x81\x80" if response else b"\x01\x00"
    header = b"\x12\x34" + flags + b"\x00\x01"
    header += b"\x00\x01" if response else b"\x00\x00"
    header += b"\x00\x00\x00\x00"
    question = b"\x07example\x03org\x00\x00\x01\x00\x01"
    answer = (
        b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c"
        b"\x00\x04\x01\x02\x03\x04"
    ) if response else b""
    return header + question + answer


def test_full_derived_archive_files_and_temporal_only_correlations(tmp_path):
    root = tmp_path
    baseline = datetime(2026, 10, 10, tzinfo=timezone.utc).timestamp()
    request = _packet(
        "10.0.2.15", "8.8.8.8", 53499, 53, _dns(b"example.org")
    )
    response = _packet(
        "8.8.8.8", "10.0.2.15", 53, 53499,
        _dns(b"example.org", response=True),
    )
    _pcap(
        root / "01_raw/network/traffic.pcap",
        [(baseline + 0.2, request), (baseline + 0.23, response)],
    )
    norm = root / "02_normalized"
    norm.mkdir(parents=True)
    (norm / "user-actions.jsonl").write_text(
        json.dumps({
            "action": "tap", "action_id": "tap-001",
            "host_utc": datetime.fromtimestamp(
                baseline + 0.1, timezone.utc
            ).isoformat(),
        }) + "\n", encoding="utf-8",
    )
    (norm / "http-transactions.jsonl").write_text(
        json.dumps({
            "transaction_id": "http-1",
            "timestamp_start": baseline + 0.3,
        }) + "\n", encoding="utf-8",
    )
    (norm / "screen.json").write_text(
        json.dumps({"completed_chunks": [{
            "index": 1, "started_utc": "2026-10-10T00:00:00Z",
            "stopped_utc": "2026-10-10T00:00:10Z",
            "frame_timing": {"frame_count": 17},
        }]}), encoding="utf-8",
    )

    session = _Session(root)
    report = build_network_enrichment(session)
    assert report["status"] == "complete"
    assert report["counts"]["dns"] == 2
    assert report["counts"]["temporal_links"] == 1
    assert report["counts"]["screen_chunks"] == 1
    assert len(session.artifacts) == 5
    assert all(not raw for _, raw, _ in session.artifacts)
    dns = [
        json.loads(line) for line in (root / DNS_PATH).read_text().splitlines()
    ]
    assert dns[0]["dns"]["kind"] == "query"
    assert dns[1]["dns"]["answers"][0]["data"] == "1.2.3.4"
    assert 20 <= dns[1]["response_delay_ms"] <= 40
    links = [
        json.loads(line)
        for line in (root / LINKS_PATH).read_text().splitlines()
    ]
    assert links[0]["causality_proven"] is False
    assert links[0]["relationship"] == "temporal-association-only"
    screen = json.loads((root / SCREEN_PATH).read_text().splitlines()[0])
    assert screen["per_action_latency_asserted"] is False
    assert (root / TLS_PATH).is_file()


def test_missing_pcap_still_produces_valid_empty_enrichment(tmp_path):
    session = _Session(tmp_path)
    result = build_network_enrichment(session)
    assert result["status"] == "complete"
    assert result["packet_data_available"] is False
    assert len(session.artifacts) == 5
    assert (tmp_path / DNS_PATH).read_text() == ""
    assert (tmp_path / TLS_PATH).read_text() == ""
