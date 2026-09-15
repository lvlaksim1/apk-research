from __future__ import annotations

import hashlib
import json
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mobile_research.export import (
    ExportError,
    audit_complete_research_zip,
)


REQUIRED_EVENTS = (
    "session_created",
    "preflight_started",
    "device_metadata_completed",
    "raw_network_preflight_completed",
    "preflight_completed",
    "logcat_started",
    "screen_recording_started",
    "raw_network_started",
    "capture_active",
    "package_launched",
    "stop_requested",
    "raw_network_stopped",
    "screen_recording_stopped",
    "logcat_stopped",
    "capture_finished",
)


def _epoch(value: str) -> float:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).timestamp()


def stamp_for_test(seconds: float) -> str:
    base = datetime(
        2026,
        9,
        13,
        12,
        0,
        tzinfo=timezone.utc,
    )
    return (
        datetime.fromtimestamp(
            base.timestamp() + seconds,
            tz=timezone.utc,
        )
        .isoformat()
        .replace("+00:00", "Z")
    )


def _pcap(*timestamps: str) -> bytes:
    data = bytearray(
        b"\xd4\xc3\xb2\xa1"
        b"\x02\x00"
        b"\x04\x00"
        b"\x00\x00\x00\x00"
        b"\x00\x00\x00\x00"
        b"\xff\xff\x00\x00"
        b"\x01\x00\x00\x00"
    )
    for index, value in enumerate(timestamps):
        epoch = _epoch(value)
        seconds = int(epoch)
        micros = int(round((epoch - seconds) * 1_000_000))
        payload = f"pkt-{index}".encode()
        data.extend(
            struct.pack(
                "<IIII",
                seconds,
                micros,
                len(payload),
                len(payload),
            )
        )
        data.extend(payload)
    return bytes(data)


def _build_zip(
    path: Path,
    *,
    degraded: bool = False,
) -> None:
    base = datetime(
        2026,
        9,
        13,
        12,
        0,
        tzinfo=timezone.utc,
    )

    def stamp(seconds: float) -> str:
        return (
            datetime.fromtimestamp(
                base.timestamp() + seconds,
                tz=timezone.utc,
            )
            .isoformat()
            .replace("+00:00", "Z")
        )

    event_seconds = (
        0.2,
        0.5,
        1.0,
        1.2,
        1.5,
        2.0,
        2.2,
        2.4,
        2.5,
        4.0,
        8.0,
        8.2,
        8.4,
        8.5,
        8.8,
    )
    events = []
    for name, seconds in zip(REQUIRED_EVENTS, event_seconds):
        event = {
            "event": name,
            "host_utc": stamp(seconds),
            "target_utc": None,
        }
        if name in {
            "session_created",
            "capture_active",
            "package_launched",
            "stop_requested",
            "capture_finished",
        }:
            event["target_utc"] = stamp(int(seconds))
        events.append(event)

    manifest = {
        "schema_version": "0.1",
        "session_id": "audit-session",
        "mobile_research_version": "0.1.0.dev0",
        "status": "complete",
        "degraded": degraded,
        "errors": [],
        "package": {"name": "com.example.app"},
        "collectors": {
            name: {"status": "completed"}
            for name in (
                "device_metadata",
                "logcat",
                "screen_recording",
                "raw_network",
            )
        },
    }
    target = {
        "clock": {
            "host_started_utc": stamp(0.4),
            "target_started_utc": stamp(0.0),
            "host_finished_utc": stamp(1.4),
            "target_finished_utc": stamp(1.0),
        }
    }
    screen = {
        "completed_chunks": [
            {
                "status": "completed",
                "bytes": 100,
                "host_started_utc": stamp(1.9),
                "host_finished_utc": stamp(8.2),
                "capture_span_seconds": 6.3,
                "frame_timing": {
                    "source": "winscope-v2",
                    "version": 2,
                    "frame_count": 12,
                    "first_frame_utc": stamp(2.1),
                    "last_frame_utc": stamp(5.0),
                    "frame_span_seconds": 2.9,
                },
            }
        ]
    }
    logcat = (
        f"{_epoch(stamp(2.0)):.3f}  1  1 I Test: start\n"
        f"{_epoch(stamp(4.0)):.3f}  1  1 I Test: launch\n"
        f"{_epoch(stamp(8.2)):.3f}  1  1 I Test: stop\n"
    ).encode()

    files: dict[str, bytes] = {
        "00_manifest/session.json": (
            json.dumps(manifest).encode()
        ),
        "01_raw/device/package-launch.txt": (
            b"Status: ok\nActivity: com.example/.MainActivity\n"
        ),
        "01_raw/logcat/logcat.txt": logcat,
        "01_raw/network/traffic.pcap": _pcap(
            stamp(2.6),
            stamp(4.2),
            stamp(7.5),
        ),
        "02_normalized/session-events.jsonl": (
            "\n".join(json.dumps(event) for event in events)
            + "\n"
        ).encode(),
        "02_normalized/target.json": (
            json.dumps(target).encode()
        ),
        "02_normalized/screen.json": (
            json.dumps(screen).encode()
        ),
    }

    checksums = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in sorted(files.items())
    ).encode()
    files["00_manifest/checksums.sha256"] = checksums

    with zipfile.ZipFile(
        path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def test_complete_research_zip_semantic_audit(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "audit.zip"
    _build_zip(archive)

    result = audit_complete_research_zip(archive)

    assert result.session_id == "audit-session"
    assert result.package == "com.example.app"
    assert result.packet_count == 3
    assert result.logcat_entries == 3
    assert result.screen_frames == 12
    assert result.max_clock_skew_seconds <= 1.0
    assert result.screen_last_frame_gap_seconds >= 3.0
    assert result.screen_capture_span_seconds == pytest.approx(6.3)
    assert result.screen_capture_started_utc == stamp_for_test(1.9)
    assert result.screen_capture_stopped_utc == stamp_for_test(8.2)


def test_semantic_audit_rejects_degraded_complete_session(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "degraded.zip"
    _build_zip(archive, degraded=True)

    with pytest.raises(
        ExportError,
        match="unexpectedly degraded",
    ):
        audit_complete_research_zip(archive)
