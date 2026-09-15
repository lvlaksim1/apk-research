from __future__ import annotations

import bisect
import json
import os
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

from mobile_research import timeline as legacy
from mobile_research.session import SessionManager

MAX_AFTER_SECONDS = 2.0
MAX_FLOW_SAMPLE = 12
MAX_LOG_SAMPLE = 12

_LEGACY_BUILD = legacy.build_research_timeline


def _alignment(root: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    calibration = legacy._read_json(
        root / "02_normalized" / "clock-calibration.json"
    )
    try:
        offset = float(calibration["target_minus_host_seconds"])
        selected = int(calibration["selected_count"])
    except (KeyError, TypeError, ValueError):
        return fallback
    if selected <= 0:
        return fallback
    uncertainty_ns = int(
        calibration.get("estimated_uncertainty_ns") or 0
    )
    return {
        "method": calibration.get("method") or "adb-ntp-midpoint",
        "target_minus_host_seconds": offset,
        "estimated_uncertainty_seconds": uncertainty_ns / 1_000_000_000,
        "sample_count": int(calibration.get("sample_count") or selected),
        "selected_count": selected,
        "samples": calibration.get("samples") or [],
    }


def _flow_summary(
    packets: list[dict[str, Any]],
    first_flow: dict[tuple[Any, ...], float],
    window_start: float,
    window_end: float,
) -> dict[str, Any]:
    counts: Counter[tuple[Any, ...]] = Counter()
    new_flows: list[dict[str, Any]] = []
    dns: list[str] = []
    sni: list[str] = []
    dns_seen: set[str] = set()
    sni_seen: set[str] = set()
    total_bytes = 0

    for packet in packets:
        total_bytes += int(packet.get("captured_length") or 0)
        key = legacy._flow_key(packet)
        if key is not None:
            counts[key] += 1
            first_epoch = first_flow.get(key)
            if (
                first_epoch is not None
                and window_start <= first_epoch <= window_end
                and not any(
                    item["flow"] == legacy._flow_value(key)
                    for item in new_flows
                )
            ):
                new_flows.append(
                    {
                        "target_utc": legacy._iso_epoch(first_epoch),
                        "flow": legacy._flow_value(key),
                    }
                )
        query = packet.get("dns_query")
        if isinstance(query, str) and query and query not in dns_seen:
            dns_seen.add(query)
            dns.append(query)
        server_name = packet.get("tls_sni")
        if (
            isinstance(server_name, str)
            and server_name
            and server_name not in sni_seen
        ):
            sni_seen.add(server_name)
            sni.append(server_name)

    flows = [
        {
            **legacy._flow_value(key),
            "packet_count": count,
        }
        for key, count in counts.most_common(MAX_FLOW_SAMPLE)
    ]
    return {
        "packet_count": len(packets),
        "captured_bytes": total_bytes,
        "flows": flows,
        "new_flows": new_flows[:MAX_FLOW_SAMPLE],
        "dns_queries": dns,
        "tls_sni": sni,
    }


def _confidence(
    network: dict[str, Any],
    log_entries: list[dict[str, Any]],
    *,
    uncertainty_seconds: float,
    truncated: bool,
    actual_after: float,
) -> tuple[str, list[str]]:
    ambiguity: list[str] = []
    package_log = [
        item for item in log_entries
        if item.get("package_related")
    ]
    if truncated:
        ambiguity.append("window_truncated_by_next_action")
    if actual_after < 0.15:
        ambiguity.append("very_short_correlation_window")
    if uncertainty_seconds > 0.1:
        ambiguity.append("clock_uncertainty_above_100ms")
    if (
        network["packet_count"] > 0
        and not network["new_flows"]
        and not network["dns_queries"]
        and not network["tls_sni"]
        and not package_log
    ):
        ambiguity.append("background_or_unattributed_activity")
    if network["packet_count"] == 0 and not log_entries:
        ambiguity.append("no_observed_signal")

    strong_network = bool(
        network["new_flows"]
        or network["dns_queries"]
        or network["tls_sni"]
    )
    if strong_network and package_log and uncertainty_seconds <= 0.1:
        return "high", ambiguity
    if strong_network or package_log or log_entries:
        return "medium", ambiguity
    return "low", ambiguity


def _correlate(
    action: dict[str, Any],
    *,
    offset_seconds: float,
    uncertainty_seconds: float,
    next_target_start,
    packets: list[dict[str, Any]],
    packet_epochs: list[float],
    logcat: list[dict[str, Any]],
    log_epochs: list[float],
    first_flow: dict[tuple[Any, ...], float],
) -> dict[str, Any]:
    host_start = legacy._parse_utc(
        str(action.get("host_started_utc") or action["host_utc"])
    )
    host_end = legacy._parse_utc(str(action["host_utc"]))
    target_start = host_start + timedelta(seconds=offset_seconds)
    target_end = host_end + timedelta(seconds=offset_seconds)

    window_start = target_start.timestamp()
    natural_end = target_end.timestamp() + MAX_AFTER_SECONDS
    window_end = natural_end
    truncated = False
    if next_target_start is not None:
        next_epoch = next_target_start.timestamp()
        if next_epoch <= natural_end:
            window_end = max(
                target_end.timestamp(),
                next_epoch - 0.001,
            )
            truncated = True

    p0 = bisect.bisect_left(packet_epochs, window_start)
    p1 = bisect.bisect_right(packet_epochs, window_end)
    selected_packets = packets[p0:p1]
    network = _flow_summary(
        selected_packets,
        first_flow,
        window_start,
        window_end,
    )

    l0 = bisect.bisect_left(log_epochs, window_start)
    l1 = bisect.bisect_right(log_epochs, window_end)
    selected_log = logcat[l0:l1]
    relevant = [item for item in selected_log if item.get("relevant")]
    sample = (relevant or selected_log)[:MAX_LOG_SAMPLE]

    actual_after = max(
        0.0,
        window_end - target_end.timestamp(),
    )
    confidence, ambiguity = _confidence(
        network,
        selected_log,
        uncertainty_seconds=uncertainty_seconds,
        truncated=truncated,
        actual_after=actual_after,
    )

    return {
        "target_started_utc_estimate": legacy._iso_utc(target_start),
        "target_finished_utc_estimate": legacy._iso_utc(target_end),
        "window": {
            "before_seconds": 0.0,
            "maximum_after_seconds": MAX_AFTER_SECONDS,
            "actual_after_seconds": actual_after,
            "truncated_by_next_action": truncated,
            "exclusive_until_next_action": True,
        },
        "causal_confidence": confidence,
        "causal_claim": False,
        "attribution": "temporal-only",
        "ambiguity": ambiguity,
        "network": network,
        "logcat": {
            "entry_count": len(selected_log),
            "relevant_entry_count": len(relevant),
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
                for item in sample
            ],
        },
    }


def build_research_timeline(session: SessionManager) -> dict[str, Any]:
    timeline = _LEGACY_BUILD(session)
    root = session.paths.root
    lifecycle = legacy._read_jsonl(
        root / "02_normalized" / "session-events.jsonl"
    )
    alignment = _alignment(root, timeline.get("clock_alignment") or {})
    offset = float(alignment.get("target_minus_host_seconds") or 0.0)
    uncertainty = float(
        alignment.get("estimated_uncertainty_seconds") or 0.0
    )

    actions = list(timeline.get("user_actions") or [])
    actions.sort(
        key=lambda item: str(
            item.get("host_started_utc")
            or item.get("host_utc")
            or ""
        )
    )

    packets, network_summary = legacy._read_pcap(
        root / "01_raw" / "network" / "traffic.pcap"
    )
    packets.sort(key=lambda item: float(item["epoch"]))
    packet_epochs = [float(item["epoch"]) for item in packets]
    network_markers, first_flow = legacy._network_markers(
        packets,
        offset,
    )

    package_name = str(timeline.get("package") or "")
    logcat = legacy._read_logcat(
        root / "01_raw" / "logcat" / "logcat.txt",
        package_name,
    )
    logcat.sort(key=lambda item: float(item["epoch"]))
    log_epochs = [float(item["epoch"]) for item in logcat]

    target_starts = []
    for action in actions:
        host_value = action.get("host_started_utc") or action.get("host_utc")
        try:
            target_starts.append(
                legacy._parse_utc(str(host_value))
                + timedelta(seconds=offset)
                if host_value
                else None
            )
        except ValueError:
            target_starts.append(None)

    for index, action in enumerate(actions):
        next_start = (
            target_starts[index + 1]
            if index + 1 < len(target_starts)
            else None
        )
        try:
            action["correlation"] = _correlate(
                action,
                offset_seconds=offset,
                uncertainty_seconds=uncertainty,
                next_target_start=next_start,
                packets=packets,
                packet_epochs=packet_epochs,
                logcat=logcat,
                log_epochs=log_epochs,
                first_flow=first_flow,
            )
        except (KeyError, TypeError, ValueError) as exc:
            action["correlation"] = {
                "error": str(exc) or exc.__class__.__name__
            }

    events: list[dict[str, Any]] = []
    for event in lifecycle:
        if not event.get("host_utc"):
            continue
        events.append(
            {
                "kind": "lifecycle",
                "host_utc": event.get("host_utc"),
                "target_utc": event.get("target_utc"),
                "name": event.get("event"),
                "details": event.get("details"),
            }
        )
    for action in actions:
        correlation = action.get("correlation")
        target_utc = (
            correlation.get("target_started_utc_estimate")
            if isinstance(correlation, dict)
            else None
        )
        events.append(
            {
                "kind": "user_action",
                "host_utc": action.get("host_started_utc") or action.get("host_utc"),
                "target_utc": target_utc,
                "name": action.get("action"),
                "action_id": action.get("action_id"),
                "details": action.get("details"),
            }
        )
    events.extend(network_markers)
    events.sort(key=lambda item: str(item.get("host_utc") or ""))

    timeline["schema_version"] = "0.2"
    timeline["clock_alignment"] = alignment
    timeline["user_actions"] = actions
    timeline["events"] = events
    timeline["correlation_window"] = {
        "before_seconds": 0.0,
        "maximum_after_seconds": MAX_AFTER_SECONDS,
        "policy": "action-end to min(+2s, next-action-start)",
        "non_overlapping": True,
    }
    summary = timeline.setdefault("summary", {})
    summary["user_actions"] = len(actions)
    summary["network_packets"] = network_summary["packet_count"]
    summary["network_markers"] = len(network_markers)
    summary["timeline_events"] = len(events)

    path = root / legacy.TIMELINE_ARTIFACT
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                timeline,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

    return timeline

