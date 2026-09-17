from __future__ import annotations

from collections import defaultdict
from typing import Any

from apk_research.desktop.network_view_model import (
    action_label,
    build_action_index,
    flow_host,
)

RAW_PCAP_ARTIFACT = "01_raw/network/traffic.pcap"
RAW_SOCKET_ARTIFACT = "01_raw/network/socket-snapshots.txt"
NORMALIZED_SOCKET_ARTIFACT = "02_normalized/socket-attribution.json"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _owner(flow: dict[str, Any]) -> dict[str, Any]:
    value = flow.get("owner")
    return value if isinstance(value, dict) else {}


def _action_ids(flow: dict[str, Any]) -> list[str]:
    return [
        _text(value)
        for value in flow.get("correlated_action_ids") or []
        if _text(value)
    ]


def _flow_locator(flow: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact": RAW_PCAP_ARTIFACT,
        "flow_id": _text(flow.get("flow_id")),
        "protocol": _text(flow.get("protocol")),
        "first_target_utc": _text(flow.get("first_target_utc")),
        "last_target_utc": _text(flow.get("last_target_utc")),
        "local_ip": _text(flow.get("local_ip")),
        "local_port": flow.get("local_port"),
        "remote_ip": _text(flow.get("remote_ip")),
        "remote_port": flow.get("remote_port"),
    }


def _socket_locator(flow: dict[str, Any]) -> dict[str, Any]:
    owner = _owner(flow)
    return {
        "artifact": RAW_SOCKET_ARTIFACT,
        "normalized_artifact": NORMALIZED_SOCKET_ARTIFACT,
        "flow_id": _text(flow.get("flow_id")),
        "inode": owner.get("inode"),
        "pids": list(owner.get("pids") or []),
        "processes": list(owner.get("processes") or []),
        "uid": owner.get("uid"),
        "confidence": _text(owner.get("confidence")) or "UNKNOWN",
        "evidence": _text(owner.get("evidence")),
        "first_target_utc": _text(flow.get("first_target_utc")),
        "last_target_utc": _text(flow.get("last_target_utc")),
    }


def build_evidence_model(
    flows: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    *,
    package: str = "",
) -> dict[str, Any]:
    """Build a presentation-only evidence graph over existing artifacts.

    No new forensic claim is created here. Action/flow relations remain the
    temporal correlations already recorded in Research Timeline.
    """

    flow_index = {
        _text(flow.get("flow_id")): flow
        for flow in flows
        if _text(flow.get("flow_id"))
    }
    action_index = build_action_index(actions)

    action_nodes: list[dict[str, Any]] = []
    for action in actions:
        action_id = _text(action.get("action_id"))
        if not action_id:
            continue
        correlation = action.get("correlation")
        if not isinstance(correlation, dict):
            correlation = {}
        network = correlation.get("network")
        if not isinstance(network, dict):
            network = {}
        flow_ids = [
            _text(value)
            for value in network.get("flow_ids") or []
            if _text(value) in flow_index
        ]
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for flow_id in flow_ids:
            flow = flow_index[flow_id]
            grouped[flow_host(flow)].append(flow)
        host_nodes = [
            _host_node(host, grouped[host], action_index)
            for host in sorted(grouped)
        ]
        action_nodes.append(
            {
                "kind": "action",
                "action_id": action_id,
                "label": action_label(action_id, action_index),
                "action": action,
                "hosts": host_nodes,
                "flow_ids": flow_ids,
                "correlation_type": _text(
                    correlation.get("type")
                )
                or "temporal-only",
                "causal_claim": bool(
                    correlation.get("causal_claim", False)
                ),
            }
        )

    host_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for flow in flows:
        host_map[flow_host(flow)].append(flow)
    host_nodes = [
        _host_node(host, host_map[host], action_index)
        for host in sorted(host_map)
    ]

    return {
        "package": package,
        "flow_count": len(flows),
        "action_count": len(action_nodes),
        "host_count": len(host_nodes),
        "actions": action_nodes,
        "hosts": host_nodes,
        "flow_index": flow_index,
        "action_index": action_index,
        "raw_artifacts": [
            RAW_PCAP_ARTIFACT,
            RAW_SOCKET_ARTIFACT,
        ],
    }


def _host_node(
    host: str,
    flows: list[dict[str, Any]],
    action_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    action_ids: list[str] = []
    seen_actions: set[str] = set()
    flow_nodes = []
    for flow in flows:
        for action_id in _action_ids(flow):
            if action_id not in seen_actions:
                seen_actions.add(action_id)
                action_ids.append(action_id)
        flow_nodes.append(_flow_node(flow, action_index))
    return {
        "kind": "host",
        "host": host,
        "flow_count": len(flow_nodes),
        "flow_nodes": flow_nodes,
        "action_ids": action_ids,
    }


def _flow_node(
    flow: dict[str, Any],
    action_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    owner = _owner(flow)
    action_ids = _action_ids(flow)
    process_nodes = []
    processes = [
        _text(value)
        for value in owner.get("processes") or []
        if _text(value)
    ]
    pids = list(owner.get("pids") or [])
    if processes or pids or owner.get("inode") is not None:
        process_nodes.append(
            {
                "kind": "process_socket",
                "processes": processes,
                "pids": pids,
                "inode": owner.get("inode"),
                "uid": owner.get("uid"),
                "confidence": _text(owner.get("confidence")) or "UNKNOWN",
                "evidence": _text(owner.get("evidence")),
                "raw_locator": _socket_locator(flow),
            }
        )
    return {
        "kind": "flow",
        "flow_id": _text(flow.get("flow_id")),
        "host": flow_host(flow),
        "flow": flow,
        "owner": owner,
        "action_ids": action_ids,
        "action_labels": [
            action_label(action_id, action_index)
            for action_id in action_ids
        ],
        "process_nodes": process_nodes,
        "raw_locator": _flow_locator(flow),
    }


def node_search_text(node: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "action_id",
        "label",
        "host",
        "flow_id",
        "correlation_type",
        "confidence",
        "evidence",
    ):
        value = node.get(key)
        if value is not None:
            values.append(_text(value))
    for key in (
        "action_ids",
        "action_labels",
        "processes",
        "pids",
    ):
        values.extend(_text(value) for value in node.get(key) or [])
    flow = node.get("flow")
    if isinstance(flow, dict):
        values.extend(
            _text(flow.get(key))
            for key in (
                "protocol",
                "local_ip",
                "local_port",
                "remote_ip",
                "remote_port",
            )
        )
        for key in (
            "dns_queries",
            "tls_sni",
            "quic_sni",
            "quic_alpn",
            "application_protocols",
        ):
            values.extend(_text(value) for value in flow.get(key) or [])
    return " ".join(value for value in values if value).lower()


def format_evidence_details(node: dict[str, Any]) -> str:
    kind = _text(node.get("kind"))
    if kind == "action":
        return "\n".join(
            [
                f"Action: {_text(node.get('action_id'))}",
                f"{_text(node.get('label'))}",
                f"Correlation: {_text(node.get('correlation_type'))}",
                f"Causal claim: {'yes' if node.get('causal_claim') else 'no'}",
                f"Flows: {len(node.get('flow_ids') or [])}",
                "",
                "Связь Action → Flow является временной корреляцией, а не доказанной причинностью.",
            ]
        )
    if kind == "host":
        return "\n".join(
            [
                f"Host: {_text(node.get('host'))}",
                f"Flows: {int(node.get('flow_count') or 0)}",
                f"Actions: {len(node.get('action_ids') or [])}",
            ]
        )
    if kind == "flow":
        flow = node.get("flow") if isinstance(node.get("flow"), dict) else {}
        owner = node.get("owner") if isinstance(node.get("owner"), dict) else {}
        locator = node.get("raw_locator") if isinstance(node.get("raw_locator"), dict) else {}
        return "\n".join(
            [
                f"Flow: {_text(node.get('flow_id'))}",
                f"Host: {_text(node.get('host'))}",
                f"Transport: {_text(flow.get('protocol')).upper() or '—'}",
                f"Local: {_text(flow.get('local_ip'))}:{flow.get('local_port') or '—'}",
                f"Remote: {_text(flow.get('remote_ip'))}:{flow.get('remote_port') or '—'}",
                f"Owner: {_text(owner.get('package')) or 'Unknown'}",
                f"Confidence: {_text(owner.get('confidence')) or 'UNKNOWN'}",
                f"Actions: {len(node.get('action_ids') or [])}",
                "",
                "Raw PCAP locator:",
                f"  artifact: {_text(locator.get('artifact'))}",
                f"  time: {_text(locator.get('first_target_utc'))} .. {_text(locator.get('last_target_utc'))}",
                f"  5-tuple: {_text(locator.get('protocol'))} {_text(locator.get('local_ip'))}:{locator.get('local_port')} ↔ {_text(locator.get('remote_ip'))}:{locator.get('remote_port')}",
            ]
        )
    if kind == "process_socket":
        locator = node.get("raw_locator") if isinstance(node.get("raw_locator"), dict) else {}
        return "\n".join(
            [
                "Process / Socket evidence",
                f"Processes: {', '.join(_text(value) for value in node.get('processes') or []) or '—'}",
                f"PIDs: {', '.join(_text(value) for value in node.get('pids') or []) or '—'}",
                f"UID: {node.get('uid') if node.get('uid') is not None else '—'}",
                f"Socket inode: {node.get('inode') if node.get('inode') is not None else '—'}",
                f"Confidence: {_text(node.get('confidence')) or 'UNKNOWN'}",
                f"Evidence: {_text(node.get('evidence')) or '—'}",
                "",
                f"Raw socket artifact: {_text(locator.get('artifact'))}",
                f"Normalized attribution: {_text(locator.get('normalized_artifact'))}",
            ]
        )
    if kind == "raw":
        locator = node.get("locator") if isinstance(node.get("locator"), dict) else {}
        return "\n".join(
            [
                f"Raw evidence: {_text(locator.get('artifact'))}",
                f"Flow: {_text(locator.get('flow_id')) or '—'}",
                f"Time: {_text(locator.get('first_target_utc'))} .. {_text(locator.get('last_target_utc'))}",
                f"Inode: {locator.get('inode') if locator.get('inode') is not None else '—'}",
                "",
                "Этот locator не заменяет RAW-артефакт; он задаёт проверяемый путь обратно к исходным данным ZIP.",
            ]
        )
    return ""
