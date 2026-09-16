from __future__ import annotations

from collections import Counter
from typing import Any


_CONFIDENCE_ORDER = {
    "UNKNOWN": 0,
    "MEDIUM": 1,
    "HIGH": 2,
    "EXACT": 3,
}


def size_text(value: int) -> str:
    number = float(max(0, int(value)))
    for unit in ("B", "KB", "MB", "GB"):
        if number < 1024 or unit == "GB":
            return f"{number:.1f} {unit}"
        number /= 1024
    return f"{int(value)} B"


def time_text(value: object) -> str:
    text = str(value or "")
    if "T" in text:
        text = text.split("T", 1)[1]
    return text.replace("Z", "")[:12]


def endpoint_text(
    ip_value: object,
    port_value: object,
) -> str:
    ip_text = str(ip_value or "—")
    if port_value in {None, ""}:
        return ip_text
    return f"{ip_text}:{port_value}"


def flow_host(flow: dict[str, Any]) -> str:
    for key in ("tls_sni", "dns_queries"):
        for value in flow.get(key) or []:
            text = str(value or "").strip().rstrip(".")
            if text:
                return text.lower()
    remote_ip = str(
        flow.get("remote_ip") or ""
    ).strip()
    return remote_ip or "unknown-host"


def is_dns_resolution_flow(
    flow: dict[str, Any],
) -> bool:
    protocol = str(
        flow.get("protocol") or ""
    ).lower()
    ports = {
        str(flow.get("local_port") or ""),
        str(flow.get("remote_port") or ""),
    }
    return (
        protocol in {"tcp", "udp"}
        and "53" in ports
        and bool(flow.get("dns_queries"))
    )


def flow_owner(flow: dict[str, Any]) -> str:
    owner = (
        flow.get("owner")
        if isinstance(flow.get("owner"), dict)
        else {}
    )
    confidence = str(
        owner.get("confidence") or "UNKNOWN"
    )
    package = str(owner.get("package") or "")
    if confidence == "UNKNOWN" or not package:
        return "Unknown"
    return package


def flow_confidence(
    flow: dict[str, Any],
) -> str:
    owner = (
        flow.get("owner")
        if isinstance(flow.get("owner"), dict)
        else {}
    )
    value = str(
        owner.get("confidence") or "UNKNOWN"
    )
    return (
        value
        if value in _CONFIDENCE_ORDER
        else "UNKNOWN"
    )


def _unique_strings(
    values: list[object],
) -> list[str]:
    return list(
        dict.fromkeys(
            str(value)
            for value in values
            if str(value or "").strip()
        )
    )


def summarize_flows(
    flows: list[dict[str, Any]],
) -> dict[str, Any]:
    confidence_counts: Counter[str] = Counter()
    protocols: set[str] = set()
    application_protocols: set[str] = set()
    quic_versions: set[str] = set()
    quic_alpn: set[str] = set()
    owners: list[str] = []
    action_ids: list[str] = []
    remote_ips: list[str] = []
    outbound_bytes = 0
    inbound_bytes = 0
    packet_count = 0

    for flow in flows:
        confidence_counts[
            flow_confidence(flow)
        ] += 1
        protocol = str(
            flow.get("protocol") or ""
        ).upper()
        if protocol:
            protocols.add(protocol)
        application_protocols.update(
            str(value)
            for value in flow.get(
                "application_protocols"
            )
            or []
            if value
        )
        quic_versions.update(
            str(value)
            for value in flow.get(
                "quic_versions"
            )
            or []
            if value
        )
        quic_alpn.update(
            str(value)
            for value in flow.get(
                "quic_alpn"
            )
            or []
            if value
        )
        owners.append(flow_owner(flow))
        action_ids.extend(
            flow.get("correlated_action_ids")
            or []
        )
        remote_ip = str(
            flow.get("remote_ip") or ""
        )
        if remote_ip:
            remote_ips.append(remote_ip)
        outbound_bytes += int(
            flow.get("outbound_bytes") or 0
        )
        inbound_bytes += int(
            flow.get("inbound_bytes") or 0
        )
        packet_count += int(
            flow.get("packet_count") or 0
        )

    owner_values = _unique_strings(owners)
    known_owners = [
        value
        for value in owner_values
        if value != "Unknown"
    ]
    has_unknown = "Unknown" in owner_values
    if not known_owners:
        owner_text = "Unknown"
    elif len(known_owners) == 1:
        owner_text = known_owners[0]
        if has_unknown:
            owner_text += " + Unknown"
    else:
        owner_text = (
            f"{len(known_owners)} packages"
            + (" + Unknown" if has_unknown else "")
        )

    best_confidence = max(
        confidence_counts,
        key=lambda value: _CONFIDENCE_ORDER.get(
            value,
            0,
        ),
        default="UNKNOWN",
    )
    first_target_utc = min(
        (
            str(flow.get("first_target_utc") or "")
            for flow in flows
            if flow.get("first_target_utc")
        ),
        default="",
    )
    last_target_utc = max(
        (
            str(flow.get("last_target_utc") or "")
            for flow in flows
            if flow.get("last_target_utc")
        ),
        default="",
    )
    return {
        "flow_count": len(flows),
        "packet_count": packet_count,
        "outbound_bytes": outbound_bytes,
        "inbound_bytes": inbound_bytes,
        "protocols": sorted(protocols),
        "application_protocols": sorted(
            application_protocols
        ),
        "quic_versions": sorted(
            quic_versions
        ),
        "quic_alpn": sorted(
            quic_alpn
        ),
        "owner_text": owner_text,
        "best_confidence": best_confidence,
        "confidence_counts": dict(
            confidence_counts
        ),
        "action_ids": _unique_strings(
            action_ids
        ),
        "remote_ips": _unique_strings(
            remote_ips
        ),
        "first_target_utc": first_target_utc,
        "last_target_utc": last_target_utc,
    }


def summarize_host_flows(
    flows: list[dict[str, Any]],
) -> dict[str, Any]:
    all_summary = summarize_flows(flows)
    resolution_flows = [
        flow
        for flow in flows
        if is_dns_resolution_flow(flow)
    ]
    service_flows = [
        flow
        for flow in flows
        if not is_dns_resolution_flow(flow)
    ]
    ownership_flows = service_flows or flows
    ownership_summary = summarize_flows(
        ownership_flows
    )
    service_remote_ips = _unique_strings(
        [
            flow.get("remote_ip")
            for flow in service_flows
        ]
    )
    resolver_ips = _unique_strings(
        [
            flow.get("remote_ip")
            for flow in resolution_flows
        ]
    )
    service_ports = sorted(
        {
            str(flow.get("remote_port"))
            for flow in service_flows
            if flow.get("remote_port")
            not in {None, ""}
        }
    )
    return {
        **all_summary,
        "service_flow_count": len(service_flows),
        "resolution_flow_count": len(
            resolution_flows
        ),
        "service_remote_ips": service_remote_ips,
        "resolver_ips": resolver_ips,
        "service_ports": service_ports,
        "service_owner_text": ownership_summary[
            "owner_text"
        ],
        "service_best_confidence": (
            ownership_summary["best_confidence"]
        ),
        "service_confidence_counts": (
            ownership_summary["confidence_counts"]
        ),
        "owner_text": ownership_summary[
            "owner_text"
        ],
        "best_confidence": ownership_summary[
            "best_confidence"
        ],
        "confidence_counts": ownership_summary[
            "confidence_counts"
        ],
    }


def group_flows_by_host(
    flows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for flow in flows:
        grouped.setdefault(
            flow_host(flow),
            [],
        ).append(flow)

    values: list[dict[str, Any]] = []
    for host, host_flows in grouped.items():
        host_flows = sorted(
            host_flows,
            key=lambda value: str(
                value.get("first_target_utc")
                or ""
            ),
        )
        summary = summarize_host_flows(host_flows)
        values.append(
            {
                "host": host,
                "flows": host_flows,
                **summary,
            }
        )
    values.sort(
        key=lambda value: (
            str(value.get("first_target_utc") or ""),
            str(value.get("host") or ""),
        )
    )
    return values


def flow_matches(
    flow: dict[str, Any],
    *,
    owner_filter: str,
    protocol_filter: str,
    query: str,
    package: str,
) -> bool:
    owner = flow_owner(flow)
    if owner_filter == "app":
        if owner != package:
            return False
    elif owner_filter == "unknown":
        if owner != "Unknown":
            return False

    protocol = str(
        flow.get("protocol") or ""
    ).lower()
    if (
        protocol_filter != "all"
        and protocol != protocol_filter
    ):
        return False

    query = query.strip().lower()
    if not query:
        return True

    owner_value = (
        flow.get("owner")
        if isinstance(flow.get("owner"), dict)
        else {}
    )
    searchable = " ".join(
        [
            flow_host(flow),
            flow_owner(flow),
            str(flow.get("flow_id") or ""),
            protocol,
            str(flow.get("local_ip") or ""),
            str(flow.get("local_port") or ""),
            str(flow.get("remote_ip") or ""),
            str(flow.get("remote_port") or ""),
            " ".join(
                str(value)
                for value in flow.get("tls_sni") or []
            ),
            " ".join(
                str(value)
                for value in flow.get("dns_queries") or []
            ),
            " ".join(
                str(value)
                for value in flow.get(
                    "application_protocols"
                )
                or []
            ),
            " ".join(
                str(value)
                for value in flow.get(
                    "quic_versions"
                )
                or []
            ),
            " ".join(
                str(value)
                for value in flow.get(
                    "quic_alpn"
                )
                or []
            ),
            " ".join(
                str(value)
                for value in owner_value.get("processes") or []
            ),
            " ".join(
                str(value)
                for value in flow.get("correlated_action_ids") or []
            ),
        ]
    ).lower()
    return query in searchable


def build_action_index(
    actions: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        str(action.get("action_id") or ""): action
        for action in actions
        if isinstance(action, dict)
        and action.get("action_id")
    }


def action_label(
    action_id: str,
    action_index: dict[str, dict[str, Any]],
) -> str:
    action = action_index.get(action_id) or {}
    correlation = (
        action.get("correlation")
        if isinstance(action.get("correlation"), dict)
        else {}
    )
    when = (
        correlation.get(
            "target_started_utc_estimate"
        )
        or action.get("host_started_utc")
        or action.get("host_utc")
        or ""
    )
    action_name = str(
        action.get("action") or "action"
    )
    return (
        f"{time_text(when)} • "
        f"{action_name} • {action_id}"
    )


def format_host_details(
    host: str,
    flows: list[dict[str, Any]],
    action_index: dict[str, dict[str, Any]],
) -> str:
    summary = summarize_host_flows(flows)
    action_ids = [
        str(value)
        for value in summary.get("action_ids") or []
        if value
    ]
    confidence_counts = (
        summary.get("service_confidence_counts")
        if isinstance(
            summary.get("service_confidence_counts"),
            dict,
        )
        else {}
    )
    confidence_text = " / ".join(
        f"{key} {int(confidence_counts.get(key) or 0)}"
        for key in (
            "EXACT",
            "HIGH",
            "MEDIUM",
            "UNKNOWN",
        )
        if int(confidence_counts.get(key) or 0) > 0
    ) or "UNKNOWN"
    service_ips = [
        str(value)
        for value in summary.get("service_remote_ips") or []
        if value
    ]
    resolver_ips = [
        str(value)
        for value in summary.get("resolver_ips") or []
        if value
    ]
    service_ports = [
        str(value)
        for value in summary.get("service_ports") or []
        if value
    ]
    lines = [
        f"Хост: {host or 'unknown-host'}",
        "",
        "Активность",
        (
            f"  Период: {summary.get('first_target_utc') or '—'}"
            f" → {summary.get('last_target_utc') or '—'}"
        ),
        (
            f"  Соединений: {summary.get('flow_count') or 0}"
            f" (service {summary.get('service_flow_count') or 0}"
            f", DNS {summary.get('resolution_flow_count') or 0})"
        ),
        (
            f"  Транспорт: "
            f"{' + '.join(summary.get('protocols') or []) or '—'}"
        ),
        (
            f"  Приложение: "
            f"{' + '.join(summary.get('application_protocols') or []) or '—'}"
        ),
        (
            f"  Трафик: "
            f"↑ {size_text(int(summary.get('outbound_bytes') or 0))}"
            f"  ↓ {size_text(int(summary.get('inbound_bytes') or 0))}"
        ),
        (
            f"  Пакеты: {int(summary.get('packet_count') or 0)}"
        ),
        "",
        "Service endpoints",
        (
            "  Remote IP: "
            + (", ".join(service_ips) or "—")
        ),
        (
            "  Remote ports: "
            + (", ".join(service_ports) or "—")
        ),
        (
            f"  Owner: {summary.get('service_owner_text') or 'Unknown'}"
        ),
        f"  Confidence: {confidence_text}",
    ]
    if resolver_ips or int(
        summary.get("resolution_flow_count") or 0
    ):
        lines.extend(
            [
                "",
                "DNS resolution",
                (
                    "  Resolver IP: "
                    + (", ".join(resolver_ips) or "—")
                ),
                (
                    f"  DNS flows: "
                    f"{int(summary.get('resolution_flow_count') or 0)}"
                ),
            ]
        )
    if (
        int(summary.get("service_flow_count") or 0) == 0
        and int(summary.get("resolution_flow_count") or 0) > 0
    ):
        lines.append(
            "  Для этого имени наблюдалось только DNS-разрешение; "
            "service flow с этим именем не подтверждён."
        )
    lines.extend(
        [
            "",
            "Timeline",
            f"  Связанных действий: {len(action_ids)}",
        ]
    )
    for action_id in action_ids:
        lines.append(
            "  • "
            + action_label(
                action_id,
                action_index,
            )
        )
    if not action_ids:
        lines.append(
            "  В temporal window действий не найдено."
        )
    return "\n".join(lines)


def format_flow_details(
    flow: dict[str, Any],
    action_index: dict[str, dict[str, Any]],
) -> str:
    owner = (
        flow.get("owner")
        if isinstance(flow.get("owner"), dict)
        else {}
    )
    action_ids = [
        str(value)
        for value in (
            flow.get("correlated_action_ids")
            or []
        )
        if value
    ]
    confidence_counts = (
        flow.get("packet_confidence_counts")
        if isinstance(
            flow.get("packet_confidence_counts"),
            dict,
        )
        else {}
    )
    ambiguity = [
        str(value)
        for value in owner.get("ambiguity") or []
        if value
    ]
    processes = [
        str(value)
        for value in owner.get("processes") or []
        if value
    ]
    pids = [
        str(value)
        for value in owner.get("pids") or []
        if value
    ]

    lines = [
        f"Хост: {flow_host(flow)}",
        f"Flow: {flow.get('flow_id') or '—'}",
        "",
        "Соединение",
        (
            f"  {str(flow.get('protocol') or '').upper()}  "
            f"{endpoint_text(flow.get('local_ip'), flow.get('local_port'))}"
            "  →  "
            f"{endpoint_text(flow.get('remote_ip'), flow.get('remote_port'))}"
        ),
        (
            f"  Время: {flow.get('first_target_utc') or '—'}"
            f" → {flow.get('last_target_utc') or '—'}"
        ),
        (
            f"  Длительность: "
            f"{float(flow.get('duration_seconds') or 0):.3f} с"
        ),
        "",
        "Трафик",
        (
            f"  ↑ {size_text(int(flow.get('outbound_bytes') or 0))}"
            f" / {int(flow.get('outbound_packet_count') or 0)} pkt"
        ),
        (
            f"  ↓ {size_text(int(flow.get('inbound_bytes') or 0))}"
            f" / {int(flow.get('inbound_packet_count') or 0)} pkt"
        ),
    ]

    application_protocols = [
        str(value)
        for value in (
            flow.get(
                "application_protocols"
            )
            or []
        )
        if value
    ]
    quic_versions = [
        str(value)
        for value in (
            flow.get("quic_versions")
            or []
        )
        if value
    ]
    quic_alpn = [
        str(value)
        for value in (
            flow.get("quic_alpn")
            or []
        )
        if value
    ]
    if (
        application_protocols
        or quic_versions
        or quic_alpn
    ):
        lines.extend(
            [
                "",
                "Протокол приложения",
                (
                    "  Application: "
                    + (
                        ", ".join(
                            application_protocols
                        )
                        or "QUIC"
                    )
                ),
            ]
        )
        if quic_versions:
            lines.append(
                "  QUIC version: "
                + ", ".join(quic_versions)
            )
        if quic_alpn:
            lines.append(
                "  ALPN: "
                + ", ".join(quic_alpn)
            )
        lines.append(
            "  QUIC Initial decrypted: "
            + str(
                int(
                    flow.get(
                        "quic_initial_decrypted_packet_count"
                    )
                    or 0
                )
            )
        )

    lines.extend(
        [
            "",
            "Владелец",
        f"  Package: {flow_owner(flow)}",
        f"  Confidence: {flow_confidence(flow)}",
        f"  Evidence: {owner.get('evidence') or '—'}",
        ]
    )

    if processes:
        lines.append(
            "  Process: " + ", ".join(processes)
        )
    if pids:
        lines.append(
            "  PID: " + ", ".join(pids)
        )
    if owner.get("inode"):
        lines.append(
            f"  Socket inode: {owner.get('inode')}"
        )
    if confidence_counts:
        lines.append(
            "  Packet confidence: "
            + " / ".join(
                f"{key} {int(confidence_counts.get(key) or 0)}"
                for key in (
                    "EXACT",
                    "HIGH",
                    "MEDIUM",
                    "UNKNOWN",
                )
            )
        )
    if ambiguity:
        lines.append(
            "  Ограничения: "
            + ", ".join(ambiguity)
        )

    sni = [
        str(value)
        for value in flow.get("tls_sni") or []
        if value
    ]
    dns = [
        str(value)
        for value in flow.get("dns_queries") or []
        if value
    ]
    if sni or dns:
        lines.extend(["", "Имена"])
        if sni:
            lines.append(
                "  TLS SNI: " + ", ".join(sni)
            )
        if dns:
            lines.append(
                "  DNS: " + ", ".join(dns)
            )

    lines.extend(
        [
            "",
            "Timeline",
            (
                f"  Связанных действий: {len(action_ids)}"
            ),
        ]
    )
    for action_id in action_ids:
        lines.append(
            "  • "
            + action_label(
                action_id,
                action_index,
            )
        )

    if not action_ids:
        lines.append(
            "  В temporal window действий не найдено."
        )

    return "\n".join(lines)
