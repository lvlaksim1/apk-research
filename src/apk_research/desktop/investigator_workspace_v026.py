from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from apk_research.desktop.unified_session_model import row_search_text

WORKSPACE_SCHEMA = "apk-research-investigator-workspace"
WORKSPACE_SCHEMA_VERSION = 1


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


def _sorted_unique(values: Iterable[Any]) -> list[str]:
    result = {_text(value) for value in values if _text(value)}
    return sorted(result, key=str.lower)


def _flow_protocols(flow: dict[str, Any]) -> list[str]:
    values: list[Any] = [flow.get("protocol")]
    for key in (
        "application_protocols",
        "quic_alpn",
    ):
        current = flow.get(key)
        if isinstance(current, (list, tuple, set)):
            values.extend(current)
        elif current:
            values.append(current)
    return _sorted_unique(values)


def _flow_endpoints(flow: dict[str, Any]) -> list[str]:
    remote_ip = _text(flow.get("remote_ip"))
    remote_port = _text(flow.get("remote_port"))
    if not remote_ip:
        return []
    return [f"{remote_ip}:{remote_port}" if remote_port else remote_ip]


def _flow_processes(flow: dict[str, Any]) -> list[str]:
    owner = flow.get("owner")
    if not isinstance(owner, dict):
        return []
    values: list[Any] = []
    processes = owner.get("processes")
    if isinstance(processes, (list, tuple, set)):
        values.extend(processes)
    elif processes:
        values.append(processes)
    pids = owner.get("pids")
    if isinstance(pids, (list, tuple, set)):
        values.extend(f"pid={_text(value)}" for value in pids if _text(value))
    elif pids:
        values.append(f"pid={_text(pids)}")
    inode = owner.get("inode")
    if inode is not None and _text(inode):
        values.append(f"inode={_text(inode)}")
    return _sorted_unique(values)


def _workspace_ref(row: dict[str, Any]) -> str:
    source = {
        "target_utc": _text(row.get("target_utc")),
        "host_utc": _text(row.get("host_utc")),
        "kind": _text(row.get("kind")),
        "name": _text(row.get("name")),
        "action_id": _text(row.get("action_id")),
        "flow_ids": sorted(_text(value) for value in row.get("flow_ids") or [] if _text(value)),
        "sequence": int(row.get("sequence") or 0),
    }
    payload = json.dumps(
        source,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16].upper()
    return f"EV-{digest}"


def _evidence_class(row: dict[str, Any]) -> str:
    relation = _text(row.get("relation_type")).lower()
    if "temporal" in relation:
        return "temporal-relationship"
    if "attribution" in relation or "socket" in relation or "process" in relation:
        return "technical-relationship"
    if relation.startswith("observed-") or relation in {"observed", "direct-observation"}:
        return "observed-fact"
    if row.get("flow_ids") and row.get("action_id"):
        return "relationship"
    return "observed-fact"


def _workspace_row(row: dict[str, Any]) -> dict[str, Any]:
    flows = [value for value in row.get("flows") or [] if isinstance(value, dict)]
    protocols = _sorted_unique(
        protocol
        for flow in flows
        for protocol in _flow_protocols(flow)
    )
    endpoints = _sorted_unique(
        endpoint
        for flow in flows
        for endpoint in _flow_endpoints(flow)
    )
    processes = _sorted_unique(
        process
        for flow in flows
        for process in _flow_processes(flow)
    )
    reference = _workspace_ref(row)
    action_id = _text(row.get("action_id"))
    values = [
        row_search_text(row),
        reference,
        _text(row.get("kind")),
        _text(row.get("name")),
        action_id,
        _text(row.get("relation_type")),
        _text(row.get("relation_strength")),
        " ".join(protocols),
        " ".join(endpoints),
        " ".join(processes),
    ]
    return {
        "ref": reference,
        "target_utc": _text(row.get("target_utc")),
        "host_utc": _text(row.get("host_utc")),
        "kind": _text(row.get("kind")),
        "name": _text(row.get("name")),
        "action_id": action_id,
        "flow_ids": [_text(value) for value in row.get("flow_ids") or [] if _text(value)],
        "protocols": protocols,
        "endpoints": endpoints,
        "processes": processes,
        "relation_type": _text(row.get("relation_type")),
        "relation_strength": _text(row.get("relation_strength")),
        "causal_claim": bool(row.get("causal_claim", False)),
        "evidence_class": _evidence_class(row),
        "screen_available": isinstance(row.get("screen"), dict),
        "packet_count": int(row.get("packet_count") or 0),
        "search_text": " ".join(value for value in values if value).lower(),
        "source_row": row,
    }


def build_workspace_model(unified_model: dict[str, Any]) -> dict[str, Any]:
    rows = [
        _workspace_row(row)
        for row in unified_model.get("rows") or []
        if isinstance(row, dict)
    ]
    rows_by_ref = {row["ref"]: row for row in rows}
    protocols = _sorted_unique(
        value for row in rows for value in row.get("protocols") or []
    )
    processes = _sorted_unique(
        value for row in rows for value in row.get("processes") or []
    )
    endpoints = _sorted_unique(
        value for row in rows for value in row.get("endpoints") or []
    )
    kinds = _sorted_unique(row.get("kind") for row in rows)
    evidence_classes = _sorted_unique(row.get("evidence_class") for row in rows)
    first_time = next(
        (_parse_utc(row.get("target_utc") or row.get("host_utc")) for row in rows if _parse_utc(row.get("target_utc") or row.get("host_utc")) is not None),
        None,
    )
    times = [
        value
        for row in rows
        if (value := _parse_utc(row.get("target_utc") or row.get("host_utc"))) is not None
    ]
    last_time = max(times) if times else first_time
    first_time = min(times) if times else first_time
    return {
        "package": _text(unified_model.get("package")),
        "rows": rows,
        "rows_by_ref": rows_by_ref,
        "row_count": len(rows),
        "action_count": int(unified_model.get("action_count") or 0),
        "flow_count": int(unified_model.get("flow_count") or 0),
        "protocols": protocols,
        "processes": processes,
        "endpoints": endpoints,
        "kinds": kinds,
        "evidence_classes": evidence_classes,
        "first_utc": first_time.isoformat().replace("+00:00", "Z") if first_time else "",
        "last_utc": last_time.isoformat().replace("+00:00", "Z") if last_time else "",
        "evidence_policy": {
            "raw_is_authoritative": True,
            "action_network": "temporal-only unless source says otherwise",
            "screen": "time-aligned-navigation",
            "protocol": "captured-packets-only",
            "causal_upgrade": False,
        },
    }


def filter_workspace_rows(
    model: dict[str, Any],
    *,
    query: str = "",
    kind: str = "",
    protocol: str = "",
    process: str = "",
    endpoint: str = "",
    action: str = "",
    evidence_class: str = "",
    start_utc: str = "",
    end_utc: str = "",
) -> list[dict[str, Any]]:
    query_tokens = [value for value in query.strip().lower().split() if value]
    kind_l = kind.strip().lower()
    protocol_l = protocol.strip().lower()
    process_l = process.strip().lower()
    endpoint_l = endpoint.strip().lower()
    action_l = action.strip().lower()
    class_l = evidence_class.strip().lower()
    start = _parse_utc(start_utc)
    end = _parse_utc(end_utc)

    result: list[dict[str, Any]] = []
    for row in model.get("rows") or []:
        if not isinstance(row, dict):
            continue
        search = _text(row.get("search_text")).lower()
        if query_tokens and not all(token in search for token in query_tokens):
            continue
        if kind_l and _text(row.get("kind")).lower() != kind_l:
            continue
        if protocol_l and protocol_l not in {_text(value).lower() for value in row.get("protocols") or []}:
            continue
        if process_l and not any(process_l in _text(value).lower() for value in row.get("processes") or []):
            continue
        if endpoint_l and not any(endpoint_l in _text(value).lower() for value in row.get("endpoints") or []):
            continue
        if action_l and action_l not in _text(row.get("action_id")).lower():
            continue
        if class_l and _text(row.get("evidence_class")).lower() != class_l:
            continue
        row_time = _parse_utc(row.get("target_utc") or row.get("host_utc"))
        if start is not None and (row_time is None or row_time < start):
            continue
        if end is not None and (row_time is None or row_time > end):
            continue
        result.append(row)
    return result


def workspace_state_path(archive: str | Path) -> Path:
    path = Path(archive)
    return path.with_name(path.name + ".investigator.json")


def empty_workspace_state(archive: str | Path = "") -> dict[str, Any]:
    return {
        "schema": WORKSPACE_SCHEMA,
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "archive": str(archive or ""),
        "bookmarks": [],
        "evidence_sets": [
            {
                "id": "set-001",
                "name": "Основной набор",
                "refs": [],
            }
        ],
        "active_set_id": "set-001",
    }


def normalize_workspace_state(
    value: Any,
    *,
    archive: str | Path = "",
    valid_refs: Iterable[str] | None = None,
) -> dict[str, Any]:
    state = empty_workspace_state(archive)
    if isinstance(value, dict):
        state.update(
            {
                "archive": _text(value.get("archive")) or str(archive or ""),
                "active_set_id": _text(value.get("active_set_id")) or "set-001",
            }
        )
        bookmarks = value.get("bookmarks")
        if isinstance(bookmarks, list):
            state["bookmarks"] = _sorted_unique(bookmarks)
        sets = value.get("evidence_sets")
        if isinstance(sets, list):
            cleaned_sets = []
            seen_ids: set[str] = set()
            for index, item in enumerate(sets, start=1):
                if not isinstance(item, dict):
                    continue
                set_id = _text(item.get("id")) or f"set-{index:03d}"
                if set_id in seen_ids:
                    continue
                seen_ids.add(set_id)
                cleaned_sets.append(
                    {
                        "id": set_id,
                        "name": _text(item.get("name")) or f"Набор {index}",
                        "refs": _sorted_unique(item.get("refs") or []),
                    }
                )
            if cleaned_sets:
                state["evidence_sets"] = cleaned_sets
    valid = set(valid_refs) if valid_refs is not None else None
    if valid is not None:
        state["bookmarks"] = [ref for ref in state["bookmarks"] if ref in valid]
        for item in state["evidence_sets"]:
            item["refs"] = [ref for ref in item.get("refs") or [] if ref in valid]
    set_ids = {_text(item.get("id")) for item in state["evidence_sets"]}
    if state["active_set_id"] not in set_ids:
        state["active_set_id"] = _text(state["evidence_sets"][0].get("id"))
    return state


def load_workspace_state(
    path: str | Path,
    *,
    archive: str | Path = "",
    valid_refs: Iterable[str] | None = None,
) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        value = {}
    return normalize_workspace_state(value, archive=archive, valid_refs=valid_refs)


def save_workspace_state(path: str | Path, state: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_workspace_state(state, archive=state.get("archive") or "")
    payload = json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(target)


def toggle_bookmark(state: dict[str, Any], reference: str) -> bool:
    ref = _text(reference)
    bookmarks = _sorted_unique(state.get("bookmarks") or [])
    if ref in bookmarks:
        bookmarks.remove(ref)
        enabled = False
    else:
        bookmarks.append(ref)
        bookmarks = _sorted_unique(bookmarks)
        enabled = True
    state["bookmarks"] = bookmarks
    return enabled


def add_evidence_set(state: dict[str, Any], name: str) -> str:
    label = _text(name) or "Новый набор"
    sets = [item for item in state.get("evidence_sets") or [] if isinstance(item, dict)]
    used = {_text(item.get("id")) for item in sets}
    number = 1
    while f"set-{number:03d}" in used:
        number += 1
    set_id = f"set-{number:03d}"
    sets.append({"id": set_id, "name": label, "refs": []})
    state["evidence_sets"] = sets
    state["active_set_id"] = set_id
    return set_id


def remove_evidence_set(state: dict[str, Any], set_id: str) -> bool:
    target = _text(set_id)
    sets = [item for item in state.get("evidence_sets") or [] if isinstance(item, dict)]
    if len(sets) <= 1:
        return False
    kept = [item for item in sets if _text(item.get("id")) != target]
    if len(kept) == len(sets):
        return False
    state["evidence_sets"] = kept
    if _text(state.get("active_set_id")) == target:
        state["active_set_id"] = _text(kept[0].get("id"))
    return True


def set_evidence_membership(
    state: dict[str, Any],
    set_id: str,
    references: Iterable[str],
    *,
    include: bool = True,
) -> None:
    target = _text(set_id)
    refs = _sorted_unique(references)
    for item in state.get("evidence_sets") or []:
        if not isinstance(item, dict) or _text(item.get("id")) != target:
            continue
        current = set(_sorted_unique(item.get("refs") or []))
        if include:
            current.update(refs)
        else:
            current.difference_update(refs)
        item["refs"] = sorted(current, key=str.lower)
        return


def active_evidence_refs(state: dict[str, Any]) -> list[str]:
    target = _text(state.get("active_set_id"))
    for item in state.get("evidence_sets") or []:
        if isinstance(item, dict) and _text(item.get("id")) == target:
            return _sorted_unique(item.get("refs") or [])
    return []


def build_report_data(
    model: dict[str, Any],
    references: Iterable[str],
    *,
    archive: str | Path = "",
    title: str = "Investigator Evidence Report",
) -> dict[str, Any]:
    rows_by_ref = model.get("rows_by_ref") if isinstance(model.get("rows_by_ref"), dict) else {}
    items = []
    for ref in _sorted_unique(references):
        row = rows_by_ref.get(ref)
        if not isinstance(row, dict):
            continue
        items.append(
            {
                "ref": ref,
                "time_utc": _text(row.get("target_utc") or row.get("host_utc")),
                "evidence_class": _text(row.get("evidence_class")),
                "kind": _text(row.get("kind")),
                "name": _text(row.get("name")),
                "action_id": _text(row.get("action_id")),
                "flow_ids": list(row.get("flow_ids") or []),
                "protocols": list(row.get("protocols") or []),
                "endpoints": list(row.get("endpoints") or []),
                "processes": list(row.get("processes") or []),
                "relation_type": _text(row.get("relation_type")),
                "relation_strength": _text(row.get("relation_strength")),
                "causal_claim": bool(row.get("causal_claim", False)),
                "source_navigation": {
                    "workspace_ref": ref,
                    "action_id": _text(row.get("action_id")),
                    "flow_ids": list(row.get("flow_ids") or []),
                    "target_utc": _text(row.get("target_utc")),
                },
            }
        )
    return {
        "schema": "apk-research-investigator-report",
        "schema_version": 1,
        "title": _text(title) or "Investigator Evidence Report",
        "package": _text(model.get("package")),
        "archive": str(archive or ""),
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "item_count": len(items),
        "items": items,
        "evidence_policy": deepcopy(model.get("evidence_policy") or {}),
    }


def report_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {_text(report.get('title')) or 'Investigator Evidence Report'}",
        "",
        f"- Package: `{_text(report.get('package')) or '—'}`",
        f"- Research ZIP: `{_text(report.get('archive')) or '—'}`",
        f"- Generated UTC: `{_text(report.get('generated_utc')) or '—'}`",
        f"- Evidence items: {int(report.get('item_count') or 0)}",
        "",
        "> RAW evidence remains authoritative. Temporal and navigation links do not establish causality. Absence from this report means only that an item was not selected.",
        "",
    ]
    for index, item in enumerate(report.get("items") or [], start=1):
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"## {index}. {_text(item.get('ref'))} — {_text(item.get('name')) or _text(item.get('kind')) or 'Evidence'}",
                "",
                f"- Time UTC: `{_text(item.get('time_utc')) or '—'}`",
                f"- Class: `{_text(item.get('evidence_class')) or '—'}`",
                f"- Kind: `{_text(item.get('kind')) or '—'}`",
                f"- Action: `{_text(item.get('action_id')) or '—'}`",
                f"- Flows: `{', '.join(_text(value) for value in item.get('flow_ids') or []) or '—'}`",
                f"- Protocols: `{', '.join(_text(value) for value in item.get('protocols') or []) or '—'}`",
                f"- Endpoints: `{', '.join(_text(value) for value in item.get('endpoints') or []) or '—'}`",
                f"- Processes: `{', '.join(_text(value) for value in item.get('processes') or []) or '—'}`",
                f"- Relation: `{_text(item.get('relation_type')) or '—'}` / `{_text(item.get('relation_strength')) or '—'}`",
                f"- Causal claim: `{'yes' if item.get('causal_claim') else 'no'}`",
                f"- Return reference: `{_text(item.get('ref'))}` (paste/search this ref in Investigator Workspace)",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def format_workspace_row_details(row: dict[str, Any]) -> str:
    lines = [
        f"Reference: {_text(row.get('ref'))}",
        f"Class: {_text(row.get('evidence_class')) or '—'}",
        f"Event: {_text(row.get('kind')) or '—'} / {_text(row.get('name')) or '—'}",
        f"Time UTC: {_text(row.get('target_utc') or row.get('host_utc')) or '—'}",
        f"Action: {_text(row.get('action_id')) or '—'}",
        f"Flows: {', '.join(_text(value) for value in row.get('flow_ids') or []) or '—'}",
        f"Protocols: {', '.join(_text(value) for value in row.get('protocols') or []) or '—'}",
        f"Endpoints: {', '.join(_text(value) for value in row.get('endpoints') or []) or '—'}",
        f"Processes: {', '.join(_text(value) for value in row.get('processes') or []) or '—'}",
        f"Packets: {int(row.get('packet_count') or 0)}",
        f"Relation: {_text(row.get('relation_type')) or '—'} / {_text(row.get('relation_strength')) or '—'}",
        f"Causal claim: {'yes' if row.get('causal_claim') else 'no'}",
        f"Screen navigation: {'available' if row.get('screen_available') else 'not available'}",
        "",
        "Reference is a navigation key over existing evidence; it does not create a new fact or strengthen the source relationship.",
    ]
    return "\n".join(lines)
