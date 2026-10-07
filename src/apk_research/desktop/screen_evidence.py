from __future__ import annotations

from bisect import bisect_left
from datetime import datetime, timezone
from statistics import median
from typing import Any

CONTINUOUS_VIDEO_ARTIFACT = "01_raw/screen/continuous-screen.h264"
CONTINUOUS_INDEX_ARTIFACT = "02_normalized/continuous-screen-packets.jsonl"
CONTINUOUS_METADATA_ARTIFACT = "02_normalized/continuous-screen.json"
CANONICAL_SCREEN_ARTIFACT = "02_normalized/screen.json"


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


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _unix_ns(value: datetime) -> int:
    return int(round(value.timestamp() * 1_000_000_000))


def _offset_candidates(screen: dict[str, Any]) -> list[int]:
    values: list[int] = []
    for chunk in screen.get("completed_chunks") or []:
        if not isinstance(chunk, dict):
            continue
        timing = chunk.get("frame_timing")
        if not isinstance(timing, dict):
            continue
        value = timing.get("realtime_to_elapsed_offset_ns")
        try:
            values.append(int(value))
        except (TypeError, ValueError):
            continue
    return values


def _canonical_chunks(screen: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for chunk in screen.get("completed_chunks") or []:
        if not isinstance(chunk, dict):
            continue
        timing = chunk.get("frame_timing")
        if not isinstance(timing, dict):
            timing = {}
        first_utc = _parse_utc(timing.get("first_frame_utc"))
        last_utc = _parse_utc(timing.get("last_frame_utc"))
        if first_utc is None or last_utc is None:
            continue
        result.append(
            {
                "index": int(chunk.get("index") or 0),
                "artifact": _text(chunk.get("local_video")),
                "first_frame_utc": _iso_utc(first_utc),
                "last_frame_utc": _iso_utc(last_utc),
                "first_dt": first_utc,
                "last_dt": last_utc,
                "frame_count": int(timing.get("frame_count") or 0),
                "clock_domain": _text(timing.get("clock_domain")),
                "source": _text(timing.get("source")),
            }
        )
    result.sort(key=lambda item: item["first_dt"])
    return result


def build_screen_evidence_index(
    continuous: dict[str, Any] | None,
    canonical: dict[str, Any] | None,
    packets: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Build a navigation-only screen timing index.

    Media PTS is never treated as UTC by itself. When available, conversion
    uses the device realtime↔elapsed offset already exported by canonical
    screenrecord Winscope timing. A fallback anchor is explicitly marked as an
    estimate. No screen/network or screen/action causality is asserted.
    """

    continuous = continuous if isinstance(continuous, dict) else {}
    canonical = canonical if isinstance(canonical, dict) else {}
    packet_rows = [
        row
        for row in (packets or [])
        if isinstance(row, dict)
        and int(row.get("size") or 0) > 0
        and not bool(row.get("codec_config"))
        and not bool(row.get("end_of_stream"))
    ]
    packet_rows.sort(key=lambda row: int(row.get("pts_us") or 0))

    offsets = _offset_candidates(canonical)
    offset_ns: int | None = None
    mapping_method = "unavailable"
    confidence = "UNAVAILABLE"
    uncertainty_seconds: float | None = None

    if offsets:
        offset_ns = int(median(offsets))
        spread_ns = max(offsets) - min(offsets)
        mapping_method = "screenrecord-realtime-to-elapsed-offset"
        confidence = "HIGH"
        uncertainty_seconds = max(spread_ns / 1_000_000_000, 0.001)
    else:
        target_started = _parse_utc(continuous.get("target_started_utc"))
        first_pts = continuous.get("first_pts_us")
        if target_started is not None and first_pts is not None:
            try:
                offset_ns = _unix_ns(target_started) - int(first_pts) * 1000
            except (TypeError, ValueError):
                offset_ns = None
            if offset_ns is not None:
                mapping_method = "target-start-boundary-anchor"
                confidence = "ESTIMATED"
                uncertainty_seconds = 1.0

    frames: list[dict[str, Any]] = []
    if offset_ns is not None:
        for row in packet_rows:
            pts_us = int(row.get("pts_us") or 0)
            target_ns = pts_us * 1000 + offset_ns
            target_dt = datetime.fromtimestamp(
                target_ns / 1_000_000_000,
                tz=timezone.utc,
            )
            frames.append(
                {
                    "sequence": int(row.get("sequence") or 0),
                    "pts_us": pts_us,
                    "raw_offset": int(row.get("raw_offset") or 0),
                    "size": int(row.get("size") or 0),
                    "key_frame": bool(row.get("key_frame")),
                    "target_utc": _iso_utc(target_dt),
                    "target_dt": target_dt,
                }
            )

    return {
        "available": bool(frames),
        "status": _text(continuous.get("status")),
        "role": _text(continuous.get("evidence_role")) or "continuous-timeline",
        "raw_video": _text(continuous.get("raw_video")) or CONTINUOUS_VIDEO_ARTIFACT,
        "packet_index": _text(continuous.get("packet_index")) or CONTINUOUS_INDEX_ARTIFACT,
        "mapping_method": mapping_method,
        "confidence": confidence,
        "uncertainty_seconds": uncertainty_seconds,
        "offset_ns": offset_ns,
        "frames": frames,
        "frame_target_times": [frame["target_dt"] for frame in frames],
        "canonical_chunks": _canonical_chunks(canonical),
        "canonical_artifact": CANONICAL_SCREEN_ARTIFACT,
        "continuous_metadata_artifact": CONTINUOUS_METADATA_ARTIFACT,
        "causal_claim": False,
    }


def _canonical_locator(
    chunks: list[dict[str, Any]],
    target: datetime,
) -> dict[str, Any]:
    for chunk in chunks:
        if chunk["first_dt"] <= target <= chunk["last_dt"]:
            return {
                "covered": True,
                "chunk_index": chunk["index"],
                "artifact": chunk["artifact"],
                "first_frame_utc": chunk["first_frame_utc"],
                "last_frame_utc": chunk["last_frame_utc"],
                "relative_seconds": (
                    target - chunk["first_dt"]
                ).total_seconds(),
                "frame_count": chunk["frame_count"],
                "clock_domain": chunk["clock_domain"],
                "source": chunk["source"],
            }
    if not chunks:
        return {"covered": False}

    nearest = min(
        chunks,
        key=lambda chunk: min(
            abs((target - chunk["first_dt"]).total_seconds()),
            abs((target - chunk["last_dt"]).total_seconds()),
        ),
    )
    distance = min(
        abs((target - nearest["first_dt"]).total_seconds()),
        abs((target - nearest["last_dt"]).total_seconds()),
    )
    return {
        "covered": False,
        "nearest_chunk_index": nearest["index"],
        "nearest_artifact": nearest["artifact"],
        "distance_seconds": distance,
    }


def locate_screen_moment(
    index: dict[str, Any],
    target_utc: Any,
) -> dict[str, Any] | None:
    target = _parse_utc(target_utc)
    if target is None:
        return None

    chunks = index.get("canonical_chunks")
    canonical = _canonical_locator(
        chunks if isinstance(chunks, list) else [],
        target,
    )

    frames = index.get("frames")
    times = index.get("frame_target_times")
    if not isinstance(frames, list) or not frames:
        return {
            "kind": "screen",
            "target_utc": _iso_utc(target),
            "continuous_available": False,
            "canonical": canonical,
            "relation_type": "time-aligned-navigation",
            "relation_strength": "unavailable",
            "causal_claim": False,
        }
    if not isinstance(times, list) or len(times) != len(frames):
        return None

    position = bisect_left(times, target)
    candidates = []
    if position < len(frames):
        candidates.append(frames[position])
    if position > 0:
        candidates.append(frames[position - 1])
    frame = min(
        candidates,
        key=lambda item: abs(
            (item["target_dt"] - target).total_seconds()
        ),
    )
    delta_seconds = (frame["target_dt"] - target).total_seconds()

    return {
        "kind": "screen",
        "target_utc": _iso_utc(target),
        "continuous_available": True,
        "continuous": {
            "artifact": index.get("raw_video") or CONTINUOUS_VIDEO_ARTIFACT,
            "packet_index": index.get("packet_index") or CONTINUOUS_INDEX_ARTIFACT,
            "sequence": frame["sequence"],
            "pts_us": frame["pts_us"],
            "raw_offset": frame["raw_offset"],
            "size": frame["size"],
            "key_frame": frame["key_frame"],
            "derived_target_utc": frame["target_utc"],
            "delta_seconds": delta_seconds,
            "mapping_method": index.get("mapping_method"),
            "mapping_confidence": index.get("confidence"),
            "mapping_uncertainty_seconds": index.get("uncertainty_seconds"),
        },
        "canonical": canonical,
        "relation_type": "time-aligned-navigation",
        "relation_strength": str(index.get("confidence") or "UNKNOWN"),
        "causal_claim": False,
    }


def format_screen_locator(locator: dict[str, Any] | None) -> str:
    if not isinstance(locator, dict):
        return "Screen evidence: недоступно"
    lines = [
        f"Screen target UTC: {_text(locator.get('target_utc')) or '—'}",
        "Relation: time-aligned-navigation",
        "Causal claim: no",
    ]
    continuous = locator.get("continuous")
    if isinstance(continuous, dict):
        lines.extend(
            [
                "",
                "Continuous Screen:",
                f"  artifact: {_text(continuous.get('artifact'))}",
                f"  frame sequence: {continuous.get('sequence')}",
                f"  PTS: {continuous.get('pts_us')} us",
                f"  raw offset: {continuous.get('raw_offset')}",
                f"  derived UTC: {_text(continuous.get('derived_target_utc'))}",
                f"  delta: {float(continuous.get('delta_seconds') or 0.0) * 1000:.3f} ms",
                f"  clock mapping: {_text(continuous.get('mapping_method'))}",
                f"  confidence: {_text(continuous.get('mapping_confidence'))}",
            ]
        )
    else:
        lines.extend(["", "Continuous Screen: недоступно"])

    canonical = locator.get("canonical")
    if isinstance(canonical, dict):
        if canonical.get("covered"):
            lines.extend(
                [
                    "",
                    "High-resolution screenrecord:",
                    f"  chunk: {canonical.get('chunk_index')}",
                    f"  artifact: {_text(canonical.get('artifact'))}",
                    f"  relative: {float(canonical.get('relative_seconds') or 0.0):.3f} s",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "High-resolution screenrecord: frame coverage gap",
                    f"  nearest chunk: {canonical.get('nearest_chunk_index') or '—'}",
                    f"  distance: {float(canonical.get('distance_seconds') or 0.0):.3f} s",
                ]
            )
    return "\n".join(lines)
