from __future__ import annotations

import json
import struct
from datetime import datetime, timezone
from pathlib import Path

from apk_research.session import SessionManager
from apk_research.timeline import (
    TIMELINE_ARTIFACT,
    USER_ACTIONS_ARTIFACT,
    build_research_timeline,
)


def _stamp(seconds: float) -> str:
    base = datetime(
        2026,
        9,
        15,
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


def _dns_query(name: str) -> bytes:
    labels = b"".join(
        bytes([len(label)])
        + label.encode("ascii")
        for label in name.split(".")
    )
    return (
        b"\x12\x34"
        b"\x01\x00"
        b"\x00\x01"
        b"\x00\x00"
        b"\x00\x00"
        b"\x00\x00"
        + labels
        + b"\x00"
        + b"\x00\x01"
        + b"\x00\x01"
    )


def _ethernet_dns_packet(name: str) -> bytes:
    dns = _dns_query(name)
    udp_length = 8 + len(dns)
    udp = (
        struct.pack(
            "!HHHH",
            42000,
            53,
            udp_length,
            0,
        )
        + dns
    )
    total_length = 20 + len(udp)
    ip = (
        b"\x45\x00"
        + struct.pack("!H", total_length)
        + b"\x00\x01"
        + b"\x00\x00"
        + b"\x40"
        + b"\x11"
        + b"\x00\x00"
        + bytes([10, 0, 2, 15])
        + bytes([10, 0, 2, 3])
    )
    ethernet = (
        b"\x00\x11\x22\x33\x44\x55"
        b"\x66\x77\x88\x99\xaa\xbb"
        b"\x08\x00"
    )
    return ethernet + ip + udp


def _pcap(
    timestamp: float,
    packet: bytes,
) -> bytes:
    seconds = int(timestamp)
    micros = int(
        round(
            (timestamp - seconds)
            * 1_000_000
        )
    )
    return (
        b"\xd4\xc3\xb2\xa1"
        b"\x02\x00"
        b"\x04\x00"
        b"\x00\x00\x00\x00"
        b"\x00\x00\x00\x00"
        b"\xff\xff\x00\x00"
        b"\x01\x00\x00\x00"
        + struct.pack(
            "<IIII",
            seconds,
            micros,
            len(packet),
            len(packet),
        )
        + packet
    )


def test_timeline_correlates_user_action_with_dns_and_logcat(
    tmp_path: Path,
) -> None:
    session = SessionManager.create(
        tmp_path,
        target={
            "serial": "emulator-5554",
        },
        package={
            "name": "com.example.app",
        },
        session_id_factory=lambda: "timeline-session",
    )
    root = session.paths.root

    events = [
        {
            "event": "capture_active",
            "host_utc": _stamp(1.0),
            "target_utc": _stamp(2.0),
        },
        {
            "event": "package_launched",
            "host_utc": _stamp(1.5),
            "target_utc": _stamp(2.5),
        },
    ]
    (
        root
        / "02_normalized"
        / "session-events.jsonl"
    ).write_text(
        "\n".join(
            json.dumps(value)
            for value in events
        )
        + "\n",
        encoding="utf-8",
    )
    (
        root
        / USER_ACTIONS_ARTIFACT
    ).write_text(
        json.dumps(
            {
                "action_id": "action-000001",
                "sequence": 1,
                "action": "tap",
                "host_started_utc": _stamp(2.0),
                "host_utc": _stamp(2.0),
                "details": {
                    "start_x": 100,
                    "start_y": 200,
                    "end_x": 100,
                    "end_y": 200,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (
        root
        / "02_normalized"
        / "target.json"
    ).write_text(
        json.dumps(
            {
                "clock": {
                    "host_started_utc": _stamp(0.0),
                    "target_started_utc": _stamp(1.0),
                    "host_finished_utc": _stamp(0.5),
                    "target_finished_utc": _stamp(1.5),
                }
            }
        ),
        encoding="utf-8",
    )
    log_epoch = (
        datetime.fromisoformat(
            _stamp(3.4).replace(
                "Z",
                "+00:00",
            )
        ).timestamp()
    )
    (
        root
        / "01_raw"
        / "logcat"
        / "logcat.txt"
    ).write_text(
        (
            f"{log_epoch:.3f}  123  123 I "
            "ActivityManager: com.example.app resumed\n"
        ),
        encoding="utf-8",
    )
    packet_epoch = (
        datetime.fromisoformat(
            _stamp(3.5).replace(
                "Z",
                "+00:00",
            )
        ).timestamp()
    )
    (
        root
        / "01_raw"
        / "network"
        / "traffic.pcap"
    ).write_bytes(
        _pcap(
            packet_epoch,
            _ethernet_dns_packet(
                "example.com"
            ),
        )
    )

    timeline = build_research_timeline(
        session
    )

    assert timeline["summary"]["user_actions"] == 1
    assert timeline["summary"]["network_packets"] == 1
    action = timeline["user_actions"][0]
    correlation = action["correlation"]
    assert correlation["network"]["packet_count"] == 1
    assert correlation["network"]["dns_queries"] == [
        "example.com"
    ]
    assert correlation["logcat"]["entry_count"] == 1
    assert (
        correlation["logcat"]["sample"][0][
            "package_related"
        ]
        is True
    )
    assert (
        root / TIMELINE_ARTIFACT
    ).is_file()


def test_timeline_coalesces_adjacent_text_input(
    tmp_path: Path,
) -> None:
    session = SessionManager.create(
        tmp_path,
        target={},
        package={
            "name": "com.example.app",
        },
        session_id_factory=lambda: "text-session",
    )
    root = session.paths.root
    (
        root
        / USER_ACTIONS_ARTIFACT
    ).write_text(
        "\n".join(
            json.dumps(
                {
                    "action_id": f"action-{index:06d}",
                    "sequence": index,
                    "action": "text_input",
                    "host_started_utc": _stamp(
                        2.0 + index * 0.2
                    ),
                    "host_utc": _stamp(
                        2.0 + index * 0.2
                    ),
                    "details": {
                        "text": value,
                        "length": 1,
                    },
                }
            )
            for index, value in (
                (1, "a"),
                (2, "b"),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    timeline = build_research_timeline(
        session
    )

    assert timeline["summary"]["user_actions"] == 1
    assert (
        timeline["user_actions"][0]["details"]["text"]
        == "ab"
    )
    assert (
        timeline["user_actions"][0]["details"]["length"]
        == 2
    )
