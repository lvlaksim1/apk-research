from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from apk_research.desktop.screen_evidence import locate_screen_moment


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_utc(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        result = datetime.fromisoformat(text)
    except ValueError:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _action_index(actions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        _text(action.get("action_id")): action
        for action in actions
        if _text(action.get("action_id"))
    }


def _flow_index(flows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        _text(flow.get("flow_id")): flow
        for flow in flows
        if _text(flow.get("flow_id"))
    }


def _event_flow_ids(
    event: dict[str, Any],
    action: dict[str, Any] | None,
    flows: dict[str, dict[str, Any]],
) -> list[str]:
    result: list[str] = []
    event_flow = _text(event.get("flow_id"))
    if event_flow and event_flow in flows:
        result.append(event_flow)

    if isinstance(action, dict):
        correlation = action.get("correlation")
        if not isinstance(correlation, dict):
            correlation = {}
        network = correlation.get("network")
        if not isinstance(network, dict):
            network = {}
        for value in network.get("flow_ids") or []:
            flow_id = _text(value)
            if flow_id and flow_id in flows and flow_id not in result:
                result.append(flow_id)
    return result


def _event_relation(
    event: dict[str, Any],
    action: dict[str, Any] | None,
    flow_ids: list[str],
) -> tuple[str, str, bool]:
    kind = _text(event.get("kind"))
    if kind == "user_action" and flow_ids:
        correlation = action.get("correlation") if isinstance(action, dict) else {}
        if not isinstance(correlation, dict):
            correlation = {}
        relation = _text(correlation.get("attribution")) or _text(correlation.get("type"))
        relation = relation or "temporal-only"
        confidence = _text(correlation.get("causal_confidence")) or "bounded"
        return relation, confidence, bool(correlation.get("causal_claim", False))
    if kind == "network_flow":
        return "observed-normalized-flow", "direct-observation", False
    if kind == "lifecycle":
        return "observed-lifecycle", "direct-observation", False
    if kind == "user_action":
        return "observed-action", "direct-observation", False
    return "observed-event", "direct-observation", False


def _owner_summary(flow: dict[str, Any]) -> str:
    owner = flow.get("owner")
    if not isinstance(owner, dict):
        return ""
    process = ",".join(_text(value) for value in owner.get("processes") or [] if _text(value))
    pid = ",".join(_text(value) for value in owner.get("pids") or [] if _text(value))
    inode = owner.get("inode")
    confidence = _text(owner.get("confidence")) or "UNKNOWN"
    pieces = [piece for piece in [process, f"pid={pid}" if pid else "", f"inode={inode}" if inode is not None else "", confidence] if piece]
    return " • ".join(pieces)


def build_unified_session_model(
    *,
    timeline: dict[str, Any],
    flows: list[dict[str, Any]],
    screen_index: dict[str, Any],
    package: str = "",
) -> dict[str, Any]:
    """Build one chronological navigation model over existing evidence.

    The model is presentation-only. It links already-recorded action, network,
    process/socket and screen evidence while preserving each relationship's
    provenance and explicitly keeping causal_claim false unless the source
    artifact itself says otherwise.
    """

    actions = [
        action
        for action in timeline.get("user_actions") or []
        if isinstance(action, dict)
    ]
    events = [
        event
        for event in timeline.get("events") or []
        if isinstance(event, dict)
    ]
    actions_by_id = _action_index(actions)
    flows_by_id = _flow_index(flows)

    rows: list[dict[str, Any]] = []
    for sequence, event in enumerate(events):
        action_id = _text(event.get("action_id"))
        action = actions_by_id.get(action_id)
        flow_ids = _event_flow_ids(event, action, flows_by_id)
        relation_type, relation_strength, causal_claim = _event_relation(
            event,
            action,
            flow_ids,
        )
        target_utc = _text(event.get("target_utc"))
        screen = locate_screen_moment(screen_index, target_utc) if target_utc else None
        event_flows = [flows_by_id[value] for value in flow_ids if value in flows_by_id]
        owner_summaries = [
            value
            for value in (_owner_summary(flow) for flow in event_flows)
            if value
        ]
        rows.append(
            {
                "sequence": sequence,
                "kind": _text(event.get("kind")),
                "name": _text(event.get("name")),
                "target_utc": target_utc,
                "host_utc": _text(event.get("host_utc")),
                "time_domain": "target" if target_utc else "host-only",
                "event": event,
                "action_id": action_id,
                "action": action if isinstance(action, dict) else {},
                "flow_ids": flow_ids,
                "flows": event_flows,
                "packet_count": sum(int(flow.get("packet_count") or 0) for flow in event_flows),
                "owners": owner_summaries,
                "screen": screen,
                "relation_type": relation_type,
                "relation_strength": relation_strength,
                "causal_claim": causal_claim,
            }
        )

    rows.sort(
        key=lambda row: (
            _parse_utc(row.get("target_utc"))
            or _parse_utc(row.get("host_utc"))
            or datetime.min.replace(tzinfo=timezone.utc),
            int(row.get("sequence") or 0),
        )
    )
    for index, row in enumerate(rows):
        row["timeline_index"] = index

    return {
        "package": package,
        "rows": rows,
        "row_count": len(rows),
        "action_count": len(actions),
        "flow_count": len(flows_by_id),
        "screen_available": bool(screen_index.get("available")),
        "screen_mapping_method": _text(screen_index.get("mapping_method")),
        "screen_mapping_confidence": _text(screen_index.get("confidence")),
        "screen_index": screen_index,
        "flow_index": flows_by_id,
        "action_index": actions_by_id,
        "evidence_policy": {
            "raw_is_authoritative": True,
            "action_flow": "temporal-only unless source says otherwise",
            "screen_links": "time-aligned-navigation",
            "screen_causal_claim": False,
        },
    }


def row_search_text(row: dict[str, Any]) -> str:
    values = [
        _text(row.get("kind")),
        _text(row.get("name")),
        _text(row.get("target_utc")),
        _text(row.get("host_utc")),
        _text(row.get("action_id")),
        _text(row.get("relation_type")),
        _text(row.get("relation_strength")),
    ]
    values.extend(_text(value) for value in row.get("flow_ids") or [])
    values.extend(_text(value) for value in row.get("owners") or [])
    for flow in row.get("flows") or []:
        if not isinstance(flow, dict):
            continue
        for key in (
            "protocol",
            "local_ip",
            "local_port",
            "remote_ip",
            "remote_port",
        ):
            values.append(_text(flow.get(key)))
        for key in (
            "dns_queries",
            "tls_sni",
            "quic_sni",
            "quic_alpn",
            "application_protocols",
        ):
            values.extend(_text(value) for value in flow.get(key) or [])
    return " ".join(value for value in values if value).lower()


def rows_near_target(
    model: dict[str, Any],
    target_utc: Any,
    *,
    radius_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    target = _parse_utc(target_utc)
    if target is None:
        return []
    result = []
    for row in model.get("rows") or []:
        if not isinstance(row, dict):
            continue
        value = _parse_utc(row.get("target_utc"))
        if value is None:
            continue
        delta = (value - target).total_seconds()
        if abs(delta) <= radius_seconds:
            result.append({**row, "delta_seconds": delta})
    result.sort(key=lambda row: abs(float(row.get("delta_seconds") or 0.0)))
    return result


def format_session_row_details(row: dict[str, Any]) -> str:
    lines = [
        f"Event: {_text(row.get('kind'))} / {_text(row.get('name'))}",
        f"Target UTC: {_text(row.get('target_utc')) or '—'}",
        f"Host UTC: {_text(row.get('host_utc')) or '—'}",
        f"Action: {_text(row.get('action_id')) or '—'}",
        f"Flows: {', '.join(_text(value) for value in row.get('flow_ids') or []) or '—'}",
        f"Relation: {_text(row.get('relation_type')) or '—'}",
        f"Strength: {_text(row.get('relation_strength')) or '—'}",
        f"Causal claim: {'yes' if row.get('causal_claim') else 'no'}",
    ]
    if row.get("owners"):
        lines.extend(["", "Process/socket attribution:"])
        lines.extend(f"  {value}" for value in row.get("owners") or [])
    screen = row.get("screen")
    if isinstance(screen, dict):
        continuous = screen.get("continuous")
        lines.extend(["", "Screen navigation:"])
        if isinstance(continuous, dict):
            lines.extend(
                [
                    f"  sequence: {continuous.get('sequence')}",
                    f"  derived UTC: {_text(continuous.get('derived_target_utc'))}",
                    f"  delta: {float(continuous.get('delta_seconds') or 0.0) * 1000:.3f} ms",
                    f"  mapping: {_text(continuous.get('mapping_method'))}",
                    f"  confidence: {_text(continuous.get('mapping_confidence'))}",
                ]
            )
        canonical = screen.get("canonical")
        if isinstance(canonical, dict):
            if canonical.get("covered"):
                lines.append(
                    f"  high-res: chunk {canonical.get('chunk_index')} +{float(canonical.get('relative_seconds') or 0.0):.3f}s"
                )
            else:
                lines.append("  high-res: rollover/frame coverage gap")
    lines.extend(
        [
            "",
            "Навигационные связи не повышают силу исходного доказательства и не создают причинность.",
        ]
    )
    return "\n".join(lines)
