from __future__ import annotations

from collections import defaultdict
from typing import Any

from apk_research.desktop.evidence_view_model import build_evidence_model


def _text(value: Any) -> str:
    return str(value or "").strip()


def _process_key(flow_node: dict[str, Any]) -> tuple[str, ...]:
    owner = flow_node.get("owner")
    if not isinstance(owner, dict):
        owner = {}
    inode = owner.get("inode")
    uid = owner.get("uid")
    processes = tuple(sorted(_text(value) for value in owner.get("processes") or [] if _text(value)))
    pids = tuple(sorted(_text(value) for value in owner.get("pids") or [] if _text(value)))
    if inode is not None:
        return ("inode", _text(inode), _text(uid), *processes, *pids)
    if processes or pids:
        return ("process", _text(uid), *processes, *pids)
    return ()


def build_evidence_model_v024(
    flows: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    *,
    package: str = "",
) -> dict[str, Any]:
    """Extend the existing presentation graph with reverse process/socket paths."""

    model = build_evidence_model(flows, actions, package=package)
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)

    for host in model.get("hosts") or []:
        if not isinstance(host, dict):
            continue
        for flow_node in host.get("flow_nodes") or []:
            if not isinstance(flow_node, dict):
                continue
            key = _process_key(flow_node)
            if key:
                grouped[key].append(flow_node)

    process_nodes: list[dict[str, Any]] = []
    for key, flow_nodes in grouped.items():
        first = flow_nodes[0]
        owner = first.get("owner")
        if not isinstance(owner, dict):
            owner = {}
        processes = [
            _text(value)
            for value in owner.get("processes") or []
            if _text(value)
        ]
        pids = list(owner.get("pids") or [])
        inode = owner.get("inode")
        process_nodes.append(
            {
                "kind": "process_index",
                "identity_key": "|".join(key),
                "package": _text(owner.get("package")) or package,
                "uid": owner.get("uid"),
                "processes": processes,
                "pids": pids,
                "inode": inode,
                "confidence": _text(owner.get("confidence")) or "UNKNOWN",
                "evidence": _text(owner.get("evidence")),
                "flow_ids": [
                    _text(flow_node.get("flow_id"))
                    for flow_node in flow_nodes
                    if _text(flow_node.get("flow_id"))
                ],
                "flow_nodes": flow_nodes,
                "relation_type": "socket-attribution",
                "relation_strength": _text(owner.get("confidence")) or "UNKNOWN",
                "causal_claim": False,
            }
        )

    process_nodes.sort(
        key=lambda node: (
            ",".join(node.get("processes") or []),
            _text(node.get("inode")),
            _text(node.get("uid")),
        )
    )
    model["processes"] = process_nodes
    model["process_count"] = len(process_nodes)
    model["relation_policy"] = {
        "action_flow": "temporal-only",
        "flow_packet": "raw-observation",
        "flow_process_socket": "attribution-confidence",
        "derived_raw": "locator-only",
        "causal_upgrade": False,
    }
    return model


def format_process_index_details(node: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Process / Socket reverse index",
            f"Package: {_text(node.get('package')) or '—'}",
            f"Processes: {', '.join(_text(value) for value in node.get('processes') or []) or '—'}",
            f"PIDs: {', '.join(_text(value) for value in node.get('pids') or []) or '—'}",
            f"UID: {node.get('uid') if node.get('uid') is not None else '—'}",
            f"Socket inode: {node.get('inode') if node.get('inode') is not None else '—'}",
            f"Attribution confidence: {_text(node.get('confidence')) or 'UNKNOWN'}",
            f"Evidence: {_text(node.get('evidence')) or '—'}",
            f"Related flows: {', '.join(_text(value) for value in node.get('flow_ids') or []) or '—'}",
            "",
            "Эта обратная навигация группирует уже существующие flow→socket/process attribution и не создаёт новую причинную связь.",
        ]
    )
