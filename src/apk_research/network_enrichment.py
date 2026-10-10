"""Post-session DNS, TLS and action timing evidence from original records.

Only observed data are emitted. No DNS records, TLS parameters, device
ownership or causal links are invented. Raw PCAP and HTTP bodies are not
changed. Parsing runs after raw collectors stop, before ZIP sealing.
"""
from __future__ import annotations

import json
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from apk_research.timeline import (
    _pcap_header, _network_payload, _decode_ip, _read_jsonl,
)
from apk_research.desktop.protocol_analysis_v025 import (
    parse_dns_message, parse_tls_records,
)

DNS_PATH = "02_normalized/dns.jsonl"
TLS_PATH = "02_normalized/tls-sessions.jsonl"
LINKS_PATH = "02_normalized/action-network-links.jsonl"
SCREEN_PATH = "02_normalized/screen-timing.jsonl"
STATUS_PATH = "02_normalized/network-enrichment.json"
EVIDENCE_PATHS = (DNS_PATH, TLS_PATH, LINKS_PATH, SCREEN_PATH, STATUS_PATH)
MAX_PCAP_RECORD = 16 * 1024 * 1024
ACTION_WINDOW_S = 5.0


def _packets(path: Path) -> Iterator[tuple[float, dict[str, Any]]]:
    if not path.is_file():
        return
    with path.open("rb") as raw:
        endian, scale, linktype = _pcap_header(raw)
        if linktype < 0:
            return
        while True:
            header = raw.read(16)
            if len(header) != 16:
                return
            sec, fract, size, _original = struct.unpack(
                endian + "IIII", header
            )
            if size > MAX_PCAP_RECORD:
                return
            payload = raw.read(size)
            if len(payload) != size:
                return
            network, ether, _direction = _network_payload(payload, linktype)
            if network is None:
                continue
            decoded = _decode_ip(network, ether)
            if decoded is not None:
                yield sec + fract / scale, decoded


def _epoch(value: Any) -> float | None:
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if not value:
            return None
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (ValueError, TypeError, OverflowError):
        return None


def _line(writer, record: dict[str, Any]) -> None:
    writer.write(json.dumps(
        record, ensure_ascii=False, sort_keys=True
    ) + "\n")


def _parse_network(root: Path, dns_file, tls_file) -> dict[str, int]:
    counts = {"dns": 0, "tls": 0, "packets_observed": 0}
    requests: dict[tuple, float] = {}
    for epoch, packet in _packets(root / "01_raw/network/traffic.pcap"):
        counts["packets_observed"] += 1
        protocol = packet.get("protocol")
        sport, dport = packet.get("src_port"), packet.get("dst_port")
        src, dst = packet.get("src"), packet.get("dst")
        data = packet.get("payload") or b""
        if 53 in (sport, dport) and protocol in ("tcp", "udp"):
            dns = parse_dns_message(data, tcp=protocol == "tcp")
            if dns:
                names = dns.get("questions") or []
                key = (
                    dns["id"], str(names[0].get("name") if names else ""),
                    protocol, tuple(sorted((str(src), str(dst)))),
                )
                if dns["kind"] == "query":
                    requests[key] = epoch
                duration = (
                    round((epoch - requests[key]) * 1000, 3)
                    if dns["kind"] == "response" and key in requests
                    and epoch >= requests[key] else None
                )
                _line(dns_file, {
                    "epoch": epoch, "src": src, "dst": dst,
                    "src_port": sport, "dst_port": dport,
                    "protocol": protocol, "observed": True,
                    "dns": dns, "response_delay_ms": duration,
                    "timing_evidence": "same-transaction-id-name-endpoints"
                    if duration is not None else None,
                })
                counts["dns"] += 1
        if protocol == "tcp" and 443 in (sport, dport) and data:
            tls = parse_tls_records(data)
            if tls and (tls.get("client_hello") or tls.get("server_hello")):
                _line(tls_file, {
                    "epoch": epoch,
                    "src": src, "dst": dst,
                    "src_port": sport, "dst_port": dport,
                    "observed": True,
                    "client_hello": tls.get("client_hello"),
                    "server_hello": tls.get("server_hello"),
                    "note": "Observed TLS record; no synthetic missing handshake",
                })
                counts["tls"] += 1
    return counts


def _action_network_links(root: Path, output) -> int:
    actions = _read_jsonl(root / "02_normalized/user-actions.jsonl")
    actions_with_times = []
    for item in actions:
        t = _epoch(item.get("host_utc"))
        if t is not None:
            actions_with_times.append((t, item))
    actions_with_times.sort(key=lambda x: x[0])
    links = 0
    for tx in _read_jsonl(root / "02_normalized/http-transactions.jsonl"):
        started = _epoch(tx.get("timestamp_start"))
        if started is None:
            continue
        candidates = [
            (t, action) for t, action in actions_with_times
            if 0 <= started - t <= ACTION_WINDOW_S
        ]
        if not candidates:
            continue
        t, action = candidates[-1]
        _line(output, {
            "transaction_id": tx.get("transaction_id"),
            "request_utc_epoch": started,
            "action_utc_epoch": t,
            "action": action.get("action"),
            "action_id": action.get("action_id"),
            "elapsed_after_action_ms": round((started - t) * 1000, 3),
            "relationship": "temporal-association-only",
            "causality_proven": False,
            "window_seconds": ACTION_WINDOW_S,
        })
        links += 1
    return links


def _screen_timing(root: Path, output) -> int:
    path = root / "02_normalized/screen.json"
    if not path.is_file():
        return 0
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    chunks = metadata.get("completed_chunks") or []
    count = 0
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            continue
        timing = chunk.get("frame_timing")
        if not isinstance(timing, dict):
            timing = None
        _line(output, {
            "chunk_index": chunk.get("index", index + 1),
            "capture_started_utc": chunk.get("started_utc"),
            "capture_stopped_utc": chunk.get("stopped_utc"),
            "frame_timing": timing,
            "source": "screen-recording-chunk-metadata",
            "per_action_latency_asserted": False,
        })
        count += 1
    return count


def build_network_enrichment(session) -> dict[str, Any]:
    """Register always-present files and add grounded optional data to ZIP."""
    root = session.paths.root
    for relative in EVIDENCE_PATHS:
        session.register_artifact(
            kind="network_enrichment",
            relative_path=relative,
            source="network-enrichment",
            raw=False,
        )
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "schema_version": "0.1",
        "status": "complete",
        "packet_data_available": (root / "01_raw/network/traffic.pcap").is_file(),
        "counts": {},
        "limitations": [
            "Packet-based DNS excludes encrypted DNS not visible as port 53",
            "TLS data contains only observed complete handshake records",
            "Action links are temporal, not proof of causality",
            "Screen timing reflects recorded chunk timestamps",
        ],
    }
    try:
        with (
            (root / DNS_PATH).open("w", encoding="utf-8") as dns_file,
            (root / TLS_PATH).open("w", encoding="utf-8") as tls_file,
            (root / LINKS_PATH).open("w", encoding="utf-8") as link_file,
            (root / SCREEN_PATH).open("w", encoding="utf-8") as screen_file,
        ):
            result["counts"] = _parse_network(root, dns_file, tls_file)
            result["counts"]["temporal_links"] = _action_network_links(root, link_file)
            result["counts"]["screen_chunks"] = _screen_timing(root, screen_file)
            http = _read_jsonl(root / "02_normalized/http-transactions.jsonl")
            result["counts"]["http_transactions"] = len(http)
            result["counts"]["https_direct"] = sum(
                (item.get("interception") or {}).get("route") == "direct"
                for item in http
            )
            result["counts"]["request_bytes"] = sum(
                int(((item.get("request") or {}).get("body") or {}).get("size") or 0)
                for item in http
            )
            result["counts"]["response_bytes"] = sum(
                int(((item.get("response") or {}).get("body") or {}).get("size") or 0)
                for item in http
            )
    except Exception as exc:
        # Derived enrichment must not destroy a complete raw recording.
        result["status"] = "incomplete"
        result["error"] = str(exc) or exc.__class__.__name__
    (root / STATUS_PATH).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result
