"""Bounded offline DNS, TLS and action/network summaries from an existing Research ZIP session.

This module never changes source PCAP or HTTP transactions. Unknown, fragmented
or undecodable records are skipped and counted rather than reconstructed by guess.
"""
from __future__ import annotations

import ipaddress
import json
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


DNS_PATH = "02_normalized/dns.jsonl"
TLS_PATH = "02_normalized/tls-sessions.jsonl"
LINKS_PATH = "02_normalized/action-network-links.jsonl"
TIMINGS_PATH = "02_normalized/network-timings.jsonl"
SUMMARY_PATH = "02_normalized/network-enrichment.json"

INPUT_PCAP = "01_raw/network/traffic.pcap"
INPUT_HTTP = "02_normalized/http-transactions.jsonl"
INPUT_ACTIONS = "02_normalized/user-actions.jsonl"
MAX_CAPTURED_PACKET = 1024 * 1024
MAX_RECORDS = 1000000


def _jsonl(path: Path) -> Iterator[dict]:
    if not path.is_file():
        return
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict):
                yield item


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _packets(path: Path) -> Iterator[tuple[float, int, bytes]]:
    if not path.is_file():
        return
    with path.open("rb") as stream:
        header = stream.read(24)
        if len(header) != 24:
            return
        magic = header[:4]
        formats = {
            b"\xd4\xc3\xb2\xa1": ("<", 1e6),
            b"\xa1\xb2\xc3\xd4": (">", 1e6),
            b"\x4d\x3c\xb2\xa1": ("<", 1e9),
            b"\xa1\xb2\x3c\x4d": (">", 1e9),
        }
        if magic not in formats:
            return
        endian, resolution = formats[magic]
        network = struct.unpack_from(endian + "I", header, 20)[0] & 0xffff
        for _ in range(MAX_RECORDS):
            record_header = stream.read(16)
            if len(record_header) != 16:
                break
            secs, fraction, captured, original = struct.unpack(
                endian + "IIII", record_header
            )
            if captured > MAX_CAPTURED_PACKET:
                break
            frame = stream.read(captured)
            if len(frame) != captured:
                break
            yield secs + fraction / resolution, network, frame


def _ip_packet(linktype: int, packet: bytes):
    """Return (protocol, src, dst, payload), or None for unsupported layouts."""
    if linktype == 1:  # Ethernet
        if len(packet) < 14:
            return None
        offset = 14
        ethertype = int.from_bytes(packet[12:14], "big")
        if ethertype in (0x8100, 0x88a8):
            if len(packet) < 18:
                return None
            ethertype = int.from_bytes(packet[16:18], "big")
            offset += 4
    elif linktype == 113:  # Linux cooked v1; tcpdump -i any
        if len(packet) < 16:
            return None
        ethertype = int.from_bytes(packet[14:16], "big")
        offset = 16
    elif linktype == 276:  # Linux cooked v2
        if len(packet) < 20:
            return None
        ethertype = int.from_bytes(packet[:2], "big")
        offset = 20
    elif linktype == 101:  # Raw IP
        if not packet:
            return None
        ethertype = 0x86dd if packet[0] >> 4 == 6 else 0x0800
        offset = 0
    else:
        return None

    if ethertype == 0x0800:
        ip = packet[offset:]
        if len(ip) < 20 or ip[0] >> 4 != 4:
            return None
        ihl = (ip[0] & 15) * 4
        if len(ip) < ihl or ihl < 20:
            return None
        # A partial IPv4 fragment cannot be decoded without reassembly.
        fragment = int.from_bytes(ip[6:8], "big")
        if fragment & 0x3fff:
            return None
        length = min(len(ip), int.from_bytes(ip[2:4], "big"))
        return (ip[9], str(ipaddress.IPv4Address(ip[12:16])),
                str(ipaddress.IPv4Address(ip[16:20])), ip[ihl:length])
    if ethertype == 0x86dd:
        ip = packet[offset:]
        if len(ip) < 40 or ip[0] >> 4 != 6:
            return None
        # Extension headers are not presumed to be TCP/UDP.
        return (ip[6], str(ipaddress.IPv6Address(ip[8:24])),
                str(ipaddress.IPv6Address(ip[24:40])), ip[40:40 + int.from_bytes(ip[4:6], "big")])
    return None


def _transport(proto: int, data: bytes):
    if proto == 17 and len(data) >= 8:  # UDP
        length = int.from_bytes(data[4:6], "big")
        if length < 8:
            return None
        return (int.from_bytes(data[:2], "big"), int.from_bytes(data[2:4], "big"),
                data[8:min(len(data), length)], "udp")
    if proto == 6 and len(data) >= 20:
        offset = (data[12] >> 4) * 4
        if offset < 20 or len(data) < offset:
            return None
        return (int.from_bytes(data[:2], "big"), int.from_bytes(data[2:4], "big"),
                data[offset:], "tcp")
    return None


def _dns_name(message: bytes, start: int) -> tuple[str, int]:
    labels: list[str] = []
    pos = start
    after = None
    visited: set[int] = set()
    for _ in range(80):
        if pos >= len(message) or pos in visited:
            raise ValueError("invalid DNS name")
        visited.add(pos)
        length = message[pos]
        if length & 0xc0 == 0xc0:
            if pos + 1 >= len(message):
                raise ValueError("truncated DNS pointer")
            target = ((length & 0x3f) << 8) | message[pos + 1]
            if after is None:
                after = pos + 2
            pos = target
            continue
        if length & 0xc0:
            raise ValueError("unsupported DNS label")
        pos += 1
        if length == 0:
            return (".".join(labels) or ".", pos if after is None else after)
        if length > 63 or pos + length > len(message):
            raise ValueError("invalid DNS label length")
        labels.append(message[pos:pos+length].decode("ascii", errors="replace"))
        pos += length
    raise ValueError("DNS name too deep")


def _dns(data: bytes, when: float, src: str, dst: str, transport: str):
    if transport == "tcp":
        if len(data) < 2:
            return None
        size = int.from_bytes(data[:2], "big")
        if len(data) < size + 2:
            return None
        data = data[2:2+size]
    if len(data) < 12:
        return None
    message_id, flags, questions, answers = struct.unpack_from("!HHHH", data)
    if questions > 30 or answers > 120:
        return None
    pos = 12
    qs: list[dict] = []
    response: list[dict] = []
    try:
        for _ in range(questions):
            domain, pos = _dns_name(data, pos)
            if pos + 4 > len(data):
                return None
            qtype, qclass = struct.unpack_from("!HH", data, pos)
            pos += 4
            qs.append({"name": domain, "type": qtype, "class": qclass})
        for _ in range(answers):
            domain, pos = _dns_name(data, pos)
            if pos + 10 > len(data):
                return None
            rtype, rclass, ttl, length = struct.unpack_from("!HHIH", data, pos)
            pos += 10
            if pos + length > len(data):
                return None
            raw = data[pos:pos+length]
            pos += length
            address = None
            if rtype == 1 and length == 4:
                address = str(ipaddress.IPv4Address(raw))
            elif rtype == 28 and length == 16:
                address = str(ipaddress.IPv6Address(raw))
            elif rtype == 5:
                address, _ = _dns_name(data, pos-length)
            if address is not None:
                response.append({"name": domain, "type": rtype, "value": address, "ttl": ttl})
    except (ValueError, struct.error):
        return None
    return {"timestamp": when, "source": src, "destination": dst,
            "protocol": transport, "id": message_id, "response": bool(flags & 0x8000),
            "rcode": flags & 15, "questions": qs, "answers": response}


def _tls_hello(data: bytes):
    if len(data) < 9 or data[0] != 22:
        return None
    size = int.from_bytes(data[3:5], "big")
    if size < 4 or len(data) < 5 + size:
        return None
    hello = data[5:5+size]
    kind = hello[0]
    length = int.from_bytes(hello[1:4], "big")
    if kind not in (1, 2) or len(hello) < 4 + length:
        return None
    body = hello[4:4+length]
    if len(body) < 38:
        return None
    try:
        ptr = 34
        sid = body[ptr]
        ptr += sid + 1
        if kind == 2:  # ServerHello
            if ptr + 3 > len(body):
                return None
            cipher = int.from_bytes(body[ptr:ptr+2], "big")
            return {"kind": "server_hello", "cipher_suite": f"0x{cipher:04x}",
                    "legacy_version": f"0x{int.from_bytes(body[:2], 'big'):04x}"}
        if ptr + 2 > len(body):
            return None
        ciphers = int.from_bytes(body[ptr:ptr+2], "big")
        ptr += 2 + ciphers
        if ptr >= len(body):
            return None
        comp = body[ptr]
        ptr += 1 + comp
        if ptr + 2 > len(body):
            return None
        end = min(len(body), ptr + 2 + int.from_bytes(body[ptr:ptr+2], "big"))
        ptr += 2
        info = {"kind": "client_hello", "sni": None, "alpn": [],
                "tls_versions": []}
        while ptr + 4 <= end:
            ext_type, ext_len = struct.unpack_from("!HH", body, ptr)
            ptr += 4
            ext = body[ptr:ptr+ext_len]
            ptr += ext_len
            if len(ext) != ext_len:
                break
            if ext_type == 0 and len(ext) >= 5:
                if ext[2] == 0:
                    n = int.from_bytes(ext[3:5], "big")
                    if 5 + n <= len(ext):
                        info["sni"] = ext[5:5+n].decode("ascii", errors="replace")
            elif ext_type == 16 and len(ext) >= 2:
                p = 2
                while p < len(ext):
                    n = ext[p]
                    p += 1
                    if n == 0 or p + n > len(ext):
                        break
                    info["alpn"].append(ext[p:p+n].decode("ascii", errors="replace"))
                    p += n
            elif ext_type == 43 and ext:
                n = ext[0]
                for q in range(1, min(1+n, len(ext)-1), 2):
                    info["tls_versions"].append(
                        f"0x{int.from_bytes(ext[q:q+2], 'big'):04x}"
                    )
        return info
    except (IndexError, struct.error, ValueError):
        return None


def _epoch(value) -> float | None:
    try:
        if isinstance(value, (int, float)):
            return float(value)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def derive_network_evidence(root: Path) -> dict:
    """Create bounded, independently reproducible derived files for ZIP export."""
    root = Path(root)
    dns: list[dict] = []
    tls: list[dict] = []
    packets_seen = 0
    unsupported = 0
    fingerprints: set[tuple] = set()
    for when, link, frame in _packets(root / INPUT_PCAP):
        packets_seen += 1
        ip = _ip_packet(link, frame)
        if ip is None:
            unsupported += 1
            continue
        proto, src, dst, payload = ip
        traffic = _transport(proto, payload)
        if traffic is None:
            continue
        src_port, dst_port, body, protocol = traffic
        if src_port == 53 or dst_port == 53:
            rec = _dns(body, when, src, dst, protocol)
            if rec is not None:
                dns.append(rec)
        if protocol == "tcp" and (src_port == 443 or dst_port == 443):
            info = _tls_hello(body)
            if info is not None:
                ident = (src, src_port, dst, dst_port, info["kind"])
                if ident in fingerprints:
                    continue
                fingerprints.add(ident)
                tls.append({"timestamp": when, "source": src, "source_port": src_port,
                            "destination": dst, "destination_port": dst_port,
                            **info, "source_evidence": "pcap_handshake"})
    actions = sorted(
        [(ts, action) for action in _jsonl(root / INPUT_ACTIONS)
         if (ts := _epoch(action.get("host_utc"))) is not None],
        key=lambda p: p[0],
    )
    import bisect
    action_times = [ts for ts, _ in actions]
    links: list[dict] = []
    timings: list[dict] = []
    for http in _jsonl(root / INPUT_HTTP):
        ts = _epoch(http.get("timestamp_start"))
        if ts is None:
            continue
        response = http.get("response") or {}
        end = _epoch(http.get("timestamp_end"))
        tx_id = str(http.get("transaction_id") or "")
        timings.append({
            "transaction_id": tx_id, "url": http.get("url"),
            "started_utc": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
            "http_duration_ms": max(0, round((end - ts) * 1000, 3)) if end is not None else None,
            "http_status": response.get("status_code"),
            "request_bytes": (http.get("request") or {}).get("body", {}).get("size"),
            "response_bytes": response.get("body", {}).get("size"),
            "http_error": http.get("error"),
            "measurement": "recorded_http_transaction",
        })
        ix = bisect.bisect_right(action_times, ts) - 1
        if ix >= 0:
            action_time, action = actions[ix]
            delta = round((ts - action_time) * 1000, 3)
            if 0 <= delta <= 10000:
                links.append({
                    "transaction_id": tx_id, "action_id": action.get("action_id"),
                    "action": action.get("action"),
                    "delta_ms": delta, "relationship": "temporal_candidate",
                    "note": "Time proximity does not establish causality",
                })

    files = {
        DNS_PATH: dns, TLS_PATH: tls, LINKS_PATH: links, TIMINGS_PATH: timings,
    }
    for path, records in files.items():
        _write_jsonl(root / path, records)
    summary = {
        "schema_version": 1, "source_pcap": INPUT_PCAP, "packets_scanned": packets_seen,
        "unsupported_or_fragmented_packets": unsupported,
        "dns_records": len(dns), "tls_hellos": len(tls),
        "http_timings": len(timings), "action_links": len(links),
        "limits": [
            "TLS records spanning packets require reassembly and may be absent",
            "DNS-over-HTTPS and QUIC are not decoded as ordinary DNS/TLS",
            "Action links are time-proximity candidates only",
            "No assertion of screen visual-change latency",
        ],
    }
    path = root / SUMMARY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary
