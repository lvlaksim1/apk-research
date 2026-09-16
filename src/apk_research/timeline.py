from __future__ import annotations

import bisect
import ipaddress
import json
import os
import re
import statistics
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from apk_research.session import SessionManager

USER_ACTIONS_ARTIFACT = "02_normalized/user-actions.jsonl"
TIMELINE_ARTIFACT = "02_normalized/research-timeline.json"

_LOGCAT_RE = re.compile(
    r"^\s*(?P<epoch>\d+\.\d+)\s+"
    r"(?P<pid>\d+)\s+"
    r"(?P<tid>\d+)\s+"
    r"(?P<level>[VDIWEF])\s+"
    r"(?P<tag>[^:]+):\s?(?P<message>.*)$"
)
_RELEVANT_LOG_TAGS = {
    "ActivityManager",
    "ActivityTaskManager",
    "WindowManager",
    "ConnectivityService",
    "NetworkMonitor",
    "libc",
    "chromium",
    "Cronet",
}
_ACTION_WINDOW_BEFORE_SECONDS = 0.25
_ACTION_WINDOW_AFTER_SECONDS = 2.0
_MAX_LOG_SAMPLE = 12
_MAX_FLOW_SAMPLE = 12
_MAX_NETWORK_MARKERS = 500


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (
        value.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _iso_epoch(value: float) -> str:
    return _iso_utc(
        datetime.fromtimestamp(
            value,
            tz=timezone.utc,
        )
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (
        FileNotFoundError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return {}
    return value if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return []

    values: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            values.append(value)
    return values


def _clock_alignment(
    root: Path,
    lifecycle: list[dict[str, Any]],
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    target = _read_json(
        root / "02_normalized" / "target.json"
    )
    clock = target.get("clock")
    if isinstance(clock, dict):
        for host_key, target_key in (
            (
                "host_started_utc",
                "target_started_utc",
            ),
            (
                "host_finished_utc",
                "target_finished_utc",
            ),
        ):
            host_value = clock.get(host_key)
            target_value = clock.get(target_key)
            if not host_value or not target_value:
                continue
            try:
                host = _parse_utc(str(host_value))
                target_time = _parse_utc(
                    str(target_value)
                )
            except ValueError:
                continue
            samples.append(
                {
                    "source": "target-clock",
                    "host_utc": _iso_utc(host),
                    "target_utc": _iso_utc(
                        target_time
                    ),
                    "target_minus_host_seconds": (
                        target_time - host
                    ).total_seconds(),
                }
            )

    if not samples:
        for event in lifecycle:
            host_value = event.get("host_utc")
            target_value = event.get("target_utc")
            if not host_value or not target_value:
                continue
            try:
                host = _parse_utc(str(host_value))
                target_time = _parse_utc(
                    str(target_value)
                )
            except ValueError:
                continue
            samples.append(
                {
                    "source": "session-event",
                    "host_utc": _iso_utc(host),
                    "target_utc": _iso_utc(
                        target_time
                    ),
                    "target_minus_host_seconds": (
                        target_time - host
                    ).total_seconds(),
                }
            )

    offsets = [
        float(
            sample["target_minus_host_seconds"]
        )
        for sample in samples
    ]
    if offsets:
        offset = statistics.median(offsets)
        spread = max(offsets) - min(offsets)
        method = "median-target-minus-host"
    else:
        offset = 0.0
        spread = 0.0
        method = "identity-no-clock-samples"

    return {
        "method": method,
        "target_minus_host_seconds": offset,
        "sample_spread_seconds": spread,
        "samples": samples,
    }


def _coalesce_text_actions(
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not actions:
        return []

    result: list[dict[str, Any]] = []
    for action in actions:
        if (
            action.get("action") == "text_input"
            and result
            and result[-1].get("action")
            == "text_input"
        ):
            previous = result[-1]
            try:
                previous_end = _parse_utc(
                    str(previous["host_utc"])
                )
                current_start = _parse_utc(
                    str(
                        action.get(
                            "host_started_utc"
                        )
                        or action["host_utc"]
                    )
                )
            except (KeyError, ValueError):
                previous_end = None
                current_start = None

            if (
                previous_end is not None
                and current_start is not None
                and (
                    current_start - previous_end
                ).total_seconds()
                <= 1.0
            ):
                previous_details = previous.setdefault(
                    "details",
                    {},
                )
                current_details = action.get(
                    "details"
                )
                if not isinstance(
                    previous_details,
                    dict,
                ):
                    previous_details = {}
                    previous["details"] = (
                        previous_details
                    )
                if not isinstance(
                    current_details,
                    dict,
                ):
                    current_details = {}
                previous_details["text"] = (
                    str(
                        previous_details.get(
                            "text"
                        )
                        or ""
                    )
                    + str(
                        current_details.get(
                            "text"
                        )
                        or ""
                    )
                )
                previous_details["length"] = len(
                    str(
                        previous_details.get(
                            "text"
                        )
                        or ""
                    )
                )
                previous["host_utc"] = action.get(
                    "host_utc"
                )
                continue

        result.append(
            json.loads(
                json.dumps(
                    action,
                    ensure_ascii=False,
                )
            )
        )
    return result


def _read_logcat(
    path: Path,
    package_name: str,
) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    except FileNotFoundError:
        return []

    result: list[dict[str, Any]] = []
    for line in lines:
        match = _LOGCAT_RE.match(line)
        if match is None:
            continue
        epoch = float(match.group("epoch"))
        tag = match.group("tag").strip()
        message = match.group("message")
        package_related = (
            package_name in line
            if package_name
            else False
        )
        relevant = (
            package_related
            or tag in _RELEVANT_LOG_TAGS
            or match.group("level") in {"E", "F"}
        )
        result.append(
            {
                "epoch": epoch,
                "target_utc": _iso_epoch(epoch),
                "pid": int(match.group("pid")),
                "tid": int(match.group("tid")),
                "level": match.group("level"),
                "tag": tag,
                "message": message[:800],
                "package_related": package_related,
                "relevant": relevant,
            }
        )
    return result


def _pcap_header(
    handle,
) -> tuple[str, int, int]:
    header = handle.read(24)
    if len(header) != 24:
        return "<", 1_000_000, -1
    magics = {
        b"\xd4\xc3\xb2\xa1": ("<", 1_000_000),
        b"\xa1\xb2\xc3\xd4": (">", 1_000_000),
        b"\x4d\x3c\xb2\xa1": (
            "<",
            1_000_000_000,
        ),
        b"\xa1\xb2\x3c\x4d": (
            ">",
            1_000_000_000,
        ),
    }
    try:
        endian, scale = magics[header[:4]]
    except KeyError:
        return "<", 1_000_000, -1
    linktype = struct.unpack(
        f"{endian}I",
        header[20:24],
    )[0]
    return endian, scale, linktype


def _network_payload(
    packet: bytes,
    linktype: int,
) -> tuple[
    bytes | None,
    int | None,
    str | None,
]:
    if linktype == 1:
        if len(packet) < 14:
            return None, None, None
        ethertype = int.from_bytes(
            packet[12:14],
            "big",
        )
        offset = 14
        while (
            ethertype in {0x8100, 0x88A8}
            and len(packet) >= offset + 4
        ):
            ethertype = int.from_bytes(
                packet[
                    offset + 2 : offset + 4
                ],
                "big",
            )
            offset += 4
        return packet[offset:], ethertype, None

    if linktype == 113:
        if len(packet) < 16:
            return None, None, None
        packet_type = int.from_bytes(
            packet[0:2],
            "big",
        )
        ethertype = int.from_bytes(
            packet[14:16],
            "big",
        )
        direction = (
            "outbound"
            if packet_type == 4
            else "inbound"
            if packet_type == 0
            else "other"
        )
        return packet[16:], ethertype, direction

    if linktype == 276:
        if len(packet) < 20:
            return None, None, None
        ethertype = int.from_bytes(
            packet[0:2],
            "big",
        )
        packet_type = packet[10]
        direction = (
            "outbound"
            if packet_type == 4
            else "inbound"
            if packet_type == 0
            else "other"
        )
        return packet[20:], ethertype, direction

    if linktype == 101:
        if not packet:
            return None, None, None
        version = packet[0] >> 4
        ethertype = (
            0x0800
            if version == 4
            else 0x86DD
            if version == 6
            else None
        )
        return packet, ethertype, None

    return None, None, None


def _decode_ip(
    payload: bytes,
    ethertype: int | None,
) -> dict[str, Any] | None:
    if ethertype == 0x0800:
        if len(payload) < 20:
            return None
        ihl = (payload[0] & 0x0F) * 4
        if ihl < 20 or len(payload) < ihl:
            return None
        protocol_number = payload[9]
        src = str(
            ipaddress.ip_address(
                payload[12:16]
            )
        )
        dst = str(
            ipaddress.ip_address(
                payload[16:20]
            )
        )
        fragment = int.from_bytes(
            payload[6:8],
            "big",
        ) & 0x1FFF
        transport = (
            payload[ihl:]
            if fragment == 0
            else b""
        )
    elif ethertype == 0x86DD:
        if len(payload) < 40:
            return None
        protocol_number = payload[6]
        src = str(
            ipaddress.ip_address(
                payload[8:24]
            )
        )
        dst = str(
            ipaddress.ip_address(
                payload[24:40]
            )
        )
        transport = payload[40:]
    else:
        return None

    protocol = {
        6: "tcp",
        17: "udp",
        1: "icmp",
        58: "icmpv6",
    }.get(
        protocol_number,
        str(protocol_number),
    )

    value: dict[str, Any] = {
        "protocol": protocol,
        "src": src,
        "dst": dst,
        "src_port": None,
        "dst_port": None,
        "payload": b"",
    }

    if protocol_number == 6:
        if len(transport) < 20:
            return value
        value["src_port"] = int.from_bytes(
            transport[0:2],
            "big",
        )
        value["dst_port"] = int.from_bytes(
            transport[2:4],
            "big",
        )
        data_offset = (
            (transport[12] >> 4) * 4
        )
        if (
            data_offset >= 20
            and len(transport) >= data_offset
        ):
            value["payload"] = transport[
                data_offset:
            ]
    elif protocol_number == 17:
        if len(transport) < 8:
            return value
        value["src_port"] = int.from_bytes(
            transport[0:2],
            "big",
        )
        value["dst_port"] = int.from_bytes(
            transport[2:4],
            "big",
        )
        value["payload"] = transport[8:]

    return value


def _dns_query_name(
    payload: bytes,
    *,
    tcp: bool,
) -> str | None:
    if tcp:
        if len(payload) < 2:
            return None
        length = int.from_bytes(
            payload[:2],
            "big",
        )
        payload = payload[2 : 2 + length]
    if len(payload) < 12:
        return None
    flags = int.from_bytes(
        payload[2:4],
        "big",
    )
    is_response = bool(flags & 0x8000)
    qdcount = int.from_bytes(
        payload[4:6],
        "big",
    )
    if is_response or qdcount <= 0:
        return None

    labels: list[str] = []
    cursor = 12
    for _ in range(128):
        if cursor >= len(payload):
            return None
        size = payload[cursor]
        cursor += 1
        if size == 0:
            break
        if size & 0xC0:
            return None
        if (
            size > 63
            or cursor + size > len(payload)
        ):
            return None
        label = payload[
            cursor : cursor + size
        ].decode(
            "ascii",
            errors="ignore",
        )
        labels.append(label)
        cursor += size
    name = ".".join(
        label
        for label in labels
        if label
    )
    return name or None


def _tls_sni(payload: bytes) -> str | None:
    if len(payload) < 9 or payload[0] != 0x16:
        return None
    record_length = int.from_bytes(
        payload[3:5],
        "big",
    )
    record = payload[
        5 : 5 + record_length
    ]
    if len(record) < 4 or record[0] != 0x01:
        return None
    body_length = int.from_bytes(
        record[1:4],
        "big",
    )
    body = record[4 : 4 + body_length]
    if len(body) < 34:
        return None

    cursor = 34
    if cursor >= len(body):
        return None
    session_length = body[cursor]
    cursor += 1 + session_length
    if cursor + 2 > len(body):
        return None
    cipher_length = int.from_bytes(
        body[cursor : cursor + 2],
        "big",
    )
    cursor += 2 + cipher_length
    if cursor >= len(body):
        return None
    compression_length = body[cursor]
    cursor += 1 + compression_length
    if cursor + 2 > len(body):
        return None
    extensions_length = int.from_bytes(
        body[cursor : cursor + 2],
        "big",
    )
    cursor += 2
    end = min(
        len(body),
        cursor + extensions_length,
    )

    while cursor + 4 <= end:
        extension_type = int.from_bytes(
            body[cursor : cursor + 2],
            "big",
        )
        extension_length = int.from_bytes(
            body[cursor + 2 : cursor + 4],
            "big",
        )
        cursor += 4
        extension = body[
            cursor : cursor + extension_length
        ]
        cursor += extension_length
        if extension_type != 0 or len(extension) < 5:
            continue
        list_length = int.from_bytes(
            extension[0:2],
            "big",
        )
        name_cursor = 2
        name_end = min(
            len(extension),
            2 + list_length,
        )
        while name_cursor + 3 <= name_end:
            name_type = extension[
                name_cursor
            ]
            name_length = int.from_bytes(
                extension[
                    name_cursor
                    + 1 : name_cursor
                    + 3
                ],
                "big",
            )
            name_cursor += 3
            name = extension[
                name_cursor : name_cursor
                + name_length
            ]
            name_cursor += name_length
            if name_type == 0:
                value = name.decode(
                    "ascii",
                    errors="ignore",
                ).strip()
                return value or None
    return None


def _read_pcap(
    path: Path,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
]:
    try:
        handle = path.open("rb")
    except FileNotFoundError:
        return [], {
            "packet_count": 0,
            "captured_bytes": 0,
            "linktype": None,
        }

    packets: list[dict[str, Any]] = []
    captured_bytes = 0
    with handle:
        endian, scale, linktype = _pcap_header(
            handle
        )
        if linktype < 0:
            return [], {
                "packet_count": 0,
                "captured_bytes": 0,
                "linktype": None,
            }

        while True:
            record = handle.read(16)
            if not record:
                break
            if len(record) != 16:
                break
            (
                seconds,
                fraction,
                included,
                original,
            ) = struct.unpack(
                f"{endian}IIII",
                record,
            )
            if included > 64 * 1024 * 1024:
                break
            payload = handle.read(included)
            if len(payload) != included:
                break

            epoch = (
                seconds
                + fraction / scale
            )
            captured_bytes += included
            network_payload, ethertype, direction = (
                _network_payload(
                    payload,
                    linktype,
                )
            )
            decoded = (
                _decode_ip(
                    network_payload,
                    ethertype,
                )
                if network_payload is not None
                else None
            )
            value: dict[str, Any] = {
                "epoch": epoch,
                "target_utc": _iso_epoch(epoch),
                "captured_length": included,
                "original_length": original,
                "direction": direction,
                "protocol": None,
                "src": None,
                "dst": None,
                "src_port": None,
                "dst_port": None,
                "dns_query": None,
                "tls_sni": None,
            }
            if decoded is not None:
                value.update(
                    {
                        "protocol": decoded[
                            "protocol"
                        ],
                        "src": decoded["src"],
                        "dst": decoded["dst"],
                        "src_port": decoded[
                            "src_port"
                        ],
                        "dst_port": decoded[
                            "dst_port"
                        ],
                    }
                )
                transport_payload = decoded[
                    "payload"
                ]
                src_port = decoded[
                    "src_port"
                ]
                dst_port = decoded[
                    "dst_port"
                ]
                protocol = decoded[
                    "protocol"
                ]
                if 53 in {src_port, dst_port}:
                    value["dns_query"] = (
                        _dns_query_name(
                            transport_payload,
                            tcp=protocol == "tcp",
                        )
                    )
                if (
                    protocol == "tcp"
                    and 443
                    in {src_port, dst_port}
                ):
                    value["tls_sni"] = (
                        _tls_sni(
                            transport_payload
                        )
                    )
            packets.append(value)

    return packets, {
        "packet_count": len(packets),
        "captured_bytes": captured_bytes,
        "linktype": linktype,
    }


def _flow_key(
    packet: dict[str, Any],
) -> tuple[Any, ...] | None:
    if (
        packet.get("src") is None
        or packet.get("dst") is None
        or packet.get("protocol") is None
    ):
        return None
    return (
        packet.get("direction"),
        packet.get("protocol"),
        packet.get("src"),
        packet.get("src_port"),
        packet.get("dst"),
        packet.get("dst_port"),
    )


def _flow_value(
    key: tuple[Any, ...],
) -> dict[str, Any]:
    (
        direction,
        protocol,
        src,
        src_port,
        dst,
        dst_port,
    ) = key
    return {
        "direction": direction,
        "protocol": protocol,
        "src": src,
        "src_port": src_port,
        "dst": dst,
        "dst_port": dst_port,
    }


def _network_markers(
    packets: list[dict[str, Any]],
    offset_seconds: float,
) -> tuple[
    list[dict[str, Any]],
    dict[tuple[Any, ...], float],
]:
    markers: list[dict[str, Any]] = []
    first_flow: dict[
        tuple[Any, ...],
        float,
    ] = {}
    seen_dns: set[str] = set()
    seen_sni: set[str] = set()

    for packet in packets:
        epoch = float(packet["epoch"])
        key = _flow_key(packet)
        if (
            key is not None
            and key not in first_flow
        ):
            first_flow[key] = epoch
            if (
                len(markers)
                < _MAX_NETWORK_MARKERS
            ):
                target_time = datetime.fromtimestamp(
                    epoch,
                    tz=timezone.utc,
                )
                markers.append(
                    {
                        "kind": "network_flow_started",
                        "target_utc": _iso_utc(
                            target_time
                        ),
                        "host_utc": _iso_utc(
                            target_time
                            - timedelta(
                                seconds=offset_seconds
                            )
                        ),
                        "details": _flow_value(
                            key
                        ),
                    }
                )

        dns = packet.get("dns_query")
        if (
            isinstance(dns, str)
            and dns
            and dns not in seen_dns
            and len(markers)
            < _MAX_NETWORK_MARKERS
        ):
            seen_dns.add(dns)
            target_time = datetime.fromtimestamp(
                epoch,
                tz=timezone.utc,
            )
            markers.append(
                {
                    "kind": "dns_query",
                    "target_utc": _iso_utc(
                        target_time
                    ),
                    "host_utc": _iso_utc(
                        target_time
                        - timedelta(
                            seconds=offset_seconds
                        )
                    ),
                    "details": {
                        "name": dns,
                    },
                }
            )

        sni = packet.get("tls_sni")
        if (
            isinstance(sni, str)
            and sni
            and sni not in seen_sni
            and len(markers)
            < _MAX_NETWORK_MARKERS
        ):
            seen_sni.add(sni)
            target_time = datetime.fromtimestamp(
                epoch,
                tz=timezone.utc,
            )
            markers.append(
                {
                    "kind": "tls_sni",
                    "target_utc": _iso_utc(
                        target_time
                    ),
                    "host_utc": _iso_utc(
                        target_time
                        - timedelta(
                            seconds=offset_seconds
                        )
                    ),
                    "details": {
                        "server_name": sni,
                    },
                }
            )

    return markers, first_flow


def _action_correlation(
    action: dict[str, Any],
    *,
    offset_seconds: float,
    packets: list[dict[str, Any]],
    packet_epochs: list[float],
    logcat: list[dict[str, Any]],
    log_epochs: list[float],
    first_flow: dict[tuple[Any, ...], float],
) -> dict[str, Any]:
    host_start = _parse_utc(
        str(
            action.get("host_started_utc")
            or action["host_utc"]
        )
    )
    host_end = _parse_utc(
        str(action["host_utc"])
    )
    target_start = (
        host_start
        + timedelta(
            seconds=offset_seconds
        )
    )
    target_end = (
        host_end
        + timedelta(
            seconds=offset_seconds
        )
    )
    window_start = (
        target_start.timestamp()
        - _ACTION_WINDOW_BEFORE_SECONDS
    )
    window_end = (
        target_end.timestamp()
        + _ACTION_WINDOW_AFTER_SECONDS
    )

    packet_start = bisect.bisect_left(
        packet_epochs,
        window_start,
    )
    packet_end = bisect.bisect_right(
        packet_epochs,
        window_end,
    )
    selected_packets = packets[
        packet_start:packet_end
    ]

    flow_counts: dict[
        tuple[Any, ...],
        int,
    ] = {}
    new_flows: list[dict[str, Any]] = []
    dns_names: list[str] = []
    tls_names: list[str] = []
    dns_seen: set[str] = set()
    tls_seen: set[str] = set()
    network_bytes = 0

    for packet in selected_packets:
        network_bytes += int(
            packet.get(
                "captured_length"
            )
            or 0
        )
        key = _flow_key(packet)
        if key is not None:
            flow_counts[key] = (
                flow_counts.get(key, 0)
                + 1
            )
            first_epoch = first_flow.get(
                key
            )
            if (
                first_epoch is not None
                and window_start
                <= first_epoch
                <= window_end
                and not any(
                    item.get("flow")
                    == _flow_value(key)
                    for item in new_flows
                )
            ):
                new_flows.append(
                    {
                        "target_utc": _iso_epoch(
                            first_epoch
                        ),
                        "flow": _flow_value(
                            key
                        ),
                    }
                )
        dns = packet.get("dns_query")
        if (
            isinstance(dns, str)
            and dns
            and dns not in dns_seen
        ):
            dns_seen.add(dns)
            dns_names.append(dns)
        sni = packet.get("tls_sni")
        if (
            isinstance(sni, str)
            and sni
            and sni not in tls_seen
        ):
            tls_seen.add(sni)
            tls_names.append(sni)

    ordered_flows = sorted(
        flow_counts.items(),
        key=lambda item: (
            -item[1],
            str(item[0]),
        ),
    )
    flow_sample = [
        {
            **_flow_value(key),
            "packet_count": count,
        }
        for key, count in ordered_flows[
            :_MAX_FLOW_SAMPLE
        ]
    ]

    log_start = bisect.bisect_left(
        log_epochs,
        window_start,
    )
    log_end = bisect.bisect_right(
        log_epochs,
        window_end,
    )
    selected_log = logcat[
        log_start:log_end
    ]
    relevant_log = [
        item
        for item in selected_log
        if item.get("relevant")
    ]
    log_sample = (
        relevant_log[:_MAX_LOG_SAMPLE]
        if relevant_log
        else selected_log[:_MAX_LOG_SAMPLE]
    )

    return {
        "target_started_utc_estimate": (
            _iso_utc(target_start)
        ),
        "target_finished_utc_estimate": (
            _iso_utc(target_end)
        ),
        "window": {
            "before_seconds": (
                _ACTION_WINDOW_BEFORE_SECONDS
            ),
            "after_seconds": (
                _ACTION_WINDOW_AFTER_SECONDS
            ),
        },
        "network": {
            "packet_count": len(
                selected_packets
            ),
            "captured_bytes": network_bytes,
            "flows": flow_sample,
            "new_flows": new_flows[
                :_MAX_FLOW_SAMPLE
            ],
            "dns_queries": dns_names,
            "tls_sni": tls_names,
        },
        "logcat": {
            "entry_count": len(
                selected_log
            ),
            "relevant_entry_count": len(
                relevant_log
            ),
            "sample": [
                {
                    key: item[key]
                    for key in (
                        "target_utc",
                        "pid",
                        "tid",
                        "level",
                        "tag",
                        "message",
                        "package_related",
                    )
                }
                for item in log_sample
            ],
        },
    }


def build_research_timeline(
    session: SessionManager,
) -> dict[str, Any]:
    root = session.paths.root
    manifest = session.manifest
    package = manifest.get("package")
    package_name = (
        str(package.get("name") or "")
        if isinstance(package, dict)
        else ""
    )

    lifecycle = _read_jsonl(
        root
        / "02_normalized"
        / "session-events.jsonl"
    )
    actions = _coalesce_text_actions(
        _read_jsonl(
            root
            / "02_normalized"
            / "user-actions.jsonl"
        )
    )
    alignment = _clock_alignment(
        root,
        lifecycle,
    )
    offset = float(
        alignment[
            "target_minus_host_seconds"
        ]
    )

    packets, network_summary = _read_pcap(
        root
        / "01_raw"
        / "network"
        / "traffic.pcap"
    )
    packets.sort(
        key=lambda item: float(
            item["epoch"]
        )
    )
    packet_epochs = [
        float(item["epoch"])
        for item in packets
    ]
    network_markers, first_flow = (
        _network_markers(
            packets,
            offset,
        )
    )

    logcat = _read_logcat(
        root
        / "01_raw"
        / "logcat"
        / "logcat.txt",
        package_name,
    )
    logcat.sort(
        key=lambda item: float(
            item["epoch"]
        )
    )
    log_epochs = [
        float(item["epoch"])
        for item in logcat
    ]

    normalized_actions: list[
        dict[str, Any]
    ] = []
    for action in actions:
        if not action.get("host_utc"):
            continue
        try:
            correlation = _action_correlation(
                action,
                offset_seconds=offset,
                packets=packets,
                packet_epochs=packet_epochs,
                logcat=logcat,
                log_epochs=log_epochs,
                first_flow=first_flow,
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            correlation = {
                "error": (
                    "action timestamp could not "
                    "be correlated"
                )
            }
        normalized_actions.append(
            {
                **action,
                "correlation": correlation,
            }
        )

    events: list[dict[str, Any]] = []
    for event in lifecycle:
        host_utc = event.get(
            "host_utc"
        )
        if not host_utc:
            continue
        events.append(
            {
                "kind": "lifecycle",
                "host_utc": host_utc,
                "target_utc": event.get(
                    "target_utc"
                ),
                "name": event.get(
                    "event"
                ),
                "details": event.get(
                    "details"
                ),
            }
        )
    for action in normalized_actions:
        events.append(
            {
                "kind": "user_action",
                "host_utc": action.get(
                    "host_started_utc"
                )
                or action.get("host_utc"),
                "target_utc": (
                    action.get(
                        "correlation",
                        {},
                    ).get(
                        "target_started_utc_estimate"
                    )
                    if isinstance(
                        action.get(
                            "correlation"
                        ),
                        dict,
                    )
                    else None
                ),
                "name": action.get(
                    "action"
                ),
                "action_id": action.get(
                    "action_id"
                ),
                "details": action.get(
                    "details"
                ),
            }
        )
    events.extend(network_markers)

    def event_key(
        value: dict[str, Any],
    ) -> tuple[int, str]:
        host_value = value.get(
            "host_utc"
        )
        if not host_value:
            return 1, ""
        return 0, str(host_value)

    events.sort(key=event_key)

    timeline: dict[str, Any] = {
        "schema_version": "0.1",
        "session_id": session.session_id,
        "package": package_name,
        "session_status": session.status.value,
        "clock_alignment": alignment,
        "summary": {
            "lifecycle_events": len(
                lifecycle
            ),
            "user_actions": len(
                normalized_actions
            ),
            "network_packets": (
                network_summary[
                    "packet_count"
                ]
            ),
            "network_captured_bytes": (
                network_summary[
                    "captured_bytes"
                ]
            ),
            "network_linktype": (
                network_summary[
                    "linktype"
                ]
            ),
            "network_markers": len(
                network_markers
            ),
            "logcat_entries": len(
                logcat
            ),
        },
        "correlation_window": {
            "before_seconds": (
                _ACTION_WINDOW_BEFORE_SECONDS
            ),
            "after_seconds": (
                _ACTION_WINDOW_AFTER_SECONDS
            ),
        },
        "user_actions": normalized_actions,
        "events": events,
    }

    path = root / TIMELINE_ARTIFACT
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )
    try:
        with temporary.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            json.dump(
                timeline,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(
                handle.fileno()
            )
        os.replace(
            temporary,
            path,
        )
    finally:
        temporary.unlink(
            missing_ok=True
        )

    if not any(
        artifact.get("path")
        == TIMELINE_ARTIFACT
        for artifact in session.manifest.get(
            "artifacts",
            []
        )
    ):
        session.register_artifact(
            kind="research_timeline",
            relative_path=TIMELINE_ARTIFACT,
            source="timeline",
            raw=False,
        )

    return timeline
