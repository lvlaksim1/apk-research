from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import ipaddress
import re
from typing import Any


_DNS_TYPES = {
    1: "A",
    2: "NS",
    5: "CNAME",
    6: "SOA",
    12: "PTR",
    15: "MX",
    16: "TXT",
    28: "AAAA",
    33: "SRV",
    41: "OPT",
    64: "SVCB",
    65: "HTTPS",
}

_TLS_VERSIONS = {
    0x0301: "TLS1.0",
    0x0302: "TLS1.1",
    0x0303: "TLS1.2/1.3-record",
    0x0304: "TLS1.3",
}

_HTTP_REQUEST = re.compile(
    rb"^([A-Z]{3,20})[ ]([^\r\n ]{1,8192})[ ]HTTP/(1\.[01])\r\n"
)
_HTTP_RESPONSE = re.compile(
    rb"^HTTP/(1\.[01])[ ]([0-9]{3})(?:[ ]([^\r\n]{0,512}))?\r\n"
)


class ProtocolParseError(ValueError):
    pass


def _packet_id(packet: dict[str, Any]) -> str:
    return str(packet.get("packet_id") or "")


def _direction(packet: dict[str, Any]) -> str:
    value = str(packet.get("direction") or "unknown")
    return value if value in {"outbound", "inbound"} else "unknown"


def _dns_name(
    data: bytes,
    offset: int,
    *,
    depth: int = 0,
    visited: set[int] | None = None,
) -> tuple[str, int]:
    if depth > 20:
        raise ProtocolParseError("DNS compression depth exceeded")
    if visited is None:
        visited = set()
    labels: list[str] = []
    cursor = offset
    next_offset: int | None = None
    while True:
        if cursor >= len(data):
            raise ProtocolParseError("truncated DNS name")
        length = data[cursor]
        if length & 0xC0 == 0xC0:
            if cursor + 1 >= len(data):
                raise ProtocolParseError("truncated DNS compression pointer")
            pointer = ((length & 0x3F) << 8) | data[cursor + 1]
            if pointer >= len(data) or pointer in visited:
                raise ProtocolParseError("invalid DNS compression pointer")
            visited.add(pointer)
            suffix, _ = _dns_name(
                data,
                pointer,
                depth=depth + 1,
                visited=visited,
            )
            if suffix:
                labels.append(suffix)
            cursor += 2
            next_offset = cursor
            break
        if length & 0xC0:
            raise ProtocolParseError("unsupported DNS label encoding")
        cursor += 1
        if length == 0:
            next_offset = cursor
            break
        if length > 63 or cursor + length > len(data):
            raise ProtocolParseError("truncated DNS label")
        label = data[cursor : cursor + length].decode(
            "ascii",
            errors="replace",
        )
        labels.append(label)
        cursor += length
    return ".".join(item for item in labels if item), int(next_offset)


def _dns_record_value(
    data: bytes,
    rtype: int,
    rdata_offset: int,
    rdlength: int,
) -> str | None:
    raw = data[rdata_offset : rdata_offset + rdlength]
    try:
        if rtype == 1 and len(raw) == 4:
            return str(ipaddress.IPv4Address(raw))
        if rtype == 28 and len(raw) == 16:
            return str(ipaddress.IPv6Address(raw))
        if rtype in {2, 5, 12}:
            value, _ = _dns_name(data, rdata_offset)
            return value or None
        if rtype == 15 and len(raw) >= 3:
            preference = int.from_bytes(raw[:2], "big")
            exchange, _ = _dns_name(data, rdata_offset + 2)
            return f"{preference} {exchange}".strip()
    except (ProtocolParseError, ValueError):
        return None
    return None


def parse_dns_message(
    payload: bytes,
    *,
    tcp: bool = False,
) -> dict[str, Any] | None:
    """Parse one fully captured DNS message without synthesizing missing bytes."""

    data = payload
    tcp_declared_length: int | None = None
    if tcp:
        if len(data) < 2:
            return None
        tcp_declared_length = int.from_bytes(data[:2], "big")
        if tcp_declared_length < 12 or len(data) < 2 + tcp_declared_length:
            return None
        data = data[2 : 2 + tcp_declared_length]
    if len(data) < 12:
        return None

    message_id = int.from_bytes(data[0:2], "big")
    flags = int.from_bytes(data[2:4], "big")
    counts = [
        int.from_bytes(data[index : index + 2], "big")
        for index in (4, 6, 8, 10)
    ]
    if any(value > 256 for value in counts):
        return None

    cursor = 12
    questions: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    authorities: list[dict[str, Any]] = []
    additionals: list[dict[str, Any]] = []

    try:
        for _ in range(counts[0]):
            name, cursor = _dns_name(data, cursor)
            if cursor + 4 > len(data):
                raise ProtocolParseError("truncated DNS question")
            qtype = int.from_bytes(data[cursor : cursor + 2], "big")
            qclass = int.from_bytes(data[cursor + 2 : cursor + 4], "big")
            cursor += 4
            questions.append(
                {
                    "name": name,
                    "type": _DNS_TYPES.get(qtype, str(qtype)),
                    "type_code": qtype,
                    "class": qclass,
                }
            )

        for count, target in zip(
            counts[1:],
            (answers, authorities, additionals),
        ):
            for _ in range(count):
                name, cursor = _dns_name(data, cursor)
                if cursor + 10 > len(data):
                    raise ProtocolParseError("truncated DNS resource record")
                rtype = int.from_bytes(data[cursor : cursor + 2], "big")
                rclass = int.from_bytes(data[cursor + 2 : cursor + 4], "big")
                ttl = int.from_bytes(data[cursor + 4 : cursor + 8], "big")
                rdlength = int.from_bytes(data[cursor + 8 : cursor + 10], "big")
                cursor += 10
                if cursor + rdlength > len(data):
                    raise ProtocolParseError("truncated DNS resource data")
                value = _dns_record_value(data, rtype, cursor, rdlength)
                target.append(
                    {
                        "name": name,
                        "type": _DNS_TYPES.get(rtype, str(rtype)),
                        "type_code": rtype,
                        "class": rclass,
                        "ttl": ttl,
                        "data": value,
                        "rdata_length": rdlength,
                    }
                )
                cursor += rdlength
    except ProtocolParseError:
        return None

    return {
        "id": message_id,
        "kind": "response" if flags & 0x8000 else "query",
        "opcode": (flags >> 11) & 0x0F,
        "rcode": flags & 0x0F,
        "truncated_flag": bool(flags & 0x0200),
        "recursion_desired": bool(flags & 0x0100),
        "recursion_available": bool(flags & 0x0080),
        "questions": questions,
        "answers": answers,
        "authorities": authorities,
        "additionals": additionals,
        "tcp_declared_length": tcp_declared_length,
        "captured_message_length": len(data),
        "complete": True,
    }


def _tls_extensions(data: bytes) -> dict[int, list[bytes]]:
    values: dict[int, list[bytes]] = defaultdict(list)
    cursor = 0
    while cursor + 4 <= len(data):
        extension_type = int.from_bytes(data[cursor : cursor + 2], "big")
        length = int.from_bytes(data[cursor + 2 : cursor + 4], "big")
        cursor += 4
        if cursor + length > len(data):
            break
        values[extension_type].append(data[cursor : cursor + length])
        cursor += length
    return dict(values)


def _tls_sni(extension: bytes) -> str | None:
    if len(extension) < 2:
        return None
    total = int.from_bytes(extension[:2], "big")
    cursor = 2
    end = min(len(extension), 2 + total)
    while cursor + 3 <= end:
        name_type = extension[cursor]
        length = int.from_bytes(extension[cursor + 1 : cursor + 3], "big")
        cursor += 3
        if cursor + length > end:
            return None
        raw = extension[cursor : cursor + length]
        cursor += length
        if name_type == 0:
            text = raw.decode("ascii", errors="ignore").strip()
            return text or None
    return None


def _tls_alpn(extension: bytes) -> list[str]:
    if len(extension) < 2:
        return []
    total = int.from_bytes(extension[:2], "big")
    cursor = 2
    end = min(len(extension), 2 + total)
    values: list[str] = []
    while cursor < end:
        length = extension[cursor]
        cursor += 1
        if cursor + length > end:
            break
        text = extension[cursor : cursor + length].decode(
            "ascii",
            errors="ignore",
        ).strip()
        cursor += length
        if text:
            values.append(text)
    return values


def _tls_supported_versions(extension: bytes) -> list[str]:
    if not extension:
        return []
    if len(extension) == 2:
        code = int.from_bytes(extension, "big")
        return [_TLS_VERSIONS.get(code, f"0x{code:04x}")]
    length = extension[0]
    end = min(len(extension), 1 + length)
    values: list[str] = []
    cursor = 1
    while cursor + 2 <= end:
        code = int.from_bytes(extension[cursor : cursor + 2], "big")
        values.append(_TLS_VERSIONS.get(code, f"0x{code:04x}"))
        cursor += 2
    return values


def _parse_client_hello(body: bytes) -> dict[str, Any] | None:
    if len(body) < 34:
        return None
    legacy_version = int.from_bytes(body[:2], "big")
    cursor = 34
    if cursor >= len(body):
        return None
    session_length = body[cursor]
    cursor += 1 + session_length
    if cursor + 2 > len(body):
        return None
    cipher_length = int.from_bytes(body[cursor : cursor + 2], "big")
    cursor += 2
    if cursor + cipher_length > len(body):
        return None
    ciphers = [
        int.from_bytes(body[index : index + 2], "big")
        for index in range(cursor, cursor + cipher_length, 2)
        if index + 2 <= cursor + cipher_length
    ]
    cursor += cipher_length
    if cursor >= len(body):
        return None
    compression_length = body[cursor]
    cursor += 1 + compression_length
    extensions: dict[int, list[bytes]] = {}
    if cursor + 2 <= len(body):
        extension_length = int.from_bytes(body[cursor : cursor + 2], "big")
        cursor += 2
        extensions = _tls_extensions(body[cursor : cursor + extension_length])

    sni = None
    if extensions.get(0):
        sni = _tls_sni(extensions[0][0])
    alpn: list[str] = []
    if extensions.get(16):
        alpn = _tls_alpn(extensions[16][0])
    versions: list[str] = []
    if extensions.get(43):
        versions = _tls_supported_versions(extensions[43][0])
    return {
        "handshake_type": "client-hello",
        "legacy_version": _TLS_VERSIONS.get(
            legacy_version,
            f"0x{legacy_version:04x}",
        ),
        "supported_versions": versions,
        "sni": sni,
        "alpn": alpn,
        "cipher_suites": [f"0x{value:04x}" for value in ciphers],
    }


def _parse_server_hello(body: bytes) -> dict[str, Any] | None:
    if len(body) < 38:
        return None
    legacy_version = int.from_bytes(body[:2], "big")
    cursor = 34
    session_length = body[cursor]
    cursor += 1 + session_length
    if cursor + 3 > len(body):
        return None
    cipher = int.from_bytes(body[cursor : cursor + 2], "big")
    cursor += 3
    extensions: dict[int, list[bytes]] = {}
    if cursor + 2 <= len(body):
        extension_length = int.from_bytes(body[cursor : cursor + 2], "big")
        cursor += 2
        extensions = _tls_extensions(body[cursor : cursor + extension_length])
    versions: list[str] = []
    if extensions.get(43):
        versions = _tls_supported_versions(extensions[43][0])
    alpn: list[str] = []
    if extensions.get(16):
        alpn = _tls_alpn(extensions[16][0])
    return {
        "handshake_type": "server-hello",
        "legacy_version": _TLS_VERSIONS.get(
            legacy_version,
            f"0x{legacy_version:04x}",
        ),
        "selected_version": versions[0] if versions else None,
        "selected_cipher": f"0x{cipher:04x}",
        "alpn": alpn,
    }


def parse_tls_records(payload: bytes) -> dict[str, Any] | None:
    """Parse complete TLS records/hellos present in the supplied captured bytes."""

    if len(payload) < 5:
        return None
    if payload[0] not in {20, 21, 22, 23} or payload[1] != 3:
        return None

    records: list[dict[str, Any]] = []
    hellos: list[dict[str, Any]] = []
    cursor = 0
    while cursor + 5 <= len(payload):
        content_type = payload[cursor]
        version = int.from_bytes(payload[cursor + 1 : cursor + 3], "big")
        length = int.from_bytes(payload[cursor + 3 : cursor + 5], "big")
        record_start = cursor
        cursor += 5
        if length > 1 << 15 or cursor + length > len(payload):
            records.append(
                {
                    "content_type": content_type,
                    "record_version": _TLS_VERSIONS.get(
                        version,
                        f"0x{version:04x}",
                    ),
                    "declared_length": length,
                    "complete": False,
                    "offset": record_start,
                }
            )
            break
        body = payload[cursor : cursor + length]
        records.append(
            {
                "content_type": content_type,
                "record_version": _TLS_VERSIONS.get(
                    version,
                    f"0x{version:04x}",
                ),
                "declared_length": length,
                "complete": True,
                "offset": record_start,
            }
        )
        if content_type == 22:
            handshake_cursor = 0
            while handshake_cursor + 4 <= len(body):
                handshake_type = body[handshake_cursor]
                handshake_length = int.from_bytes(
                    body[handshake_cursor + 1 : handshake_cursor + 4],
                    "big",
                )
                handshake_cursor += 4
                if handshake_cursor + handshake_length > len(body):
                    break
                message = body[
                    handshake_cursor : handshake_cursor + handshake_length
                ]
                if handshake_type == 1:
                    parsed = _parse_client_hello(message)
                    if parsed:
                        hellos.append(parsed)
                elif handshake_type == 2:
                    parsed = _parse_server_hello(message)
                    if parsed:
                        hellos.append(parsed)
                handshake_cursor += handshake_length
        cursor += length

    if not records:
        return None
    client = next(
        (value for value in hellos if value.get("handshake_type") == "client-hello"),
        None,
    )
    server = next(
        (value for value in hellos if value.get("handshake_type") == "server-hello"),
        None,
    )
    return {
        "records": records,
        "hellos": hellos,
        "client_hello": client,
        "server_hello": server,
        "complete_record_count": sum(
            1 for record in records if record.get("complete") is True
        ),
        "incomplete_record_observed": any(
            record.get("complete") is False for record in records
        ),
    }


def parse_http_message(payload: bytes) -> dict[str, Any] | None:
    """Parse one complete cleartext HTTP/1.x header block or the HTTP/2 preface."""

    if payload.startswith(b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"):
        return {
            "kind": "http2-preface",
            "protocol": "h2c",
            "complete_headers": True,
        }
    header_end = payload.find(b"\r\n\r\n")
    if header_end < 0 or header_end > 128 * 1024:
        return None
    header_block = payload[: header_end + 4]
    request = _HTTP_REQUEST.match(header_block)
    response = _HTTP_RESPONSE.match(header_block)
    if request is None and response is None:
        return None

    lines = header_block[:-4].split(b"\r\n")
    headers: dict[str, str] = {}
    for raw in lines[1:201]:
        if b":" not in raw:
            continue
        name, value = raw.split(b":", 1)
        key = name.decode("ascii", errors="ignore").strip().lower()
        text = value.decode("latin1", errors="replace").strip()
        if key and key not in headers:
            headers[key] = text[:8192]

    common = {
        "protocol": "http1",
        "version": (
            request.group(3).decode("ascii")
            if request is not None
            else response.group(1).decode("ascii")
        ),
        "host": headers.get("host"),
        "content_type": headers.get("content-type"),
        "content_length": headers.get("content-length"),
        "transfer_encoding": headers.get("transfer-encoding"),
        "connection": headers.get("connection"),
        "upgrade": headers.get("upgrade"),
        "complete_headers": True,
        "header_bytes": header_end + 4,
    }
    if request is not None:
        common.update(
            {
                "kind": "request",
                "method": request.group(1).decode("ascii"),
                "target": request.group(2).decode(
                    "latin1",
                    errors="replace",
                ),
            }
        )
    else:
        common.update(
            {
                "kind": "response",
                "status": int(response.group(2)),
                "reason": (
                    response.group(3).decode("latin1", errors="replace")
                    if response.group(3)
                    else ""
                ),
            }
        )
    return common


def _copy_protocol_summary(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if key not in {"records", "cipher_suites"}
    }


@dataclass
class FlowProtocolAnalyzer:
    protocol: str
    max_stream_bytes: int = 2 * 1024 * 1024
    _segments: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _stored_bytes: dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )

    def observe(
        self,
        packet: dict[str, Any],
        payload: bytes,
    ) -> None:
        protocol = str(packet.get("protocol") or self.protocol).lower()
        src_port = packet.get("src_port")
        dst_port = packet.get("dst_port")
        direction = _direction(packet)

        if 53 in {src_port, dst_port}:
            dns = parse_dns_message(payload, tcp=protocol == "tcp")
            if dns is not None:
                packet["dns_message"] = dns
                questions = dns.get("questions") or []
                if questions and not packet.get("dns_query"):
                    packet["dns_query"] = str(questions[0].get("name") or "") or None

        if protocol == "tcp":
            tls = parse_tls_records(payload)
            if tls is not None:
                packet["tls_metadata"] = tls
                client = tls.get("client_hello")
                server = tls.get("server_hello")
                if isinstance(client, dict):
                    if client.get("sni") and not packet.get("tls_sni"):
                        packet["tls_sni"] = client.get("sni")
                    packet["tls_alpn"] = list(client.get("alpn") or [])
                    packet["tls_supported_versions"] = list(
                        client.get("supported_versions") or []
                    )
                if isinstance(server, dict):
                    packet["tls_selected_version"] = server.get("selected_version")
                    packet["tls_selected_cipher"] = server.get("selected_cipher")
                if packet.get("application_protocol") in {None, ""}:
                    packet["application_protocol"] = "tls"

            http = parse_http_message(payload)
            if http is not None:
                packet["http_metadata"] = http
                packet["http_method"] = http.get("method")
                packet["http_target"] = http.get("target")
                packet["http_status"] = http.get("status")
                packet["http_host"] = http.get("host")
                if packet.get("application_protocol") in {None, ""}:
                    packet["application_protocol"] = str(
                        http.get("protocol") or "http1"
                    )

            if packet.get("tcp_header_valid") is True and payload:
                remaining = max(
                    0,
                    self.max_stream_bytes - self._stored_bytes[direction],
                )
                if remaining:
                    flags = {
                        str(value)
                        for value in packet.get("tcp_flags") or []
                    }
                    sequence = int(packet.get("tcp_sequence") or 0)
                    payload_sequence = sequence + (1 if "SYN" in flags else 0)
                    captured = payload[:remaining]
                    self._segments[direction].append(
                        {
                            "sequence": payload_sequence,
                            "payload": captured,
                            "packet_id": _packet_id(packet),
                        }
                    )
                    self._stored_bytes[direction] += len(captured)

    @staticmethod
    def _tcp_analysis(packets: list[dict[str, Any]]) -> dict[str, Any]:
        tcp_packets = [
            packet
            for packet in packets
            if str(packet.get("protocol") or "").lower() == "tcp"
            and packet.get("tcp_header_valid") is True
        ]
        plain_syn = [
            packet
            for packet in tcp_packets
            if "SYN" in set(packet.get("tcp_flags") or [])
            and "ACK" not in set(packet.get("tcp_flags") or [])
        ]
        fin = [
            packet
            for packet in tcp_packets
            if "FIN" in set(packet.get("tcp_flags") or [])
        ]
        rst = [
            packet
            for packet in tcp_packets
            if "RST" in set(packet.get("tcp_flags") or [])
        ]
        result: dict[str, Any] = {
            "applicable": True,
            "packet_count": len(tcp_packets),
            "capture_start_status": (
                "syn-observed"
                if plain_syn
                else "capture-may-start-midstream"
            ),
            "capture_end_status": (
                "reset-observed"
                if rst
                else "fin-observed"
                if fin
                else "capture-may-end-midstream"
            ),
            "missing_start_possible": not bool(plain_syn),
            "missing_end_possible": not bool(fin or rst),
            "directions": {},
            "repeated_sequence_range_count": 0,
            "overlapping_sequence_range_count": 0,
            "sequence_gap_observation_count": 0,
            "repeated_ack_observation_count": 0,
            "zero_window_packet_count": 0,
            "evidence_semantics": (
                "sequence gaps, overlaps and repeated ACK values are capture observations; "
                "they do not by themselves prove packet loss, network retransmission, "
                "or events outside the capture"
            ),
        }

        for direction in ("outbound", "inbound", "unknown"):
            items = [packet for packet in tcp_packets if _direction(packet) == direction]
            if not items:
                continue
            seen_ranges: set[tuple[int, int]] = set()
            intervals: list[tuple[int, int]] = []
            highest_end: int | None = None
            repeated_ranges: list[dict[str, Any]] = []
            overlaps: list[dict[str, Any]] = []
            gaps: list[dict[str, Any]] = []
            repeated_acks: list[dict[str, Any]] = []
            last_ack: int | None = None
            windows: list[int] = []
            zero_window_ids: list[str] = []

            for packet in items:
                packet.setdefault("tcp_analysis_flags", [])
                flags = set(packet.get("tcp_flags") or [])
                window = packet.get("tcp_window")
                if window is not None:
                    windows.append(int(window))
                    if int(window) == 0:
                        packet["tcp_analysis_flags"].append("zero-window")
                        zero_window_ids.append(_packet_id(packet))

                ack = packet.get("tcp_acknowledgment")
                if "ACK" in flags and ack is not None:
                    ack_value = int(ack)
                    if last_ack is not None and ack_value == last_ack:
                        packet["tcp_analysis_flags"].append("repeated-ack-value")
                        repeated_acks.append(
                            {"packet_id": _packet_id(packet), "ack": ack_value}
                        )
                    last_ack = ack_value

                payload_length = int(packet.get("tcp_payload_length") or 0)
                if payload_length <= 0:
                    continue
                sequence = int(packet.get("tcp_sequence") or 0)
                start = sequence + (1 if "SYN" in flags else 0)
                end = start + payload_length
                current = (start, end)
                if current in seen_ranges:
                    packet["tcp_analysis_flags"].append("repeated-sequence-range")
                    repeated_ranges.append(
                        {
                            "packet_id": _packet_id(packet),
                            "start": start,
                            "end": end,
                        }
                    )
                elif any(start < old_end and end > old_start for old_start, old_end in intervals):
                    packet["tcp_analysis_flags"].append("overlapping-sequence-range")
                    overlaps.append(
                        {
                            "packet_id": _packet_id(packet),
                            "start": start,
                            "end": end,
                        }
                    )
                if highest_end is not None and start > highest_end:
                    packet["tcp_analysis_flags"].append(
                        "sequence-gap-after-previous-observed-data"
                    )
                    gaps.append(
                        {
                            "packet_id": _packet_id(packet),
                            "start": highest_end,
                            "end": start,
                            "bytes": start - highest_end,
                        }
                    )
                seen_ranges.add(current)
                intervals.append(current)
                highest_end = end if highest_end is None else max(highest_end, end)

            direction_result = {
                "packet_count": len(items),
                "payload_packet_count": sum(
                    1 for packet in items if int(packet.get("tcp_payload_length") or 0) > 0
                ),
                "payload_bytes_observed": sum(
                    int(packet.get("tcp_payload_length") or 0) for packet in items
                ),
                "repeated_sequence_ranges": repeated_ranges,
                "overlapping_sequence_ranges": overlaps,
                "sequence_gap_observations": gaps,
                "repeated_ack_observations": repeated_acks,
                "window_min": min(windows) if windows else None,
                "window_max": max(windows) if windows else None,
                "zero_window_packet_ids": zero_window_ids,
            }
            result["directions"][direction] = direction_result
            result["repeated_sequence_range_count"] += len(repeated_ranges)
            result["overlapping_sequence_range_count"] += len(overlaps)
            result["sequence_gap_observation_count"] += len(gaps)
            result["repeated_ack_observation_count"] += len(repeated_acks)
            result["zero_window_packet_count"] += len(zero_window_ids)
        return result

    def _contiguous_stream(self, direction: str) -> dict[str, Any]:
        segments = sorted(
            self._segments.get(direction, []),
            key=lambda value: (int(value["sequence"]), str(value["packet_id"])),
        )
        if not segments:
            return {
                "bytes": b"",
                "packet_ids": [],
                "gap_observed": False,
                "overlap_observed": False,
            }
        output = bytearray()
        packet_ids: list[str] = []
        base = int(segments[0]["sequence"])
        end = base
        gap = False
        overlap = False
        for segment in segments:
            start = int(segment["sequence"])
            payload = bytes(segment["payload"])
            segment_end = start + len(payload)
            if start > end:
                gap = True
                break
            if start < end:
                overlap = True
                trim = end - start
                if trim >= len(payload):
                    continue
                payload = payload[trim:]
                start = end
            output.extend(payload)
            end = start + len(payload)
            packet_id = str(segment.get("packet_id") or "")
            if packet_id:
                packet_ids.append(packet_id)
            if len(output) >= self.max_stream_bytes:
                break
        return {
            "bytes": bytes(output[: self.max_stream_bytes]),
            "packet_ids": packet_ids,
            "gap_observed": gap,
            "overlap_observed": overlap,
            "first_sequence": base,
            "last_contiguous_sequence": end,
        }

    @staticmethod
    def _dns_transactions(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for packet in packets:
            dns = packet.get("dns_message")
            if isinstance(dns, dict):
                groups[int(dns.get("id") or 0)].append(packet)
        transactions: list[dict[str, Any]] = []
        for message_id, items in groups.items():
            queries = [item for item in items if item["dns_message"].get("kind") == "query"]
            responses = [item for item in items if item["dns_message"].get("kind") == "response"]
            if len(queries) == 1 and len(responses) == 1:
                query = queries[0]
                response = responses[0]
                questions = query["dns_message"].get("questions") or []
                transactions.append(
                    {
                        "id": message_id,
                        "status": "query-response-observed",
                        "query_packet_id": _packet_id(query),
                        "response_packet_id": _packet_id(response),
                        "query_name": (
                            str(questions[0].get("name") or "")
                            if questions
                            else ""
                        ),
                        "confidence": "HIGH",
                        "basis": "matching DNS transaction id in one selected flow",
                    }
                )
            else:
                transactions.append(
                    {
                        "id": message_id,
                        "status": "partial-or-ambiguous",
                        "query_packet_ids": [_packet_id(item) for item in queries],
                        "response_packet_ids": [_packet_id(item) for item in responses],
                        "confidence": "LOW",
                        "basis": "capture contains no unique query/response pair for this id",
                    }
                )
        return sorted(transactions, key=lambda value: int(value["id"]))

    @staticmethod
    def _http_transactions(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        requests = [
            packet
            for packet in packets
            if isinstance(packet.get("http_metadata"), dict)
            and packet["http_metadata"].get("kind") == "request"
        ]
        responses = [
            packet
            for packet in packets
            if isinstance(packet.get("http_metadata"), dict)
            and packet["http_metadata"].get("kind") == "response"
        ]
        if len(requests) != 1 or len(responses) != 1:
            return []
        request = requests[0]
        response = responses[0]
        if _direction(request) == _direction(response):
            return []
        return [
            {
                "status": "single-unambiguous-observed-pair",
                "request_packet_id": _packet_id(request),
                "response_packet_id": _packet_id(response),
                "method": request["http_metadata"].get("method"),
                "target": request["http_metadata"].get("target"),
                "status_code": response["http_metadata"].get("status"),
                "confidence": "HIGH",
                "basis": "exactly one complete cleartext request and one complete cleartext response in opposite directions",
            }
        ]

    def finalize(self, packets: list[dict[str, Any]]) -> dict[str, Any]:
        protocol = str(self.protocol or "").lower()
        tcp = (
            self._tcp_analysis(packets)
            if protocol == "tcp"
            else {"applicable": False, "reason": "not-tcp"}
        )

        stream_observations: list[dict[str, Any]] = []
        for direction in ("outbound", "inbound"):
            stream = self._contiguous_stream(direction)
            data = bytes(stream.get("bytes") or b"")
            if not data:
                continue
            tls = parse_tls_records(data)
            http = parse_http_message(data)
            observation: dict[str, Any] = {
                "direction": direction,
                "bytes_analyzed": len(data),
                "source_packet_ids": list(stream.get("packet_ids") or []),
                "gap_observed": bool(stream.get("gap_observed")),
                "overlap_observed": bool(stream.get("overlap_observed")),
                "basis": "contiguous captured TCP payload from first observed sequence until the first observed gap or memory bound",
            }
            if tls is not None:
                observation["tls"] = {
                    "client_hello": tls.get("client_hello"),
                    "server_hello": tls.get("server_hello"),
                    "complete_record_count": tls.get("complete_record_count"),
                    "incomplete_record_observed": tls.get("incomplete_record_observed"),
                }
            if http is not None:
                observation["http"] = http
            if "tls" in observation or "http" in observation:
                stream_observations.append(observation)

        dns_messages: list[dict[str, Any]] = []
        tls_messages: list[dict[str, Any]] = []
        http_messages: list[dict[str, Any]] = []
        quic_versions: set[str] = set()
        quic_types: set[str] = set()
        quic_sni: set[str] = set()
        quic_alpn: set[str] = set()
        http3_observed = False

        for packet in packets:
            packet_id = _packet_id(packet)
            dns = packet.get("dns_message")
            if isinstance(dns, dict):
                dns_messages.append(
                    {
                        "packet_id": packet_id,
                        "direction": _direction(packet),
                        **dns,
                    }
                )
            tls = packet.get("tls_metadata")
            if isinstance(tls, dict):
                tls_messages.append(
                    {
                        "packet_id": packet_id,
                        "direction": _direction(packet),
                        "client_hello": tls.get("client_hello"),
                        "server_hello": tls.get("server_hello"),
                        "complete_record_count": tls.get("complete_record_count"),
                        "incomplete_record_observed": tls.get("incomplete_record_observed"),
                    }
                )
            http = packet.get("http_metadata")
            if isinstance(http, dict):
                http_messages.append(
                    {
                        "packet_id": packet_id,
                        "direction": _direction(packet),
                        **http,
                    }
                )
            if packet.get("quic_version"):
                quic_versions.add(str(packet.get("quic_version")))
            if packet.get("quic_packet_type"):
                quic_types.add(str(packet.get("quic_packet_type")))
            if packet.get("quic_sni"):
                quic_sni.add(str(packet.get("quic_sni")))
            for value in packet.get("quic_alpn") or []:
                if value:
                    quic_alpn.add(str(value))
            if str(packet.get("application_protocol") or "") == "http3":
                http3_observed = True

        return {
            "schema_version": "0.1",
            "scope": "selected-flow",
            "evidence_basis": "captured-packets-only",
            "causal_claim": False,
            "transport": tcp,
            "dns": {
                "message_count": len(dns_messages),
                "messages": dns_messages,
                "transactions": self._dns_transactions(packets),
            },
            "tls": {
                "packet_observation_count": len(tls_messages),
                "packet_observations": tls_messages,
                "stream_observations": [
                    value for value in stream_observations if "tls" in value
                ],
                "plaintext_claim": False,
            },
            "quic": {
                "observed": bool(quic_versions or quic_types or quic_sni or quic_alpn),
                "versions": sorted(quic_versions),
                "packet_types": sorted(quic_types),
                "sni": sorted(quic_sni),
                "alpn": sorted(quic_alpn),
                "http3_observed_via_alpn": http3_observed,
                "application_payload_visibility": "encrypted-metadata-only",
            },
            "http": {
                "cleartext_message_count": len(http_messages),
                "messages": http_messages,
                "transactions": self._http_transactions(packets),
                "stream_observations": [
                    value for value in stream_observations if "http" in value
                ],
            },
            "absence_semantics": (
                "absence from this report means only not observed in the selected captured flow; "
                "missing traffic, plaintext and causality are never synthesized"
            ),
        }


def protocol_packet_label(packet: dict[str, Any]) -> str:
    parts: list[str] = []
    dns = packet.get("dns_message")
    if isinstance(dns, dict):
        questions = dns.get("questions") or []
        name = str(questions[0].get("name") or "") if questions else ""
        parts.append(f"DNS-{dns.get('kind')}{':' + name if name else ''}")
    tls = packet.get("tls_metadata")
    if isinstance(tls, dict):
        client = tls.get("client_hello")
        server = tls.get("server_hello")
        if isinstance(client, dict):
            alpn = ",".join(str(value) for value in client.get("alpn") or [])
            parts.append("TLS ClientHello" + (f" ALPN={alpn}" if alpn else ""))
        if isinstance(server, dict):
            parts.append(
                "TLS ServerHello"
                + (f" {server.get('selected_version')}" if server.get("selected_version") else "")
            )
    http = packet.get("http_metadata")
    if isinstance(http, dict):
        if http.get("kind") == "request":
            parts.append(f"HTTP {http.get('method')} {http.get('target')}")
        elif http.get("kind") == "response":
            parts.append(f"HTTP {http.get('status')}")
        else:
            parts.append(str(http.get("protocol") or "HTTP"))
    flags = [str(value) for value in packet.get("tcp_analysis_flags") or [] if value]
    if flags:
        parts.append("TCP-analysis:" + ",".join(flags))
    return " • ".join(parts)


def format_packet_protocol_evidence(packet: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    flags = [str(value) for value in packet.get("tcp_analysis_flags") or [] if value]
    if flags:
        lines.append("v0.25 TCP observations: " + ", ".join(flags))
    dns = packet.get("dns_message")
    if isinstance(dns, dict):
        lines.append(
            f"DNS: {dns.get('kind')} id={dns.get('id')} rcode={dns.get('rcode')}"
        )
        for question in dns.get("questions") or []:
            lines.append(
                f"  question: {question.get('name') or '—'} {question.get('type') or '—'}"
            )
        for answer in dns.get("answers") or []:
            lines.append(
                f"  answer: {answer.get('name') or '—'} {answer.get('type') or '—'} {answer.get('data') or '—'}"
            )
    tls = packet.get("tls_metadata")
    if isinstance(tls, dict):
        client = tls.get("client_hello")
        server = tls.get("server_hello")
        if isinstance(client, dict):
            lines.append(
                "TLS ClientHello: "
                f"SNI={client.get('sni') or '—'}; "
                f"ALPN={','.join(str(value) for value in client.get('alpn') or []) or '—'}; "
                f"versions={','.join(str(value) for value in client.get('supported_versions') or []) or client.get('legacy_version') or '—'}"
            )
        if isinstance(server, dict):
            lines.append(
                "TLS ServerHello: "
                f"version={server.get('selected_version') or server.get('legacy_version') or '—'}; "
                f"cipher={server.get('selected_cipher') or '—'}"
            )
    http = packet.get("http_metadata")
    if isinstance(http, dict):
        if http.get("kind") == "request":
            lines.append(
                f"Cleartext HTTP request: {http.get('method') or '—'} {http.get('target') or '—'}; host={http.get('host') or '—'}"
            )
        elif http.get("kind") == "response":
            lines.append(
                f"Cleartext HTTP response: {http.get('status') or '—'} {http.get('reason') or ''}".rstrip()
            )
        elif http.get("kind") == "http2-preface":
            lines.append("Cleartext HTTP/2 connection preface observed")
    return lines


def format_protocol_analysis(analysis: dict[str, Any] | None) -> str:
    if not isinstance(analysis, dict):
        return "v0.25 protocol analysis: нет данных"
    lines = [
        "v0.25 — анализ транспорта и протоколов по захваченным пакетам",
        "Граница: отсутствие события в захвате не доказывает, что события не было; пропущенные пакеты и расшифрованный текст не синтезируются.",
    ]
    transport = analysis.get("transport")
    if isinstance(transport, dict) and transport.get("applicable") is True:
        lines.extend(
            [
                "",
                "TCP:",
                f"  начало: {transport.get('capture_start_status') or '—'}",
                f"  окончание: {transport.get('capture_end_status') or '—'}",
                f"  повтор диапазона sequence: {int(transport.get('repeated_sequence_range_count') or 0)}",
                f"  перекрытия sequence: {int(transport.get('overlapping_sequence_range_count') or 0)}",
                f"  наблюдаемые разрывы sequence: {int(transport.get('sequence_gap_observation_count') or 0)}",
                f"  повторные значения ACK: {int(transport.get('repeated_ack_observation_count') or 0)}",
                f"  zero-window: {int(transport.get('zero_window_packet_count') or 0)}",
            ]
        )
    dns = analysis.get("dns") or {}
    lines.append(
        f"DNS: сообщений {int(dns.get('message_count') or 0)}, групп {len(dns.get('transactions') or [])}"
    )
    tls = analysis.get("tls") or {}
    lines.append(
        f"TLS: пакетных наблюдений {int(tls.get('packet_observation_count') or 0)}, потоковых наблюдений {len(tls.get('stream_observations') or [])}; plaintext не заявляется"
    )
    quic = analysis.get("quic") or {}
    lines.append(
        "QUIC/HTTP3: "
        f"observed={bool(quic.get('observed'))}; "
        f"versions={','.join(str(value) for value in quic.get('versions') or []) or '—'}; "
        f"ALPN={','.join(str(value) for value in quic.get('alpn') or []) or '—'}; "
        f"HTTP3={bool(quic.get('http3_observed_via_alpn'))}; application payload encrypted"
    )
    http = analysis.get("http") or {}
    lines.append(
        f"Наблюдаемый открытый HTTP: сообщений {int(http.get('cleartext_message_count') or 0)}, однозначных пар {len(http.get('transactions') or [])}"
    )
    return "\n".join(lines)
