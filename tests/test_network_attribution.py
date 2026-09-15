from __future__ import annotations

from mobile_research.network_attribution import (
    SocketAttributionIndex,
    parse_socket_snapshot_stream,
    summarize_snapshots,
)


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
