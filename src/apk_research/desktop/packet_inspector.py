from __future__ import annotations

import io
import json
import struct
import zipfile
from pathlib import Path
from typing import Any, BinaryIO

from apk_research.network_attribution import canonical_connection_key
from apk_research.quic import QuicFlowInspector
from apk_research.desktop.protocol_analysis_v025 import (
    FlowProtocolAnalyzer,
    format_packet_protocol_evidence,
    protocol_packet_label,
)
from apk_research.timeline import (
    TIMELINE_ARTIFACT,
    _decode_ip,
    _dns_query_name,
    _iso_epoch,
    _network_payload,
    _parse_utc,
    _pcap_header,
    _tls_sni,
)

RAW_PCAP_ARTIFACT = "01_raw/network/traffic.pcap"
DEFAULT_HEX_PREVIEW_BYTES = 256
MAX_PACKET_LENGTH = 64 * 1024 * 1024


def _endpoint(ip_value: Any, port_value: Any) -> tuple[str, int | None]:
    ip_text = str(ip_value or "")
    try:
        port = int(port_value) if port_value is not None else None
    except (TypeError, ValueError):
        port = None
    return ip_text, port


def flow_connection_key(flow: dict[str, Any]) -> tuple[Any, ...] | None:
    protocol = str(flow.get("protocol") or "").lower()
    if protocol not in {"tcp", "udp"}:
        return None

    endpoint_a = flow.get("endpoint_a")
    endpoint_b = flow.get("endpoint_b")
    if isinstance(endpoint_a, dict) and isinstance(endpoint_b, dict):
        left = _endpoint(endpoint_a.get("ip"), endpoint_a.get("port"))
        right = _endpoint(endpoint_b.get("ip"), endpoint_b.get("port"))
    else:
        left = _endpoint(flow.get("local_ip"), flow.get("local_port"))
        right = _endpoint(flow.get("remote_ip"), flow.get("remote_port"))

    if not left[0] or not right[0]:
        return None

    left, right = sorted(
        (left, right),
        key=lambda value: (
            value[0],
            -1 if value[1] is None else value[1],
        ),
    )
    return protocol, left, right


def _action_display_label(action: dict[str, Any]) -> str:
    action_id = str(action.get("action_id") or "")
    action_name = str(action.get("action") or "action")
    if action_id:
        return f"{action_id} • {action_name}"
    return action_name


def _timeline_action_windows(
    timeline: dict[str, Any],
    flow_id: str,
) -> list[dict[str, Any]]:
    """Return canonical temporal-only action windows referencing one flow."""

    windows: list[dict[str, Any]] = []
    if not flow_id:
        return windows

    for action in timeline.get("user_actions") or []:
        if not isinstance(action, dict):
            continue
        action_id = str(action.get("action_id") or "")
        correlation = action.get("correlation")
        if not action_id or not isinstance(correlation, dict):
            continue
        if (
            correlation.get("causal_claim") is not False
            or str(correlation.get("attribution") or "")
            != "temporal-only"
        ):
            continue

        network = correlation.get("network")
        if not isinstance(network, dict):
            continue
        flow_ids = {
            str(value)
            for value in network.get("flow_ids") or []
            if value
        }
        if flow_id not in flow_ids:
            continue

        start_text = str(
            correlation.get("target_started_utc_estimate")
            or ""
        )
        finish_text = str(
            correlation.get("target_finished_utc_estimate")
            or ""
        )
        if not start_text or not finish_text:
            continue
        try:
            start_epoch = _parse_utc(start_text).timestamp()
            finish_epoch = _parse_utc(finish_text).timestamp()
            window = correlation.get("window")
            if not isinstance(window, dict):
                window = {}
            after_seconds = max(
                0.0,
                float(window.get("actual_after_seconds") or 0.0),
            )
        except (TypeError, ValueError):
            continue
        end_epoch = finish_epoch + after_seconds
        if end_epoch < start_epoch:
            continue

        windows.append(
            {
                "action_id": action_id,
                "action": str(action.get("action") or ""),
                "label": _action_display_label(action),
                "window_started_utc": _iso_epoch(start_epoch),
                "window_finished_utc": _iso_epoch(end_epoch),
                "window_start_epoch": start_epoch,
                "window_end_epoch": end_epoch,
                "causal_confidence": str(
                    correlation.get("causal_confidence") or ""
                ),
                "attribution": "temporal-only",
                "causal_claim": False,
            }
        )

    windows.sort(
        key=lambda value: (
            float(value["window_start_epoch"]),
            str(value["action_id"]),
        )
    )
    return windows


def correlate_packets_with_timeline(
    report: dict[str, Any],
    timeline: dict[str, Any],
) -> dict[str, Any]:
    """Annotate packet presentation with existing Timeline windows.

    The correlation is derived only from the already exported Timeline:
    a packet is linked to an action when the selected flow is present in that
    action's existing network correlation and the packet timestamp falls inside
    the action's existing target-time window. This never upgrades temporal
    adjacency into causality.
    """

    flow_id = str(report.get("flow_id") or "")
    windows = _timeline_action_windows(
        timeline,
        flow_id,
    )
    matched_packets = 0
    matched_relations = 0

    for packet in report.get("packets") or []:
        if not isinstance(packet, dict):
            continue
        try:
            epoch = float(packet.get("epoch"))
        except (TypeError, ValueError):
            epoch = float("nan")

        matches = [
            {
                key: window[key]
                for key in (
                    "action_id",
                    "action",
                    "label",
                    "window_started_utc",
                    "window_finished_utc",
                    "causal_confidence",
                    "attribution",
                    "causal_claim",
                )
            }
            for window in windows
            if (
                epoch == epoch
                and float(window["window_start_epoch"])
                <= epoch
                <= float(window["window_end_epoch"])
            )
        ]
        packet["temporal_actions"] = matches
        packet["temporal_action_ids"] = [
            str(match["action_id"])
            for match in matches
        ]
        packet["temporal_action_labels"] = [
            str(match["label"])
            for match in matches
        ]
        packet["temporal_relation"] = (
            "inside-action-window"
            if matches
            else "none"
        )
        packet["causal_claim"] = False
        if matches:
            matched_packets += 1
            matched_relations += len(matches)

    report["timeline_artifact"] = TIMELINE_ARTIFACT
    report["timeline_action_window_count"] = len(windows)
    report["packet_action_match_count"] = matched_packets
    report["packet_action_relation_count"] = matched_relations
    report["correlation_type"] = "temporal-only"
    report["causal_claim"] = False
    return report


def _packet_direction(
    packet: dict[str, Any],
    flow: dict[str, Any],
) -> str:
    captured = str(packet.get("direction") or "")
    if captured in {"outbound", "inbound"}:
        return captured

    local = _endpoint(flow.get("local_ip"), flow.get("local_port"))
    remote = _endpoint(flow.get("remote_ip"), flow.get("remote_port"))
    src = _endpoint(packet.get("src"), packet.get("src_port"))
    dst = _endpoint(packet.get("dst"), packet.get("dst_port"))

    if local[0] and remote[0]:
        if src == local and dst == remote:
            return "outbound"
        if src == remote and dst == local:
            return "inbound"
    return captured or "unknown"


_TCP_FLAG_NAMES = (
    (0x80, "CWR"),
    (0x40, "ECE"),
    (0x20, "URG"),
    (0x10, "ACK"),
    (0x08, "PSH"),
    (0x04, "RST"),
    (0x02, "SYN"),
    (0x01, "FIN"),
)


def _transport_header(
    network_payload: bytes,
    ethertype: int | None,
) -> tuple[int | None, bytes]:
    """Return the transport protocol number and exact transport bytes.

    This intentionally mirrors the IP boundary currently supported by
    timeline._decode_ip: IPv4 without non-first fragmentation, or the fixed
    IPv6 header without extension-header traversal.
    """

    if ethertype == 0x0800:
        if len(network_payload) < 20:
            return None, b""
        ihl = (network_payload[0] & 0x0F) * 4
        if ihl < 20 or len(network_payload) < ihl:
            return None, b""
        fragment_offset = int.from_bytes(
            network_payload[6:8],
            "big",
        ) & 0x1FFF
        if fragment_offset:
            return int(network_payload[9]), b""
        return int(network_payload[9]), network_payload[ihl:]

    if ethertype == 0x86DD:
        if len(network_payload) < 40:
            return None, b""
        return int(network_payload[6]), network_payload[40:]

    return None, b""


def _transport_metadata(
    network_payload: bytes,
    ethertype: int | None,
    decoded: dict[str, Any],
) -> dict[str, Any]:
    protocol = str(decoded.get("protocol") or "").lower()
    protocol_number, transport = _transport_header(
        network_payload,
        ethertype,
    )

    if protocol == "tcp":
        result: dict[str, Any] = {
            "tcp_header_valid": False,
            "tcp_sequence": None,
            "tcp_acknowledgment": None,
            "tcp_flags": [],
            "tcp_flags_bits": None,
            "tcp_header_length": None,
            "tcp_window": None,
            "tcp_payload_length": len(
                decoded.get("payload")
                if isinstance(decoded.get("payload"), bytes)
                else b""
            ),
        }
        if protocol_number != 6 or len(transport) < 20:
            return result

        data_offset = (transport[12] >> 4) * 4
        if data_offset < 20 or len(transport) < data_offset:
            return result

        bits = int(transport[13])
        flags = [
            name
            for mask, name in _TCP_FLAG_NAMES
            if bits & mask
        ]
        result.update(
            {
                "tcp_header_valid": True,
                "tcp_sequence": int.from_bytes(
                    transport[4:8],
                    "big",
                ),
                "tcp_acknowledgment": int.from_bytes(
                    transport[8:12],
                    "big",
                ),
                "tcp_flags": flags,
                "tcp_flags_bits": bits,
                "tcp_header_length": data_offset,
                "tcp_window": int.from_bytes(
                    transport[14:16],
                    "big",
                ),
                "tcp_payload_length": len(transport) - data_offset,
            }
        )
        return result

    if protocol == "udp":
        result = {
            "udp_header_valid": False,
            "udp_length": None,
            "udp_checksum": None,
        }
        if protocol_number != 17 or len(transport) < 8:
            return result
        result.update(
            {
                "udp_header_valid": True,
                "udp_length": int.from_bytes(
                    transport[4:6],
                    "big",
                ),
                "udp_checksum": int.from_bytes(
                    transport[6:8],
                    "big",
                ),
            }
        )
        return result

    return {}


def _tcp_flag_set(packet: dict[str, Any]) -> set[str]:
    return {
        str(value)
        for value in packet.get("tcp_flags") or []
        if value
    }


def build_transport_session(
    packets: list[dict[str, Any]],
    protocol: str,
) -> dict[str, Any]:
    """Summarize only transport lifecycle evidence actually present in PCAP."""

    protocol = str(protocol or "").lower()
    if protocol != "tcp":
        return {
            "protocol": protocol,
            "applicable": False,
            "reason": "tcp-only",
        }

    tcp_packets = [
        packet
        for packet in packets
        if isinstance(packet, dict)
        and str(packet.get("protocol") or "").lower() == "tcp"
    ]

    syn = [
        packet
        for packet in tcp_packets
        if "SYN" in _tcp_flag_set(packet)
        and "ACK" not in _tcp_flag_set(packet)
    ]
    syn_ack = [
        packet
        for packet in tcp_packets
        if {"SYN", "ACK"} <= _tcp_flag_set(packet)
    ]
    fin = [
        packet
        for packet in tcp_packets
        if "FIN" in _tcp_flag_set(packet)
    ]
    rst = [
        packet
        for packet in tcp_packets
        if "RST" in _tcp_flag_set(packet)
    ]

    handshake: list[dict[str, Any]] = []
    if syn:
        first_syn = syn[0]
        initiator = str(first_syn.get("direction") or "")
        responder = (
            "inbound"
            if initiator == "outbound"
            else "outbound"
            if initiator == "inbound"
            else ""
        )
        syn_index = int(first_syn.get("packet_index") or 0)

        second = next(
            (
                packet
                for packet in syn_ack
                if int(packet.get("packet_index") or 0) > syn_index
                and (
                    not responder
                    or str(packet.get("direction") or "") == responder
                )
            ),
            None,
        )
        if second is not None:
            second_index = int(second.get("packet_index") or 0)
            third = next(
                (
                    packet
                    for packet in tcp_packets
                    if int(packet.get("packet_index") or 0) > second_index
                    and "ACK" in _tcp_flag_set(packet)
                    and "SYN" not in _tcp_flag_set(packet)
                    and (
                        not initiator
                        or str(packet.get("direction") or "") == initiator
                    )
                ),
                None,
            )
            if third is not None:
                handshake = [first_syn, second, third]

    handshake_observed = len(handshake) == 3
    if rst:
        termination = "reset-observed"
        termination_packets = rst
    elif fin:
        termination = "fin-observed"
        termination_packets = fin
    else:
        termination = "not-observed-in-capture"
        termination_packets = []

    return {
        "protocol": "tcp",
        "applicable": True,
        "packet_count": len(tcp_packets),
        "handshake_status": (
            "complete-three-way-observed"
            if handshake_observed
            else "partial-or-not-observed-in-capture"
        ),
        "handshake_observed": handshake_observed,
        "handshake_packet_ids": [
            str(packet.get("packet_id") or "")
            for packet in handshake
        ],
        "syn_packet_ids": [
            str(packet.get("packet_id") or "")
            for packet in syn
        ],
        "syn_ack_packet_ids": [
            str(packet.get("packet_id") or "")
            for packet in syn_ack
        ],
        "termination_status": termination,
        "termination_packet_ids": [
            str(packet.get("packet_id") or "")
            for packet in termination_packets
        ],
        "rst_packet_ids": [
            str(packet.get("packet_id") or "")
            for packet in rst
        ],
        "fin_packet_ids": [
            str(packet.get("packet_id") or "")
            for packet in fin
        ],
        "absence_semantics": (
            "not-observed means only that the event is absent from this "
            "capture; it does not prove that it did not occur"
        ),
    }


def _format_hex_preview(data: bytes, limit: int) -> tuple[str, bool]:
    bounded = data[: max(0, int(limit))]
    lines: list[str] = []
    for offset in range(0, len(bounded), 16):
        chunk = bounded[offset : offset + 16]
        hex_part = " ".join(f"{value:02x}" for value in chunk)
        ascii_part = "".join(
            chr(value) if 32 <= value <= 126 else "."
            for value in chunk
        )
        lines.append(
            f"{offset:04x}  {hex_part:<47}  {ascii_part}"
        )
    return "\n".join(lines), len(data) > len(bounded)


def _packet_metadata(
    decoded: dict[str, Any] | None,
    direction: str,
    quic: QuicFlowInspector | None,
) -> dict[str, Any]:
    if decoded is None:
        return {}

    protocol = str(decoded.get("protocol") or "").lower()
    src_port = decoded.get("src_port")
    dst_port = decoded.get("dst_port")
    transport_payload = decoded.get("payload")
    if not isinstance(transport_payload, bytes):
        transport_payload = b""

    result: dict[str, Any] = {
        "transport_payload_length": len(transport_payload),
        "dns_query": None,
        "tls_sni": None,
        "application_protocol": None,
        "quic_version": None,
        "quic_packet_type": None,
        "quic_initial_decrypted": False,
        "quic_sni": None,
        "quic_alpn": [],
    }

    if 53 in {src_port, dst_port}:
        result["dns_query"] = _dns_query_name(
            transport_payload,
            tcp=protocol == "tcp",
        )

    if protocol == "tcp" and 443 in {src_port, dst_port}:
        result["tls_sni"] = _tls_sni(transport_payload)

    if protocol == "udp" and quic is not None:
        value = quic.inspect(
            transport_payload,
            direction=direction if direction in {"outbound", "inbound"} else None,
        )
        if isinstance(value, dict):
            alpn = [
                str(item)
                for item in value.get("alpn") or []
                if item
            ]
            result["application_protocol"] = (
                "http3"
                if any(item == "h3" or item.startswith("h3-") for item in alpn)
                else "quic"
            )
            result["quic_version"] = value.get("version")
            result["quic_packet_type"] = value.get("packet_type")
            result["quic_initial_decrypted"] = bool(
                value.get("initial_decrypted")
            )
            result["quic_sni"] = value.get("sni")
            result["quic_alpn"] = alpn
            if value.get("sni"):
                result["tls_sni"] = value.get("sni")

    return result


def inspect_pcap_flow(
    handle: BinaryIO,
    flow: dict[str, Any],
    *,
    hex_preview_bytes: int = DEFAULT_HEX_PREVIEW_BYTES,
) -> dict[str, Any]:
    target_key = flow_connection_key(flow)
    if target_key is None:
        raise ValueError("Flow does not contain a canonical TCP/UDP endpoint pair")

    endian, scale, linktype = _pcap_header(handle)
    if linktype < 0:
        raise ValueError("Unsupported or invalid PCAP header")

    selected: list[dict[str, Any]] = []
    total_packets = 0
    logical_offset = 24
    quic = QuicFlowInspector() if target_key[0] == "udp" else None
    protocol_analyzer = FlowProtocolAnalyzer(target_key[0])

    while True:
        record_offset = logical_offset
        record = handle.read(16)
        if not record:
            break
        if len(record) != 16:
            raise ValueError("Truncated PCAP record header")
        logical_offset += 16

        seconds, fraction, included, original = struct.unpack(
            f"{endian}IIII",
            record,
        )
        if included > MAX_PACKET_LENGTH:
            raise ValueError("PCAP record length exceeds safety bound")

        frame_offset = logical_offset
        raw_frame = handle.read(included)
        if len(raw_frame) != included:
            raise ValueError("Truncated PCAP packet payload")
        logical_offset += included
        total_packets += 1

        network_payload, ethertype, capture_direction = _network_payload(
            raw_frame,
            linktype,
        )
        decoded = (
            _decode_ip(network_payload, ethertype)
            if network_payload is not None
            else None
        )
        if decoded is None:
            continue

        packet = {
            "protocol": decoded.get("protocol"),
            "src": decoded.get("src"),
            "dst": decoded.get("dst"),
            "src_port": decoded.get("src_port"),
            "dst_port": decoded.get("dst_port"),
            "direction": capture_direction,
        }
        if canonical_connection_key(packet) != target_key:
            continue

        direction = _packet_direction(packet, flow)
        epoch = seconds + fraction / scale
        transport_payload = decoded.get("payload")
        if not isinstance(transport_payload, bytes):
            transport_payload = b""
        metadata = _packet_metadata(decoded, direction, quic)
        transport_metadata = _transport_metadata(
            network_payload,
            ethertype,
            decoded,
        )
        preview, truncated = _format_hex_preview(
            raw_frame,
            hex_preview_bytes,
        )
        packet_index = total_packets
        packet_record = {
                "packet_id": f"packet-{packet_index:06d}",
                "packet_index": packet_index,
                "target_utc": _iso_epoch(epoch),
                "epoch": epoch,
                "direction": direction,
                "capture_direction": capture_direction,
                "protocol": str(decoded.get("protocol") or ""),
                "src": decoded.get("src"),
                "src_port": decoded.get("src_port"),
                "dst": decoded.get("dst"),
                "dst_port": decoded.get("dst_port"),
                "captured_length": included,
                "original_length": original,
                "pcap_record_offset": record_offset,
                "pcap_frame_offset": frame_offset,
                "hex_preview": preview,
                "hex_preview_bytes": min(
                    included,
                    max(0, int(hex_preview_bytes)),
                ),
                "hex_preview_truncated": truncated,
                **metadata,
                **transport_metadata,
        }
        protocol_analyzer.observe(packet_record, transport_payload)
        selected.append(packet_record)

    protocol_analysis = protocol_analyzer.finalize(selected)
    transport_session = build_transport_session(
        selected,
        target_key[0],
    )
    return {
        "flow_id": str(flow.get("flow_id") or ""),
        "protocol": target_key[0],
        "packets": selected,
        "transport_session": transport_session,
        "protocol_analysis": protocol_analysis,
        "selected_packet_count": len(selected),
        "total_packet_count": total_packets,
        "linktype": linktype,
        "hex_preview_limit": max(0, int(hex_preview_bytes)),
    }


def inspect_archive_flow(
    archive: Path,
    flow: dict[str, Any],
    *,
    hex_preview_bytes: int = DEFAULT_HEX_PREVIEW_BYTES,
) -> dict[str, Any]:
    with zipfile.ZipFile(archive) as zipped:
        info = zipped.getinfo(RAW_PCAP_ARTIFACT)
        with zipped.open(info, "r") as raw:
            report = inspect_pcap_flow(
                raw,
                flow,
                hex_preview_bytes=hex_preview_bytes,
            )

        timeline_status = "missing"
        timeline: dict[str, Any] = {}
        try:
            decoded = json.loads(
                zipped.read(TIMELINE_ARTIFACT).decode(
                    "utf-8",
                    errors="strict",
                )
            )
            if isinstance(decoded, dict):
                timeline = decoded
                timeline_status = "loaded"
            else:
                timeline_status = "invalid"
        except KeyError:
            timeline_status = "missing"
        except (UnicodeDecodeError, json.JSONDecodeError):
            timeline_status = "invalid"

        correlate_packets_with_timeline(
            report,
            timeline,
        )
        report.update(
            {
                "archive": str(archive),
                "artifact": RAW_PCAP_ARTIFACT,
                "artifact_size": info.file_size,
                "artifact_compressed_size": info.compress_size,
                "artifact_crc32": f"{info.CRC:08x}",
                "timeline_status": timeline_status,
            }
        )
        return report


def packet_search_text(packet: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "packet_id",
        "packet_index",
        "target_utc",
        "direction",
        "protocol",
        "src",
        "src_port",
        "dst",
        "dst_port",
        "captured_length",
        "original_length",
        "dns_query",
        "tls_sni",
        "application_protocol",
        "quic_version",
        "quic_packet_type",
        "quic_sni",
        "temporal_relation",
        "tcp_sequence",
        "tcp_acknowledgment",
        "tcp_payload_length",
        "udp_length",
    ):
        value = packet.get(key)
        if value not in {None, ""}:
            values.append(str(value))
    values.extend(
        str(item)
        for item in packet.get("quic_alpn") or []
        if item
    )
    values.extend(
        str(item)
        for item in packet.get("tcp_flags") or []
        if item
    )
    values.extend(
        str(item)
        for item in packet.get("temporal_action_ids") or []
        if item
    )
    values.extend(
        str(item)
        for item in packet.get("temporal_action_labels") or []
        if item
    )
    protocol_label = protocol_packet_label(packet)
    if protocol_label:
        values.append(protocol_label)
    return " ".join(values).lower()


def packet_action_label(packet: dict[str, Any]) -> str:
    labels = [
        str(value)
        for value in packet.get("temporal_action_labels") or []
        if value
    ]
    return " / ".join(labels)


def packet_transport_label(packet: dict[str, Any]) -> str:
    protocol = str(packet.get("protocol") or "").lower()
    if protocol == "tcp":
        flags = [
            str(value)
            for value in packet.get("tcp_flags") or []
            if value
        ]
        if flags:
            return "TCP:" + ",".join(flags)
        return "TCP"
    if protocol == "udp":
        length = packet.get("udp_length")
        return (
            f"UDP:len={length}"
            if length not in {None, ""}
            else "UDP"
        )
    return protocol.upper()


def packet_metadata_label(packet: dict[str, Any]) -> str:
    parts: list[str] = []
    transport = packet_transport_label(packet)
    if transport:
        parts.append(transport)
    for key, label in (
        ("dns_query", "DNS"),
        ("tls_sni", "SNI"),
        ("application_protocol", "APP"),
        ("quic_packet_type", "QUIC"),
    ):
        value = packet.get(key)
        if value not in {None, ""}:
            parts.append(f"{label}:{value}")
    alpn = [str(item) for item in packet.get("quic_alpn") or [] if item]
    if alpn:
        parts.append("ALPN:" + ",".join(alpn))
    extended = protocol_packet_label(packet)
    if extended:
        parts.append(extended)
    return " • ".join(parts)


def format_packet_details(
    packet: dict[str, Any],
    *,
    artifact: str = RAW_PCAP_ARTIFACT,
) -> str:
    src = f"{packet.get('src') or '—'}:{packet.get('src_port') if packet.get('src_port') is not None else '—'}"
    dst = f"{packet.get('dst') or '—'}:{packet.get('dst_port') if packet.get('dst_port') is not None else '—'}"
    metadata = packet_metadata_label(packet) or "—"
    preview = str(packet.get("hex_preview") or "")
    protocol = str(packet.get("protocol") or "").lower()
    transport_lines: list[str] = []
    if protocol == "tcp":
        flags = ", ".join(
            str(value)
            for value in packet.get("tcp_flags") or []
            if value
        ) or "none"
        transport_lines = [
            f"TCP flags: {flags}",
            f"Sequence / ACK: {packet.get('tcp_sequence') if packet.get('tcp_sequence') is not None else '—'} / {packet.get('tcp_acknowledgment') if packet.get('tcp_acknowledgment') is not None else '—'}",
            f"TCP header / payload: {packet.get('tcp_header_length') if packet.get('tcp_header_length') is not None else '—'} / {packet.get('tcp_payload_length') if packet.get('tcp_payload_length') is not None else '—'} bytes",
            f"TCP window: {packet.get('tcp_window') if packet.get('tcp_window') is not None else '—'}",
        ]
    elif protocol == "udp":
        transport_lines = [
            f"UDP length: {packet.get('udp_length') if packet.get('udp_length') is not None else '—'}",
            f"UDP checksum: {packet.get('udp_checksum') if packet.get('udp_checksum') is not None else '—'}",
        ]
    protocol_lines = format_packet_protocol_evidence(packet)
    if packet.get("hex_preview_truncated"):
        preview += "\n… preview truncated; locator still points to the complete raw packet"

    actions = [
        value
        for value in packet.get("temporal_actions") or []
        if isinstance(value, dict)
    ]
    if actions:
        action_lines = []
        for relation in actions:
            action_lines.extend(
                [
                    f"  {relation.get('label') or relation.get('action_id') or 'action'}",
                    "    relation: temporal-only",
                    "    causal claim: no",
                    f"    window: {relation.get('window_started_utc') or '—'} .. {relation.get('window_finished_utc') or '—'}",
                    f"    confidence: {relation.get('causal_confidence') or '—'}",
                ]
            )
    else:
        action_lines = [
            "  no exported action window contains this packet for the selected flow"
        ]

    return "\n".join(
        [
            f"Packet: {packet.get('packet_id') or '—'}",
            f"Target UTC: {packet.get('target_utc') or '—'}",
            f"Direction: {packet.get('direction') or 'unknown'}",
            f"Protocol: {str(packet.get('protocol') or '').upper() or '—'}",
            f"Source: {src}",
            f"Destination: {dst}",
            f"Captured / original: {packet.get('captured_length') or 0} / {packet.get('original_length') or 0} bytes",
            f"Protocol evidence: {metadata}",
            *transport_lines,
            "",
            "Наблюдения протоколов v0.25:",
            *(protocol_lines or ["  no additional structured protocol evidence in this packet"]),
            "",
            "Timeline relation:",
            *action_lines,
            "",
            "Raw PCAP locator:",
            f"  artifact: {artifact}",
            f"  packet index: {packet.get('packet_index') or '—'}",
            f"  record byte offset: {packet.get('pcap_record_offset') if packet.get('pcap_record_offset') is not None else '—'}",
            f"  frame byte offset: {packet.get('pcap_frame_offset') if packet.get('pcap_frame_offset') is not None else '—'}",
            "",
            "Bounded raw frame preview:",
            preview or "—",
            "",
            "Encrypted payload is not presented as plaintext; packet/action links are temporal-only and never claim causality.",
        ]
    )
