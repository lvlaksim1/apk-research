from __future__ import annotations

import ipaddress
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SNAPSHOTS_ARTIFACT = "02_normalized/socket-attribution.jsonl"
SUMMARY_ARTIFACT = "02_normalized/socket-attribution.json"
FLOW_INVENTORY_ARTIFACT = "02_normalized/network-flows.json"

_CONFIDENCE_ORDER = {
    "UNKNOWN": 0,
    "MEDIUM": 1,
    "HIGH": 2,
    "EXACT": 3,
}


def _iso_epoch(value: float) -> str:
    return (
        datetime.fromtimestamp(value, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _normalize_ip(value: str) -> str:
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address):
        mapped = address.ipv4_mapped
        if mapped is not None:
            return str(mapped)
    return str(address)


def _decode_proc_ip(value: str, family: str) -> str:
    raw = bytes.fromhex(value)
    if family == "ipv4":
        if len(raw) != 4:
            raise ValueError("invalid IPv4 /proc address")
        return str(ipaddress.IPv4Address(raw[::-1]))
    if len(raw) != 16:
        raise ValueError("invalid IPv6 /proc address")
    ordered = b"".join(
        raw[index : index + 4][::-1]
        for index in range(0, 16, 4)
    )
    return _normalize_ip(str(ipaddress.IPv6Address(ordered)))


def _decode_endpoint(value: str, family: str) -> tuple[str, int]:
    address_hex, port_hex = value.split(":", 1)
    return _decode_proc_ip(address_hex, family), int(port_hex, 16)


def parse_proc_socket_row(
    table: str,
    line: str,
    *,
    package_uid: int,
) -> dict[str, Any] | None:
    parts = line.split()
    if len(parts) < 10 or parts[0].lower().startswith("sl"):
        return None
    family = "ipv6" if table.endswith("6") else "ipv4"
    protocol = "udp" if table.startswith("udp") else "tcp"
    try:
        uid = int(parts[7])
        if uid != package_uid:
            return None
        local_ip, local_port = _decode_endpoint(parts[1], family)
        remote_ip, remote_port = _decode_endpoint(parts[2], family)
        inode = int(parts[9])
    except (ValueError, IndexError):
        return None
    return {
        "protocol": protocol,
        "family": family,
        "local_ip": local_ip,
        "local_port": local_port,
        "remote_ip": remote_ip,
        "remote_port": remote_port,
        "state": parts[3],
        "uid": uid,
        "inode": inode,
    }


def parse_socket_snapshot_stream(
    text: str,
    *,
    package: str,
    package_uid: int,
    uid_packages: list[str],
) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if not line:
            continue
        kind, separator, payload = line.partition("|")
        if not separator:
            continue

        if kind == "SNAP":
            fields = payload.split("|")
            if not fields:
                continue
            try:
                target_ns = int(fields[0])
            except ValueError:
                continue
            current = {
                "target_epoch_ns": target_ns,
                "target_utc": _iso_epoch(target_ns / 1_000_000_000),
                "package": package,
                "package_uid": package_uid,
                "uid_packages": list(uid_packages),
                "_rows": [],
                "_processes": {},
                "_fds": {},
            }
            continue

        if current is None:
            continue

        if kind == "ROW":
            table, sep, row = payload.partition("|")
            if not sep:
                continue
            socket = parse_proc_socket_row(
                table,
                row,
                package_uid=package_uid,
            )
            if socket is not None:
                current["_rows"].append(socket)
            continue

        if kind == "PROC":
            fields = payload.split("|", 2)
            if len(fields) < 2:
                continue
            try:
                pid = int(fields[0])
                uid = int(fields[1])
            except ValueError:
                continue
            if uid != package_uid:
                continue
            name = fields[2].strip() if len(fields) > 2 else ""
            current["_processes"][pid] = {
                "pid": pid,
                "uid": uid,
                "name": name,
            }
            continue

        if kind == "FD":
            fields = payload.split("|", 1)
            if len(fields) != 2:
                continue
            try:
                pid = int(fields[0])
                inode = int(fields[1])
            except ValueError:
                continue
            current["_fds"].setdefault(inode, set()).add(pid)
            continue

        if kind == "END":
            rows = current.pop("_rows")
            processes = current.pop("_processes")
            fds = current.pop("_fds")
            normalized_sockets: list[dict[str, Any]] = []
            for socket in rows:
                pids = sorted(fds.get(int(socket["inode"]), set()))
                socket["pids"] = pids
                socket["processes"] = [
                    processes[pid]["name"]
                    for pid in pids
                    if pid in processes and processes[pid]["name"]
                ]
                normalized_sockets.append(socket)
            current["processes"] = [
                processes[pid]
                for pid in sorted(processes)
            ]
            current["sockets"] = normalized_sockets
            snapshots.append(current)
            current = None

    return snapshots


def load_socket_attribution(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary: dict[str, Any] = {}
    try:
        value = json.loads(
            (root / SUMMARY_ARTIFACT).read_text(encoding="utf-8")
        )
        if isinstance(value, dict):
            summary = value
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError):
        pass

    snapshots: list[dict[str, Any]] = []
    try:
        text = (root / SNAPSHOTS_ARTIFACT).read_text(
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return summary, snapshots
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            snapshots.append(value)
    return summary, snapshots


def summarize_snapshots(
    snapshots: list[dict[str, Any]],
    *,
    package: str,
    package_uid: int,
    uid_packages: list[str],
    sample_interval_seconds: float,
) -> dict[str, Any]:
    socket_count = sum(
        len(snapshot.get("sockets") or [])
        for snapshot in snapshots
    )
    process_count = sum(
        len(snapshot.get("processes") or [])
        for snapshot in snapshots
    )
    linked_socket_count = sum(
        1
        for snapshot in snapshots
        for socket in snapshot.get("sockets") or []
        if socket.get("pids")
    )
    return {
        "schema_version": "0.1",
        "method": "android-proc-socket-snapshots",
        "package": package,
        "package_uid": package_uid,
        "uid_packages": sorted(set(uid_packages)),
        "uid_is_unique_to_package": sorted(set(uid_packages)) == [package],
        "sample_interval_seconds": sample_interval_seconds,
        "snapshot_count": len(snapshots),
        "socket_observations": socket_count,
        "process_observations": process_count,
        "pid_socket_links": linked_socket_count,
        "first_target_utc": (
            snapshots[0].get("target_utc") if snapshots else None
        ),
        "last_target_utc": (
            snapshots[-1].get("target_utc") if snapshots else None
        ),
    }


def write_normalized_attribution(
    root: Path,
    snapshots: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    snapshots_path = root / SNAPSHOTS_ARTIFACT
    snapshots_path.parent.mkdir(parents=True, exist_ok=True)
    with snapshots_path.open("w", encoding="utf-8", newline="\n") as handle:
        for snapshot in snapshots:
            handle.write(
                json.dumps(
                    snapshot,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            handle.write("\n")
    summary_path = root / SUMMARY_ARTIFACT
    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _socket_identity(socket: dict[str, Any]) -> tuple[Any, ...]:
    return (
        socket.get("protocol"),
        socket.get("local_ip"),
        socket.get("local_port"),
        socket.get("remote_ip"),
        socket.get("remote_port"),
        socket.get("inode"),
    )


def _is_wildcard_ip(value: str | None) -> bool:
    return value in {None, "", "0.0.0.0", "::"}


class SocketAttributionIndex:
    def __init__(
        self,
        summary: dict[str, Any],
        snapshots: list[dict[str, Any]],
    ) -> None:
        self.summary = dict(summary)
        self.package = str(summary.get("package") or "")
        self.package_uid = summary.get("package_uid")
        self.uid_packages = [
            str(value)
            for value in summary.get("uid_packages") or []
        ]
        interval = float(
            summary.get("sample_interval_seconds") or 0.2
        )
        self.margin_seconds = max(0.25, interval * 1.5)

        observations: dict[tuple[Any, ...], dict[str, Any]] = {}
        for snapshot in snapshots:
            try:
                epoch = int(snapshot["target_epoch_ns"]) / 1_000_000_000
            except (KeyError, TypeError, ValueError):
                continue
            for socket in snapshot.get("sockets") or []:
                if not isinstance(socket, dict):
                    continue
                key = _socket_identity(socket)
                current = observations.get(key)
                if current is None:
                    current = {
                        **socket,
                        "first_epoch": epoch,
                        "last_epoch": epoch,
                        "pids": set(),
                        "processes": set(),
                    }
                    observations[key] = current
                else:
                    current["last_epoch"] = epoch
                current["pids"].update(
                    int(value)
                    for value in socket.get("pids") or []
                    if isinstance(value, int) or str(value).isdigit()
                )
                current["processes"].update(
                    str(value)
                    for value in socket.get("processes") or []
                    if value
                )

        self.observations: list[dict[str, Any]] = []
        for value in observations.values():
            value["pids"] = sorted(value["pids"])
            value["processes"] = sorted(value["processes"])
            self.observations.append(value)

    @property
    def available(self) -> bool:
        return bool(self.summary) and self.package_uid is not None

    def _time_matches(self, observation: dict[str, Any], epoch: float) -> bool:
        return (
            float(observation["first_epoch"]) - self.margin_seconds
            <= epoch
            <= float(observation["last_epoch"]) + self.margin_seconds
        )

    def _match_level(
        self,
        observation: dict[str, Any],
        packet: dict[str, Any],
    ) -> str | None:
        protocol = str(packet.get("protocol") or "")
        if protocol not in {"tcp", "udp"}:
            return None
        if protocol != observation.get("protocol"):
            return None

        src = packet.get("src")
        dst = packet.get("dst")
        src_port = packet.get("src_port")
        dst_port = packet.get("dst_port")
        if (
            src is None
            or dst is None
            or src_port is None
            or dst_port is None
        ):
            return None

        local_ip = observation.get("local_ip")
        local_port = observation.get("local_port")
        remote_ip = observation.get("remote_ip")
        remote_port = observation.get("remote_port")

        forward = (
            src == local_ip
            and src_port == local_port
            and dst == remote_ip
            and dst_port == remote_port
        )
        reverse = (
            dst == local_ip
            and dst_port == local_port
            and src == remote_ip
            and src_port == remote_port
        )
        if forward or reverse:
            return "exact"

        remote_wildcard = (
            _is_wildcard_ip(str(remote_ip) if remote_ip is not None else None)
            and int(remote_port or 0) == 0
        )
        if not remote_wildcard:
            return None

        local_ip_wildcard = _is_wildcard_ip(
            str(local_ip) if local_ip is not None else None
        )
        local_match = (
            src_port == local_port
            and (local_ip_wildcard or src == local_ip)
        ) or (
            dst_port == local_port
            and (local_ip_wildcard or dst == local_ip)
        )
        if not local_match:
            return None
        return "port-only" if local_ip_wildcard else "local-endpoint"

    def attribute_packet(self, packet: dict[str, Any]) -> dict[str, Any]:
        if not self.available:
            return {
                "confidence": "UNKNOWN",
                "evidence": "socket-attribution-unavailable",
            }
        try:
            epoch = float(packet["epoch"])
        except (KeyError, TypeError, ValueError):
            return {
                "package": self.package,
                "uid": self.package_uid,
                "confidence": "UNKNOWN",
                "evidence": "packet-time-unavailable",
            }

        candidates: list[
            tuple[int, dict[str, Any], str, bool]
        ] = []
        for observation in self.observations:
            if not self._time_matches(observation, epoch):
                continue
            level = self._match_level(observation, packet)
            if level is None:
                continue
            directly_observed = (
                float(observation["first_epoch"])
                <= epoch
                <= float(observation["last_epoch"])
            )
            rank = {
                "exact": 4 if directly_observed else 3,
                "local-endpoint": 2,
                "port-only": 1,
            }[level]
            candidates.append(
                (rank, observation, level, directly_observed)
            )

        if not candidates:
            return {
                "package": self.package,
                "uid": self.package_uid,
                "uid_packages": self.uid_packages,
                "confidence": "UNKNOWN",
                "evidence": "no-matching-socket-observation",
                "ambiguity": [
                    "snapshot-sampling-may-miss-short-lived-sockets"
                ],
            }

        _, observation, level, directly_observed = max(
            candidates,
            key=lambda value: value[0],
        )
        unique_uid = self.uid_packages == [self.package]
        inode = int(observation.get("inode") or 0)
        process_names = [
            str(value)
            for value in observation.get("processes") or []
        ]
        target_process_link = any(
            value == self.package
            or value.startswith(self.package + ":")
            for value in process_names
        )

        if not unique_uid and not target_process_link:
            return {
                "package": self.package,
                "uid": self.package_uid,
                "uid_packages": self.uid_packages,
                "confidence": "UNKNOWN",
                "evidence": "shared-uid-without-target-process-socket-link",
                "inode": inode,
                "pids": observation.get("pids") or [],
                "processes": process_names,
                "ambiguity": [
                    "uid-shared-by-multiple-packages",
                    "target-package-pid-not-linked-to-socket",
                ],
            }

        if (
            level == "exact"
            and inode > 0
            and directly_observed
        ):
            confidence = "EXACT"
            evidence = (
                "unique-package-uid+socket-inode+5-tuple"
                if unique_uid
                else "target-process+socket-inode+5-tuple"
            )
            ambiguity: list[str] = []
        elif level == "exact":
            confidence = "HIGH"
            evidence = "package-owner+socket-inode+5-tuple"
            ambiguity = []
            if not directly_observed:
                ambiguity.append(
                    "packet-matched-within-snapshot-margin"
                )
            if not unique_uid:
                ambiguity.append(
                    "uid-shared-but-target-process-linked"
                )
            if inode <= 0:
                ambiguity.append(
                    "socket-inode-unavailable"
                )
        elif level == "local-endpoint":
            confidence = "HIGH" if target_process_link or unique_uid else "MEDIUM"
            evidence = "package-owner+local-endpoint+socket-inode"
            ambiguity = ["remote-endpoint-wildcard"]
            if not unique_uid:
                ambiguity.append("uid-shared-but-target-process-linked")
        else:
            confidence = "MEDIUM"
            evidence = "package-owner+local-port+socket-inode"
            ambiguity = ["local-and-remote-address-wildcard"]
            if not unique_uid:
                ambiguity.append("uid-shared-but-target-process-linked")

        return {
            "package": self.package,
            "uid": self.package_uid,
            "uid_packages": self.uid_packages,
            "confidence": confidence,
            "evidence": evidence,
            "inode": inode,
            "pids": observation.get("pids") or [],
            "processes": observation.get("processes") or [],
            "socket": {
                key: observation.get(key)
                for key in (
                    "protocol",
                    "family",
                    "local_ip",
                    "local_port",
                    "remote_ip",
                    "remote_port",
                    "state",
                )
            },
            "first_observed_utc": _iso_epoch(
                float(observation["first_epoch"])
            ),
            "last_observed_utc": _iso_epoch(
                float(observation["last_epoch"])
            ),
            "ambiguity": ambiguity,
        }

    def summarize_packets(
        self,
        packets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        counts = {
            "EXACT": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "UNKNOWN": 0,
        }
        for packet in packets:
            owner = self.attribute_packet(packet)
            confidence = str(owner.get("confidence") or "UNKNOWN")
            counts[confidence if confidence in counts else "UNKNOWN"] += 1
        attributed = counts["EXACT"] + counts["HIGH"] + counts["MEDIUM"]
        return {
            "method": self.summary.get("method")
            or "android-proc-socket-snapshots",
            "package": self.package,
            "package_uid": self.package_uid,
            "uid_packages": self.uid_packages,
            "snapshot_count": int(
                self.summary.get("snapshot_count") or 0
            ),
            "sample_interval_seconds": float(
                self.summary.get("sample_interval_seconds") or 0.0
            ),
            "packet_counts": counts,
            "attributed_packet_count": attributed,
            "total_packet_count": len(packets),
        }


def best_owner(
    first: dict[str, Any] | None,
    second: dict[str, Any],
) -> dict[str, Any]:
    if first is None:
        return second
    left = _CONFIDENCE_ORDER.get(
        str(first.get("confidence") or "UNKNOWN"),
        0,
    )
    right = _CONFIDENCE_ORDER.get(
        str(second.get("confidence") or "UNKNOWN"),
        0,
    )
    return second if right > left else first



def _endpoint(
    ip_value: Any,
    port_value: Any,
) -> tuple[str, int | None]:
    ip_text = str(ip_value or "")
    try:
        port = (
            int(port_value)
            if port_value is not None
            else None
        )
    except (TypeError, ValueError):
        port = None
    return ip_text, port


def _canonical_connection_key(
    packet: dict[str, Any],
) -> tuple[Any, ...] | None:
    protocol = str(packet.get("protocol") or "")
    if protocol not in {"tcp", "udp"}:
        return None
    src = _endpoint(
        packet.get("src"),
        packet.get("src_port"),
    )
    dst = _endpoint(
        packet.get("dst"),
        packet.get("dst_port"),
    )
    if not src[0] or not dst[0]:
        return None
    left, right = sorted(
        (src, dst),
        key=lambda value: (
            value[0],
            -1 if value[1] is None else value[1],
        ),
    )
    return protocol, left, right


def canonical_connection_key(
    packet: dict[str, Any],
) -> tuple[Any, ...] | None:
    """Public stable identity used by Timeline and Network Analyzer."""
    return _canonical_connection_key(packet)


def _packet_orientation(
    packet: dict[str, Any],
    owner: dict[str, Any],
) -> tuple[
    tuple[str, int | None] | None,
    tuple[str, int | None] | None,
]:
    socket = owner.get("socket")
    if (
        str(owner.get("confidence") or "UNKNOWN")
        != "UNKNOWN"
        and isinstance(socket, dict)
        and socket.get("local_ip")
        and socket.get("remote_ip")
    ):
        return (
            _endpoint(
                socket.get("local_ip"),
                socket.get("local_port"),
            ),
            _endpoint(
                socket.get("remote_ip"),
                socket.get("remote_port"),
            ),
        )

    direction = str(packet.get("direction") or "")
    src = _endpoint(
        packet.get("src"),
        packet.get("src_port"),
    )
    dst = _endpoint(
        packet.get("dst"),
        packet.get("dst_port"),
    )
    if direction == "outbound":
        return src, dst
    if direction == "inbound":
        return dst, src
    return None, None


def _add_unique(
    values: list[str],
    seen: set[str],
    candidate: Any,
) -> None:
    if not isinstance(candidate, str):
        return
    normalized = candidate.strip()
    if not normalized or normalized in seen:
        return
    seen.add(normalized)
    values.append(normalized)


def build_flow_inventory(
    packets: list[dict[str, Any]],
    index: SocketAttributionIndex,
) -> dict[str, Any]:
    """Build one bidirectional record for each observed 5-tuple.

    Packet ownership can improve over time.  Early UNKNOWN packets and later
    package-attributed packets therefore remain in the same normalized flow
    instead of being split into unrelated raw/owned records.
    """

    flows: dict[tuple[Any, ...], dict[str, Any]] = {}
    non_tcp_udp_packet_count = 0
    non_tcp_udp_bytes = 0
    non_tcp_udp_protocol_counts: dict[str, int] = {}
    unresolved_transport_packet_count = 0

    for packet in packets:
        try:
            epoch = float(packet["epoch"])
        except (KeyError, TypeError, ValueError):
            continue

        protocol = str(
            packet.get("protocol") or ""
        ).lower()
        length = int(
            packet.get("captured_length") or 0
        )
        if protocol not in {"tcp", "udp"}:
            non_tcp_udp_packet_count += 1
            non_tcp_udp_bytes += length
            label = protocol or "unknown"
            non_tcp_udp_protocol_counts[label] = (
                non_tcp_udp_protocol_counts.get(
                    label,
                    0,
                )
                + 1
            )
            continue

        key = _canonical_connection_key(packet)
        if key is None:
            unresolved_transport_packet_count += 1
            continue

        owner = index.attribute_packet(packet)
        confidence = str(
            owner.get("confidence") or "UNKNOWN"
        )
        if confidence not in _CONFIDENCE_ORDER:
            confidence = "UNKNOWN"

        local_endpoint, remote_endpoint = (
            _packet_orientation(
                packet,
                owner,
            )
        )
        current = flows.get(key)
        if current is None:
            current = {
                "protocol": key[0],
                "endpoint_a": {
                    "ip": key[1][0],
                    "port": key[1][1],
                },
                "endpoint_b": {
                    "ip": key[2][0],
                    "port": key[2][1],
                },
                "local_ip": (
                    local_endpoint[0]
                    if local_endpoint
                    else None
                ),
                "local_port": (
                    local_endpoint[1]
                    if local_endpoint
                    else None
                ),
                "remote_ip": (
                    remote_endpoint[0]
                    if remote_endpoint
                    else None
                ),
                "remote_port": (
                    remote_endpoint[1]
                    if remote_endpoint
                    else None
                ),
                "first_epoch": epoch,
                "last_epoch": epoch,
                "packet_count": 0,
                "captured_bytes": 0,
                "outbound_packet_count": 0,
                "outbound_bytes": 0,
                "inbound_packet_count": 0,
                "inbound_bytes": 0,
                "other_packet_count": 0,
                "other_bytes": 0,
                "attributed_packet_count": 0,
                "unknown_packet_count": 0,
                "packet_confidence_counts": {
                    "EXACT": 0,
                    "HIGH": 0,
                    "MEDIUM": 0,
                    "UNKNOWN": 0,
                },
                "owner": owner,
                "dns_queries": [],
                "tls_sni": [],
                "application_protocols": [],
                "quic_versions": [],
                "quic_packet_types": [],
                "quic_sni": [],
                "quic_alpn": [],
                "quic_initial_decrypted": False,
                "_dns": set(),
                "_sni": set(),
                "_application_protocols": set(),
                "_quic_versions": set(),
                "_quic_packet_types": set(),
                "_quic_sni": set(),
                "_quic_alpn": set(),
            }
            flows[key] = current
        else:
            current["last_epoch"] = epoch
            current["owner"] = best_owner(
                current.get("owner"),
                owner,
            )
            if (
                local_endpoint is not None
                and confidence != "UNKNOWN"
            ):
                current["local_ip"] = (
                    local_endpoint[0]
                )
                current["local_port"] = (
                    local_endpoint[1]
                )
                current["remote_ip"] = (
                    remote_endpoint[0]
                    if remote_endpoint
                    else None
                )
                current["remote_port"] = (
                    remote_endpoint[1]
                    if remote_endpoint
                    else None
                )

        current["packet_count"] += 1
        current["captured_bytes"] += length
        current[
            "packet_confidence_counts"
        ][confidence] += 1
        if confidence == "UNKNOWN":
            current["unknown_packet_count"] += 1
        else:
            current["attributed_packet_count"] += 1

        direction = str(
            packet.get("direction") or ""
        )
        if direction == "outbound":
            current["outbound_packet_count"] += 1
            current["outbound_bytes"] += length
        elif direction == "inbound":
            current["inbound_packet_count"] += 1
            current["inbound_bytes"] += length
        else:
            current["other_packet_count"] += 1
            current["other_bytes"] += length

        _add_unique(
            current["dns_queries"],
            current["_dns"],
            packet.get("dns_query"),
        )
        _add_unique(
            current["tls_sni"],
            current["_sni"],
            packet.get("tls_sni"),
        )
        _add_unique(
            current["application_protocols"],
            current["_application_protocols"],
            packet.get("application_protocol"),
        )
        _add_unique(
            current["quic_versions"],
            current["_quic_versions"],
            packet.get("quic_version"),
        )
        _add_unique(
            current["quic_packet_types"],
            current["_quic_packet_types"],
            packet.get("quic_packet_type"),
        )
        _add_unique(
            current["quic_sni"],
            current["_quic_sni"],
            packet.get("quic_sni"),
        )
        for alpn in packet.get("quic_alpn") or []:
            _add_unique(
                current["quic_alpn"],
                current["_quic_alpn"],
                alpn,
            )
        if packet.get("quic_initial_decrypted"):
            current["quic_initial_decrypted"] = True

    values: list[dict[str, Any]] = []
    confidence_counts = {
        "EXACT": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "UNKNOWN": 0,
    }
    total_outbound_bytes = 0
    total_inbound_bytes = 0

    for current in sorted(
        flows.values(),
        key=lambda value: float(
            value["first_epoch"]
        ),
    ):
        current.pop("_dns", None)
        current.pop("_sni", None)
        current.pop("_application_protocols", None)
        current.pop("_quic_versions", None)
        current.pop("_quic_packet_types", None)
        current.pop("_quic_sni", None)
        current.pop("_quic_alpn", None)
        first_epoch = float(
            current.pop("first_epoch")
        )
        last_epoch = float(
            current.pop("last_epoch")
        )
        current["first_target_utc"] = (
            _iso_epoch(first_epoch)
        )
        current["last_target_utc"] = (
            _iso_epoch(last_epoch)
        )
        current["duration_seconds"] = max(
            0.0,
            round(last_epoch - first_epoch, 6),
        )

        outbound = int(
            current["outbound_packet_count"]
        )
        inbound = int(
            current["inbound_packet_count"]
        )
        if outbound and inbound:
            current["direction"] = "bidirectional"
        elif outbound:
            current["direction"] = "outbound"
        elif inbound:
            current["direction"] = "inbound"
        else:
            current["direction"] = "unknown"

        confidence = str(
            (current.get("owner") or {}).get(
                "confidence"
            )
            or "UNKNOWN"
        )
        if confidence not in confidence_counts:
            confidence = "UNKNOWN"
        confidence_counts[confidence] += 1
        total_outbound_bytes += int(
            current["outbound_bytes"]
        )
        total_inbound_bytes += int(
            current["inbound_bytes"]
        )
        current["flow_id"] = (
            f"flow-{len(values) + 1:06d}"
        )
        values.append(current)

    attributed = (
        confidence_counts["EXACT"]
        + confidence_counts["HIGH"]
        + confidence_counts["MEDIUM"]
    )
    quic_flow_count = sum(
        1
        for item in values
        if any(
            protocol in {"quic", "http3"}
            for protocol in (
                item.get("application_protocols")
                or []
            )
        )
    )
    http3_flow_count = sum(
        1
        for item in values
        if "http3"
        in (item.get("application_protocols") or [])
    )
    quic_initial_decrypted_flow_count = sum(
        1
        for item in values
        if item.get("quic_initial_decrypted")
    )
    return {
        "schema_version": "0.3",
        "method": (
            "bidirectional-5tuple+"
            "android-proc-socket-attribution"
        ),
        "package": index.package,
        "package_uid": index.package_uid,
        "uid_packages": index.uid_packages,
        "summary": {
            "flow_count": len(values),
            "attributed_flow_count": attributed,
            "unknown_flow_count": (
                confidence_counts["UNKNOWN"]
            ),
            "confidence_counts": (
                confidence_counts
            ),
            "outbound_bytes": (
                total_outbound_bytes
            ),
            "inbound_bytes": (
                total_inbound_bytes
            ),
            "source_packet_count": len(packets),
            "quic_flow_count": quic_flow_count,
            "http3_flow_count": http3_flow_count,
            "quic_initial_decrypted_flow_count": (
                quic_initial_decrypted_flow_count
            ),
            "flow_packet_count": sum(
                int(item.get("packet_count") or 0)
                for item in values
            ),
            "non_tcp_udp_packet_count": (
                non_tcp_udp_packet_count
            ),
            "non_tcp_udp_bytes": (
                non_tcp_udp_bytes
            ),
            "non_tcp_udp_protocol_counts": dict(
                sorted(
                    non_tcp_udp_protocol_counts.items()
                )
            ),
            "unresolved_transport_packet_count": (
                unresolved_transport_packet_count
            ),
        },
        "flows": values,
    }


def write_flow_inventory(
    root: Path,
    inventory: dict[str, Any],
) -> None:
    path = root / FLOW_INVENTORY_ARTIFACT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            inventory,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
