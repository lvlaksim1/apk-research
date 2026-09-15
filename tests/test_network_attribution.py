from __future__ import annotations

import json
import struct
from datetime import datetime, timezone

from mobile_research.network_attribution import (
    FLOW_INVENTORY_ARTIFACT,
    SocketAttributionIndex,
    parse_socket_snapshot_stream,
    summarize_snapshots,
    write_normalized_attribution,
)
from mobile_research.session import SessionManager
from mobile_research.timeline_engine import build_research_timeline


PACKAGE = "com.example.app"
UID = 10234
EPOCH_NS = 1_700_000_000_000_000_000


def _raw_snapshot(*, uid_packages: list[str] | None = None) -> tuple[list[dict], dict]:
    raw = "\n".join(
        [
            f"SNAP|{EPOCH_NS}",
            (
                "ROW|tcp|  0: 0F02000A:9C40 22D8B85D:01BB "
                "01 00000000:00000000 02:00000000 00000000 "
                f"{UID} 0 55555 1 0000000000000000 20 4 30 10 -1"
            ),
            f"PROC|4321|{UID}|{PACKAGE}",
            "FD|4321|55555",
            f"END|{EPOCH_NS}",
        ]
    )
    packages = uid_packages or [PACKAGE]
    snapshots = parse_socket_snapshot_stream(
        raw,
        package=PACKAGE,
        package_uid=UID,
        uid_packages=packages,
    )
    summary = summarize_snapshots(
        snapshots,
        package=PACKAGE,
        package_uid=UID,
        uid_packages=packages,
        sample_interval_seconds=0.2,
    )
    return snapshots, summary


def _packet() -> dict:
    return {
        "epoch": EPOCH_NS / 1_000_000_000 + 0.05,
        "protocol": "tcp",
        "src": "10.0.2.15",
        "src_port": 40000,
        "dst": "93.184.216.34",
        "dst_port": 443,
    }


def test_proc_snapshot_decodes_uid_inode_pid_and_tuple() -> None:
    snapshots, summary = _raw_snapshot()

    assert summary["snapshot_count"] == 1
    assert summary["socket_observations"] == 1
    assert summary["pid_socket_links"] == 1
    socket = snapshots[0]["sockets"][0]
    assert socket["local_ip"] == "10.0.2.15"
    assert socket["local_port"] == 40000
    assert socket["remote_ip"] == "93.184.216.34"
    assert socket["remote_port"] == 443
    assert socket["inode"] == 55555
    assert socket["pids"] == [4321]
    assert socket["processes"] == [PACKAGE]


def test_unique_package_uid_exact_five_tuple_is_exact() -> None:
    snapshots, summary = _raw_snapshot()
    index = SocketAttributionIndex(summary, snapshots)

    owner = index.attribute_packet(_packet())

    assert owner["package"] == PACKAGE
    assert owner["uid"] == UID
    assert owner["confidence"] == "EXACT"
    assert owner["evidence"] == (
        "unique-package-uid+socket-inode+5-tuple"
    )
    assert owner["inode"] == 55555
    assert owner["pids"] == [4321]


def test_shared_uid_downgrades_exact_tuple_to_high() -> None:
    snapshots, summary = _raw_snapshot(
        uid_packages=[PACKAGE, "com.example.shared"]
    )
    index = SocketAttributionIndex(summary, snapshots)

    owner = index.attribute_packet(_packet())

    assert owner["confidence"] == "HIGH"
    assert "uid-shared-by-multiple-packages" in owner["ambiguity"]


def test_unmatched_packet_stays_unknown() -> None:
    snapshots, summary = _raw_snapshot()
    index = SocketAttributionIndex(summary, snapshots)
    packet = _packet()
    packet["dst_port"] = 8443

    owner = index.attribute_packet(packet)

    assert owner["confidence"] == "UNKNOWN"
    assert owner["evidence"] == "no-matching-socket-observation"


def test_packet_summary_separates_attributed_and_unknown() -> None:
    snapshots, summary = _raw_snapshot()
    index = SocketAttributionIndex(summary, snapshots)
    other = _packet()
    other["dst_port"] = 8443

    result = index.summarize_packets([_packet(), other])

    assert result["packet_counts"]["EXACT"] == 1
    assert result["packet_counts"]["UNKNOWN"] == 1
    assert result["attributed_packet_count"] == 1
    assert result["total_packet_count"] == 2



def _iso(value: float) -> str:
    return (
        datetime.fromtimestamp(value, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _tcp_packet() -> bytes:
    tcp = (
        struct.pack("!HH", 40000, 443)
        + b"\x00" * 8
        + b"\x50\x18"
        + b"\x00" * 6
    )
    total_length = 20 + len(tcp)
    ip = (
        b"\x45\x00"
        + struct.pack("!H", total_length)
        + b"\x00\x01\x00\x00\x40\x06\x00\x00"
        + bytes([10, 0, 2, 15])
        + bytes([93, 184, 216, 34])
    )
    ethernet = (
        b"\x00\x11\x22\x33\x44\x55"
        b"\x66\x77\x88\x99\xaa\xbb"
        b"\x08\x00"
    )
    return ethernet + ip + tcp


def _pcap(epoch: float, packet: bytes) -> bytes:
    seconds = int(epoch)
    micros = int(round((epoch - seconds) * 1_000_000))
    return (
        b"\xd4\xc3\xb2\xa1"
        b"\x02\x00\x04\x00"
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


def test_refined_timeline_exposes_exact_package_flow_owner(
    tmp_path,
) -> None:
    snapshots, summary = _raw_snapshot()
    session = SessionManager.create(
        tmp_path,
        target={"serial": "emulator-5554"},
        package={"name": PACKAGE},
        session_id_factory=lambda: "attribution-timeline",
    )
    root = session.paths.root
    write_normalized_attribution(root, snapshots, summary)

    epoch = EPOCH_NS / 1_000_000_000
    (
        root / "02_normalized" / "session-events.jsonl"
    ).write_text(
        json.dumps(
            {
                "event": "package_launched",
                "host_utc": _iso(epoch - 0.2),
                "target_utc": _iso(epoch - 0.2),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (
        root / "02_normalized" / "user-actions.jsonl"
    ).write_text(
        json.dumps(
            {
                "action_id": "action-000001",
                "sequence": 1,
                "action": "tap",
                "host_started_utc": _iso(epoch),
                "host_utc": _iso(epoch),
                "details": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (
        root / "02_normalized" / "clock-calibration.json"
    ).write_text(
        json.dumps(
            {
                "method": "adb-ntp-midpoint",
                "sample_count": 5,
                "selected_count": 5,
                "target_minus_host_seconds": 0.0,
                "estimated_uncertainty_ns": 1_000_000,
                "samples": [],
            }
        ),
        encoding="utf-8",
    )
    network_path = root / "01_raw" / "network" / "traffic.pcap"
    network_path.parent.mkdir(parents=True, exist_ok=True)
    network_path.write_bytes(
        _pcap(epoch + 0.05, _tcp_packet())
    )

    timeline = build_research_timeline(session)

    assert timeline["schema_version"] == "0.3"
    assert timeline["network_attribution"][
        "packet_counts"
    ]["EXACT"] == 1
    flow = timeline["user_actions"][0][
        "correlation"
    ]["network"]["flows"][0]
    assert flow["owner"]["package"] == PACKAGE
    assert flow["owner"]["confidence"] == "EXACT"
    assert flow["owner"]["inode"] == 55555

    inventory = json.loads(
        (root / FLOW_INVENTORY_ARTIFACT).read_text(
            encoding="utf-8"
        )
    )
    assert inventory["summary"]["flow_count"] == 1
    assert inventory["summary"]["attributed_flow_count"] == 1
    assert inventory["flows"][0]["owner"]["confidence"] == "EXACT"
