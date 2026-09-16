from __future__ import annotations

from typing import Any

from apk_research.desktop.network_view_model import (
    action_label,
    build_action_index,
    endpoint_text,
    flow_confidence,
    flow_host,
    flow_owner,
)


def packet_ranges_text(
    ranges: list[object],
) -> str:
    parts: list[str] = []
    for item in ranges:
        if (
            not isinstance(item, (list, tuple))
            or len(item) != 2
        ):
            continue
        try:
            start = int(item[0])
            end = int(item[1])
        except (TypeError, ValueError):
            continue
        if start <= 0 or end < start:
            continue
        parts.append(
            str(start)
            if start == end
            else f"{start}-{end}"
        )
    return ", ".join(parts) or "—"


def flow_process_socket_text(
    flow: dict[str, Any],
) -> str:
    owner = (
        flow.get("owner")
        if isinstance(flow.get("owner"), dict)
        else {}
    )
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
    parts: list[str] = []
    if processes:
        parts.append(
            "process "
            + ", ".join(processes)
        )
    if pids:
        parts.append(
            "PID "
            + ", ".join(pids)
        )
    if owner.get("inode"):
        parts.append(
            f"inode {owner.get('inode')}"
        )
    return " • ".join(parts) or "нет socket/process evidence"


def flow_raw_evidence_text(
    flow: dict[str, Any],
) -> str:
    evidence = (
        flow.get("raw_evidence")
        if isinstance(
            flow.get("raw_evidence"),
            dict,
        )
        else {}
    )
    pcap = str(
        evidence.get("pcap_artifact")
        or "01_raw/network/traffic.pcap"
    )
    ranges = packet_ranges_text(
        evidence.get(
            "pcap_packet_ranges"
        )
        or []
    )
    lines = [
        f"PCAP: {pcap}",
        f"Packets: {ranges}",
    ]
    first_offset = evidence.get(
        "first_pcap_record_offset"
    )
    last_offset = evidence.get(
        "last_pcap_record_offset"
    )
    if first_offset is not None:
        if last_offset == first_offset:
            lines.append(
                f"PCAP record offset: {first_offset}"
            )
        else:
            lines.append(
                "PCAP record offsets: "
                f"{first_offset} … {last_offset}"
            )

    socket_artifact = str(
        evidence.get(
            "socket_snapshot_artifact"
        )
        or ""
    )
    if socket_artifact:
        lines.append(
            f"Socket evidence: {socket_artifact}"
        )
        if evidence.get("socket_inode"):
            lines.append(
                "Socket inode: "
                + str(
                    evidence.get(
                        "socket_inode"
                    )
                )
            )
        first_observed = evidence.get(
            "socket_first_observed_utc"
        )
        last_observed = evidence.get(
            "socket_last_observed_utc"
        )
        if first_observed or last_observed:
            lines.append(
                "Socket observed: "
                f"{first_observed or '—'}"
                " → "
                f"{last_observed or '—'}"
            )
    return "\n".join(lines)


def build_evidence_groups(
    flows: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    action_index = build_action_index(
        actions
    )
    order = [
        str(action.get("action_id") or "")
        for action in actions
        if action.get("action_id")
    ]
    by_action: dict[
        str,
        list[dict[str, Any]],
    ] = {
        action_id: []
        for action_id in order
    }
    unlinked: list[dict[str, Any]] = []

    for flow in flows:
        action_ids = [
            str(value)
            for value in (
                flow.get(
                    "correlated_action_ids"
                )
                or []
            )
            if value
        ]
        if not action_ids:
            unlinked.append(flow)
            continue
        for action_id in action_ids:
            if action_id not in by_action:
                by_action[action_id] = []
                order.append(action_id)
            by_action[action_id].append(flow)

    groups: list[dict[str, Any]] = []
    for action_id in order:
        action_flows = by_action.get(
            action_id,
            [],
        )
        if not action_flows:
            continue
        action = (
            action_index.get(action_id)
            or {}
        )
        hosts: dict[
            str,
            list[dict[str, Any]],
        ] = {}
        for flow in action_flows:
            hosts.setdefault(
                flow_host(flow),
                [],
            ).append(flow)
        host_values = [
            {
                "host": host,
                "flows": sorted(
                    host_flows,
                    key=lambda item: str(
                        item.get(
                            "first_target_utc"
                        )
                        or ""
                    ),
                ),
            }
            for host, host_flows
            in hosts.items()
        ]
        host_values.sort(
            key=lambda item: (
                str(
                    item["flows"][0].get(
                        "first_target_utc"
                    )
                    or ""
                )
                if item["flows"]
                else "",
                str(item["host"]),
            )
        )
        groups.append(
            {
                "action_id": action_id,
                "action": action,
                "label": (
                    action_label(
                        action_id,
                        action_index,
                    )
                    if action
                    else (
                        f"{action_id} • action record unavailable"
                    )
                ),
                "hosts": host_values,
                "flow_count": len(
                    action_flows
                ),
            }
        )

    if unlinked:
        hosts: dict[
            str,
            list[dict[str, Any]],
        ] = {}
        for flow in unlinked:
            hosts.setdefault(
                flow_host(flow),
                [],
            ).append(flow)
        host_values = [
            {
                "host": host,
                "flows": sorted(
                    host_flows,
                    key=lambda item: str(
                        item.get(
                            "first_target_utc"
                        )
                        or ""
                    ),
                ),
            }
            for host, host_flows
            in hosts.items()
        ]
        host_values.sort(
            key=lambda item: (
                str(
                    item["flows"][0].get(
                        "first_target_utc"
                    )
                    or ""
                )
                if item["flows"]
                else "",
                str(item["host"]),
            )
        )
        groups.append(
            {
                "action_id": "",
                "action": {},
                "label": (
                    "Без temporal-связи с действием"
                ),
                "hosts": host_values,
                "flow_count": len(unlinked),
            }
        )
    return groups


def format_evidence_chain(
    action: dict[str, Any],
    host: str,
    flow: dict[str, Any],
) -> str:
    action_id = str(
        action.get("action_id") or "—"
    )
    action_name = str(
        action.get("action") or "—"
    )
    owner = (
        flow.get("owner")
        if isinstance(flow.get("owner"), dict)
        else {}
    )
    lines = [
        "Evidence chain",
        f"  Action: {action_name} • {action_id}",
        f"  Host: {host or flow_host(flow)}",
        (
            f"  Flow: {flow.get('flow_id') or '—'}"
            f" • {str(flow.get('protocol') or '').upper()}"
        ),
        (
            "  Endpoints: "
            f"{endpoint_text(flow.get('local_ip'), flow.get('local_port'))}"
            " → "
            f"{endpoint_text(flow.get('remote_ip'), flow.get('remote_port'))}"
        ),
        (
            f"  Owner: {flow_owner(flow)}"
            f" • {flow_confidence(flow)}"
        ),
        (
            "  Process/socket: "
            + flow_process_socket_text(flow)
        ),
        "",
        flow_raw_evidence_text(flow),
        "",
        (
            "Attribution evidence: "
            + str(
                owner.get("evidence")
                or "—"
            )
        ),
        (
            "Action relation: temporal-only; "
            "this view does not claim causality."
        ),
    ]
    return "\n".join(lines)
