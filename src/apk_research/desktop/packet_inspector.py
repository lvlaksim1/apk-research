from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path
from typing import Any, BinaryIO

from apk_research.network_attribution import canonical_connection_key
from apk_research.quic import QuicFlowInspector
from apk_research.timeline import (
    _decode_ip,
    _dns_query_name,
    _iso_epoch,
    _network_payload,
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
        metadata = _packet_metadata(decoded, direction, quic)
        preview, truncated = _format_hex_preview(
            raw_frame,
            hex_preview_bytes,
        )
        packet_index = total_packets
        selected.append(
            {
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
            }
        )

    return {
        "flow_id": str(flow.get("flow_id") or ""),
        "protocol": target_key[0],
        "packets": selected,
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
        report.update(
            {
                "archive": str(archive),
                "artifact": RAW_PCAP_ARTIFACT,
                "artifact_size": info.file_size,
                "artifact_compressed_size": info.compress_size,
                "artifact_crc32": f"{info.CRC:08x}",
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
    ):
        value = packet.get(key)
        if value not in {None, ""}:
            values.append(str(value))
    values.extend(
        str(item)
        for item in packet.get("quic_alpn") or []
        if item
    )
    return " ".join(values).lower()


def packet_metadata_label(packet: dict[str, Any]) -> str:
    parts: list[str] = []
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
    if packet.get("hex_preview_truncated"):
        preview += "\n… preview truncated; locator still points to the complete raw packet"

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
            "Encrypted payload is not presented as plaintext; this view is a locator/inspection layer over the original PCAP.",
        ]
    )
