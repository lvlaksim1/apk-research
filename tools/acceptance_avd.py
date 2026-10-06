from __future__ import annotations

import json
import sys
import time
import zipfile
from pathlib import Path

from apk_research.desktop.packet_inspector import (
    RAW_PCAP_ARTIFACT,
    inspect_archive_flow,
)
from apk_research.export import (
    audit_complete_research_zip,
    verify_research_zip,
)
from apk_research.orchestrator import OrchestratorError, ResearchOrchestrator
from apk_research.targets import AdbClient, AdbError
from apk_research.timeline_reader import (
    read_refined_timeline_archive,
)


SERIAL = "emulator-5554"
PACKAGE_CANDIDATES = (
    "com.android.settings",
    "com.android.launcher3",
    "com.android.dialer",
    "com.android.contacts",
)
OUTPUT_ROOT = Path("acceptance-output").resolve()
SESSION_ROOT = OUTPUT_ROOT / "sessions"
ARCHIVE = OUTPUT_ROOT / "apk-research-acceptance.research.zip"


def select_package(client: AdbClient) -> str:
    diagnostics: list[str] = []

    for package_name in PACKAGE_CANDIDATES:
        try:
            if not client.is_package_installed(SERIAL, package_name):
                diagnostics.append(f"{package_name}: not installed")
                continue
            component = client.resolve_launch_activity(
                SERIAL,
                package_name,
            )
            print(json.dumps({
                "event": "acceptance_target_selected",
                "package": package_name,
                "component": component,
            }, ensure_ascii=False))
            return package_name
        except AdbError as exc:
            diagnostics.append(f"{package_name}: {exc}")

    raise RuntimeError(
        "No launchable acceptance package found: "
        + "; ".join(diagnostics)
    )


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    client = AdbClient.from_environment()
    package_name = select_package(client)

    prewarm_output = client.launch_package(
        SERIAL,
        package_name,
    )
    time.sleep(0.5)
    prewarm_pids = client.get_process_ids(
        SERIAL,
        package_name,
    )
    if not prewarm_pids:
        raise RuntimeError(
            "Unable to prewarm acceptance package before clean launch"
        )
    print(json.dumps({
        "event": "acceptance_target_prewarmed",
        "package": package_name,
        "pids": prewarm_pids,
        "launch": prewarm_output[-1000:],
    }, ensure_ascii=False))

    orchestrator = ResearchOrchestrator(
        client,
        SERIAL,
        package_name,
        runtime_root=SESSION_ROOT,
        output_path=ARCHIVE,
        overwrite_output=True,
        screen_chunk_seconds=30,
        launch_mode="clean",
    )

    try:
        started = orchestrator.start()
        print(json.dumps({"event": "started", **started.to_dict()}, ensure_ascii=False))

        try:
            ping_output = client.shell_output(
                SERIAL,
                "ping",
                "-c",
                "2",
                "10.0.2.2",
                timeout=20.0,
            )
            print(json.dumps({
                "event": "network_probe",
                "status": "ok",
                "output": ping_output[-1000:],
            }, ensure_ascii=False))
        except AdbError as exc:
            print(json.dumps({
                "event": "network_probe",
                "status": "failed",
                "error": str(exc),
            }, ensure_ascii=False))

        time.sleep(1)

        orchestrator.record_user_action(
            "key",
            details={
                "source": "avd-acceptance",
                "key": "HOME",
                "keycode": 3,
            },
        )
        client.shell_output(
            SERIAL,
            "input",
            "keyevent",
            "3",
        )
        print(json.dumps({
            "event": "continuous_screen_idle_probe",
            "status": "started",
            "idle_seconds": 10.0,
        }, ensure_ascii=False))
        time.sleep(10.0)
        client.launch_package(SERIAL, package_name)
        print(json.dumps({
            "event": "screen_activity_probe",
            "status": "ok",
        }, ensure_ascii=False))
        time.sleep(1)

        health = orchestrator.health_check()
        print(json.dumps({"event": "health", **health.to_dict()}, ensure_ascii=False))

        result = orchestrator.stop_and_export()
        print(json.dumps({"event": "stopped", **result.to_dict()}, ensure_ascii=False))

        verification = verify_research_zip(result.archive)
        print(json.dumps({"event": "verified", **verification.to_dict()}, ensure_ascii=False))

        if result.session_status != "complete":
            raise RuntimeError(
                "Real AVD acceptance did not finish complete: "
                f"{result.session_status}"
            )
        if not verification.valid:
            raise RuntimeError("Research ZIP verification failed")

        with zipfile.ZipFile(result.archive) as archive:
            launch_evidence = archive.read(
                "01_raw/device/package-launch.txt"
            ).decode("utf-8", errors="replace")
            archived_timeline = json.loads(
                archive.read(
                    "02_normalized/research-timeline.json"
                )
            )
        if "LaunchState: COLD" not in launch_evidence:
            raise RuntimeError(
                "Clean launch did not produce LaunchState: COLD"
            )
        if "Activity not started" in launch_evidence:
            raise RuntimeError(
                "Clean launch reused an existing activity instance"
            )
        if archived_timeline.get("schema_version") != "0.4":
            raise RuntimeError(
                "Exported Research Timeline is not schema 0.4"
            )
        archived_alignment = (
            archived_timeline.get("clock_alignment") or {}
        )
        if (
            archived_alignment.get("method")
            != "adb-ntp-midpoint"
        ):
            raise RuntimeError(
                "Exported Research Timeline does not use "
                "high-resolution clock calibration"
            )
        network_attribution = (
            archived_timeline.get("network_attribution") or {}
        )
        if (
            network_attribution.get("method")
            != "android-proc-socket-snapshots"
        ):
            raise RuntimeError(
                "Package-aware network attribution is missing"
            )
        if int(
            network_attribution.get("snapshot_count") or 0
        ) <= 0:
            raise RuntimeError(
                "Socket attribution produced no snapshots"
            )
        with zipfile.ZipFile(result.archive) as archive:
            attribution_summary = json.loads(
                archive.read(
                    "02_normalized/socket-attribution.json"
                )
            )
            attribution_lines = archive.read(
                "02_normalized/socket-attribution.jsonl"
            ).decode("utf-8").splitlines()
            flow_inventory = json.loads(
                archive.read(
                    "02_normalized/network-flows.json"
                )
            )
        if (
            attribution_summary.get("method")
            != "android-proc-socket-snapshots"
        ):
            raise RuntimeError(
                "Socket attribution summary is invalid"
            )
        if int(
            attribution_summary.get("snapshot_count") or 0
        ) <= 0 or not attribution_lines:
            raise RuntimeError(
                "Socket attribution evidence is empty"
            )
        if int(
            attribution_summary.get("process_observations") or 0
        ) <= 0:
            raise RuntimeError(
                "Socket attribution captured no target-UID processes"
            )
        target_process_seen = False
        for line in attribution_lines:
            if not line.strip():
                continue
            try:
                snapshot = json.loads(line)
            except json.JSONDecodeError:
                continue
            for process in snapshot.get("processes") or []:
                if not isinstance(process, dict):
                    continue
                process_name = str(process.get("name") or "")
                if (
                    process_name == package_name
                    or process_name.startswith(package_name + ":")
                ):
                    target_process_seen = True
                    break
            if target_process_seen:
                break
        if not target_process_seen:
            raise RuntimeError(
                "Socket attribution did not observe the target package process"
            )
        if flow_inventory.get("schema_version") != "0.3":
            raise RuntimeError(
                "Network flow inventory is not schema 0.3"
            )
        if (
            flow_inventory.get("method")
            != (
                "bidirectional-5tuple+"
                "android-proc-socket-attribution"
            )
        ):
            raise RuntimeError(
                "Bidirectional attributed network flow inventory is missing"
            )
        flow_summary = flow_inventory.get("summary") or {}
        if int(flow_summary.get("flow_count") or 0) <= 0:
            raise RuntimeError(
                "Normalized network flow inventory is empty"
            )
        for flow in flow_inventory.get("flows") or []:
            if not isinstance(flow, dict):
                raise RuntimeError(
                    "Network flow inventory contains an invalid item"
                )
            if int(flow.get("packet_count") or 0) <= 0:
                raise RuntimeError(
                    "Normalized network flow has no packets"
                )
            if (
                int(flow.get("outbound_packet_count") or 0)
                + int(flow.get("inbound_packet_count") or 0)
                + int(flow.get("other_packet_count") or 0)
                != int(flow.get("packet_count") or 0)
            ):
                raise RuntimeError(
                    "Normalized network flow direction counts are inconsistent"
                )

        flow_records = [
            flow
            for flow in flow_inventory.get("flows") or []
            if isinstance(flow, dict)
        ]
        if not flow_records:
            raise RuntimeError(
                "Packet Inspector acceptance has no normalized flow"
            )
        inspected_flow = next(
            (
                flow
                for flow in flow_records
                if flow.get("correlated_action_ids")
            ),
            flow_records[0],
        )
        packet_report = inspect_archive_flow(
            Path(result.archive),
            inspected_flow,
        )
        if packet_report.get("artifact") != RAW_PCAP_ARTIFACT:
            raise RuntimeError(
                "Packet Inspector did not preserve raw PCAP provenance"
            )
        if int(
            packet_report.get("selected_packet_count") or 0
        ) != int(inspected_flow.get("packet_count") or 0):
            raise RuntimeError(
                "Packet Inspector packet count does not match normalized flow"
            )
        inspected_packets = packet_report.get("packets") or []
        if not inspected_packets:
            raise RuntimeError(
                "Packet Inspector returned no packet records"
            )
        if packet_report.get("correlation_type") != "temporal-only":
            raise RuntimeError(
                "Packet Inspector action relation is not temporal-only"
            )
        if packet_report.get("causal_claim") is not False:
            raise RuntimeError(
                "Packet Inspector must not claim packet/action causality"
            )

        correlated_ids = {
            str(value)
            for value in inspected_flow.get("correlated_action_ids") or []
            if value
        }
        archived_action_ids = {
            str(action.get("action_id") or "")
            for action in archived_timeline.get("user_actions") or []
            if isinstance(action, dict)
        }
        if correlated_ids:
            if int(
                packet_report.get("packet_action_match_count") or 0
            ) <= 0:
                raise RuntimeError(
                    "Packet Inspector did not resolve an existing "
                    "flow/action Timeline window"
                )
            for packet in inspected_packets:
                for relation in packet.get("temporal_actions") or []:
                    if not isinstance(relation, dict):
                        raise RuntimeError(
                            "Packet Inspector emitted invalid action relation"
                        )
                    action_id = str(
                        relation.get("action_id") or ""
                    )
                    if action_id not in correlated_ids:
                        raise RuntimeError(
                            "Packet Inspector linked an action not correlated "
                            "with the selected flow"
                        )
                    if action_id not in archived_action_ids:
                        raise RuntimeError(
                            "Packet Inspector linked an action missing from "
                            "the archived Timeline"
                        )
                    if relation.get("attribution") != "temporal-only":
                        raise RuntimeError(
                            "Packet/action relation lost temporal-only semantics"
                        )
                    if relation.get("causal_claim") is not False:
                        raise RuntimeError(
                            "Packet/action relation claims causality"
                        )

        tcp_flow = next(
            (
                flow
                for flow in flow_records
                if str(flow.get("protocol") or "").lower() == "tcp"
            ),
            None,
        )
        tcp_session_status = "no-tcp-flow-observed"
        if tcp_flow is not None:
            tcp_report = inspect_archive_flow(
                Path(result.archive),
                tcp_flow,
            )
            transport_session = tcp_report.get("transport_session")
            if (
                not isinstance(transport_session, dict)
                or transport_session.get("applicable") is not True
                or transport_session.get("protocol") != "tcp"
            ):
                raise RuntimeError(
                    "Packet Inspector TCP session summary is missing"
                )
            tcp_packets = [
                packet
                for packet in tcp_report.get("packets") or []
                if isinstance(packet, dict)
            ]
            if not tcp_packets:
                raise RuntimeError(
                    "Packet Inspector TCP session has no packets"
                )
            valid_headers = [
                packet
                for packet in tcp_packets
                if packet.get("tcp_header_valid") is True
            ]
            if not valid_headers:
                raise RuntimeError(
                    "Packet Inspector did not expose any valid TCP header"
                )
            for packet in valid_headers:
                if not isinstance(packet.get("tcp_flags"), list):
                    raise RuntimeError(
                        "Packet Inspector TCP flags are not structured"
                    )
                if packet.get("tcp_sequence") is None:
                    raise RuntimeError(
                        "Packet Inspector TCP sequence is missing"
                    )
                if packet.get("tcp_acknowledgment") is None:
                    raise RuntimeError(
                        "Packet Inspector TCP acknowledgment is missing"
                    )
                header_length = int(
                    packet.get("tcp_header_length") or 0
                )
                if header_length < 20:
                    raise RuntimeError(
                        "Packet Inspector TCP header length is invalid"
                    )
                if int(packet.get("tcp_payload_length") or 0) < 0:
                    raise RuntimeError(
                        "Packet Inspector TCP payload length is invalid"
                    )

            handshake_status = str(
                transport_session.get("handshake_status") or ""
            )
            if handshake_status not in {
                "complete-three-way-observed",
                "partial-or-not-observed-in-capture",
            }:
                raise RuntimeError(
                    "Packet Inspector emitted unsupported handshake status"
                )
            termination_status = str(
                transport_session.get("termination_status") or ""
            )
            if termination_status not in {
                "reset-observed",
                "fin-observed",
                "not-observed-in-capture",
            }:
                raise RuntimeError(
                    "Packet Inspector emitted unsupported termination status"
                )
            absence_semantics = str(
                transport_session.get("absence_semantics") or ""
            )
            if "does not prove" not in absence_semantics:
                raise RuntimeError(
                    "Packet Inspector lost capture-absence semantics"
                )
            tcp_session_status = (
                handshake_status + "/" + termination_status
            )

        first_packet = inspected_packets[0]
        if int(first_packet.get("pcap_record_offset") or -1) < 24:
            raise RuntimeError(
                "Packet Inspector raw record offset is invalid"
            )
        if int(first_packet.get("pcap_frame_offset") or -1) <= int(
            first_packet.get("pcap_record_offset") or -1
        ):
            raise RuntimeError(
                "Packet Inspector frame offset is not after record header"
            )
        print(json.dumps({
            "event": "packet_inspector_acceptance",
            "flow_id": packet_report.get("flow_id"),
            "selected_packet_count": packet_report.get("selected_packet_count"),
            "pcap_packet_count": packet_report.get("total_packet_count"),
            "pcap_crc32": packet_report.get("artifact_crc32"),
            "timeline_action_windows": packet_report.get(
                "timeline_action_window_count"
            ),
            "matched_packets": packet_report.get(
                "packet_action_match_count"
            ),
            "correlation_type": packet_report.get("correlation_type"),
            "causal_claim": packet_report.get("causal_claim"),
            "tcp_session_status": tcp_session_status,
        }, ensure_ascii=False))

        with zipfile.ZipFile(result.archive) as archive:
            continuous_metadata = json.loads(
                archive.read(
                    "02_normalized/continuous-screen.json"
                )
            )
            continuous_index_text = archive.read(
                "02_normalized/continuous-screen-packets.jsonl"
            ).decode("utf-8")
            continuous_h264 = archive.read(
                "01_raw/screen/continuous-screen.h264"
            )
            screen_ab = json.loads(
                archive.read(
                    "02_normalized/screen-ab-comparison.json"
                )
            )

        sidecar_ports: set[int] = set()
        for section_name in ("sidecar_handshake", "stream"):
            section = continuous_metadata.get(section_name)
            if not isinstance(section, dict):
                continue
            for key in ("host_port", "device_port"):
                try:
                    port = int(section.get(key))
                except (TypeError, ValueError):
                    continue
                if 1 <= port <= 65535:
                    sidecar_ports.add(port)

        leaked_sidecar_flows = []
        for flow in flow_inventory.get("flows") or []:
            if not isinstance(flow, dict):
                continue
            endpoints = (
                flow.get("endpoint_a") or {},
                flow.get("endpoint_b") or {},
            )
            endpoint_ips = {
                str(endpoint.get("ip") or "")
                for endpoint in endpoints
                if isinstance(endpoint, dict)
            }
            endpoint_ports = {
                int(endpoint.get("port"))
                for endpoint in endpoints
                if isinstance(endpoint, dict)
                and str(endpoint.get("port") or "").isdigit()
            }
            if (
                endpoint_ips
                and endpoint_ips <= {"127.0.0.1", "::1"}
                and endpoint_ports & sidecar_ports
            ):
                leaked_sidecar_flows.append(
                    str(flow.get("flow_id") or "")
                )
        if leaked_sidecar_flows:
            raise RuntimeError(
                "Sidecar infrastructure leaked into normalized app flows: "
                + ", ".join(leaked_sidecar_flows)
            )
        if int(
            flow_summary.get("infrastructure_packet_count") or 0
        ) <= 0:
            raise RuntimeError(
                "Real AVD did not classify captured sidecar infrastructure"
            )

        if continuous_metadata.get("canonical") is not False:
            raise RuntimeError(
                "Continuous screen evidence must remain non-canonical"
            )
        if continuous_metadata.get("experimental") is not True:
            raise RuntimeError(
                "Continuous screen evidence is not marked experimental"
            )
        if continuous_metadata.get("status") != "completed":
            raise RuntimeError(
                "Continuous screen collector did not complete: "
                + str(continuous_metadata.get("status"))
            )

        continuous_packet_count = int(
            continuous_metadata.get("packet_count") or 0
        )
        continuous_frame_count = int(
            continuous_metadata.get("media_frame_count") or 0
        )
        continuous_bytes = int(
            continuous_metadata.get("bytes_captured") or 0
        )
        continuous_span = float(
            continuous_metadata.get(
                "presentation_span_seconds"
            )
            or 0.0
        )
        if continuous_packet_count <= 0:
            raise RuntimeError(
                "Continuous screen collector produced no packets"
            )
        if continuous_frame_count <= 0:
            raise RuntimeError(
                "Continuous screen collector produced no media frames"
            )
        if continuous_bytes <= 0 or not continuous_h264:
            raise RuntimeError(
                "Continuous screen collector produced no H.264 bytes"
            )
        if continuous_span <= 0:
            raise RuntimeError(
                "Continuous screen device PTS span is empty"
            )

        continuous_records = []
        for raw_line in continuous_index_text.splitlines():
            if not raw_line.strip():
                continue
            continuous_records.append(
                json.loads(raw_line)
            )
        if len(continuous_records) != continuous_packet_count:
            raise RuntimeError(
                "Continuous screen packet index count mismatch"
            )

        expected_offset = 0
        indexed_bytes = 0
        config_packets = 0
        media_packets = 0
        eos_packets = 0
        previous_pts = None
        for record in continuous_records:
            size = int(record.get("size") or 0)
            offset = int(record.get("raw_offset") or 0)
            if offset != expected_offset:
                raise RuntimeError(
                    "Continuous screen raw offsets are not contiguous"
                )
            if size < 0:
                raise RuntimeError(
                    "Continuous screen packet has negative size"
                )
            expected_offset += size
            indexed_bytes += size

            if record.get("end_of_stream") is True:
                eos_packets += 1
            if record.get("codec_config") is True:
                config_packets += 1
            elif size > 0:
                media_packets += 1
                pts = int(record.get("pts_us") or 0)
                if previous_pts is not None and pts < previous_pts:
                    raise RuntimeError(
                        "Continuous screen MediaCodec PTS regressed"
                    )
                previous_pts = pts

        if config_packets <= 0:
            raise RuntimeError(
                "Continuous screen stream contains no codec config"
            )
        if media_packets != continuous_frame_count:
            raise RuntimeError(
                "Continuous screen media frame count mismatch"
            )
        if (
            eos_packets != 1
            or continuous_records[-1].get("end_of_stream") is not True
        ):
            raise RuntimeError(
                "Continuous screen stream has no unique terminal EOS record"
            )
        if (
            indexed_bytes != continuous_bytes
            or indexed_bytes != len(continuous_h264)
        ):
            raise RuntimeError(
                "Continuous screen byte accounting mismatch"
            )

        stop_info = continuous_metadata.get("stop")
        if not isinstance(stop_info, dict):
            raise RuntimeError(
                "Continuous screen stop statistics are missing"
            )
        if int(stop_info.get("packet_count") or 0) != continuous_packet_count:
            raise RuntimeError(
                "Agent and host continuous-screen packet counts differ"
            )
        if int(stop_info.get("byte_count") or 0) != continuous_bytes:
            raise RuntimeError(
                "Agent and host continuous-screen byte counts differ"
            )

        cleanup = continuous_metadata.get("cleanup")
        if (
            not isinstance(cleanup, dict)
            or cleanup.get("complete") is not True
        ):
            raise RuntimeError(
                "Continuous screen sidecar cleanup is incomplete"
            )

        if screen_ab.get("canonical_backend") != "adb-screenrecord":
            raise RuntimeError(
                "Screen A/B report lost canonical screenrecord backend"
            )
        if (
            screen_ab.get("experimental_backend")
            != "android-sidecar-mediacodec-h264"
        ):
            raise RuntimeError(
                "Screen A/B report has unexpected experimental backend"
            )
        if screen_ab.get("canonical_status") != "completed":
            raise RuntimeError(
                "Screen A/B canonical backend did not complete"
            )
        if screen_ab.get("experimental_status") != "completed":
            raise RuntimeError(
                "Screen A/B experimental backend did not complete"
            )
        if screen_ab.get("promotion_decision") != "not-automatic":
            raise RuntimeError(
                "Screen A/B report must not auto-promote experimental capture"
            )
        if int(
            screen_ab.get("experimental_packet_count") or 0
        ) != continuous_packet_count:
            raise RuntimeError(
                "Screen A/B report packet count mismatch"
            )

        print(json.dumps({
            "event": "continuous_screen_acceptance",
            "packet_count": continuous_packet_count,
            "media_frame_count": continuous_frame_count,
            "bytes_captured": continuous_bytes,
            "presentation_span_seconds": continuous_span,
            "config_packets": config_packets,
            "eos_packets": eos_packets,
            "canonical_capture_span_seconds": (
                screen_ab.get("canonical_capture_span_seconds")
            ),
            "canonical_presentation_span_seconds": (
                screen_ab.get("canonical_presentation_span_seconds")
            ),
            "experimental_presentation_span_seconds": (
                screen_ab.get("experimental_presentation_span_seconds")
            ),
            "promotion_decision": screen_ab.get("promotion_decision"),
        }, ensure_ascii=False))

        if "non_tcp_udp_packet_count" not in flow_summary:
            raise RuntimeError(
                "Network flow inventory does not report non-TCP/UDP packets"
            )
        timeline_summary = archived_timeline.get("summary") or {}
        if int(
            timeline_summary.get("network_markers") or 0
        ) != int(flow_summary.get("flow_count") or 0):
            raise RuntimeError(
                "Timeline network markers are not normalized flow markers"
            )
        flow_events = [
            item
            for item in archived_timeline.get("events") or []
            if isinstance(item, dict)
            and item.get("kind") == "network_flow"
        ]
        if len(flow_events) != int(
            flow_summary.get("flow_count") or 0
        ):
            raise RuntimeError(
                "Timeline network flow event count does not match inventory"
            )
        if any(
            not str(item.get("flow_id") or "")
            for item in flow_events
        ):
            raise RuntimeError(
                "Timeline network flow event is missing flow_id"
            )

        archived_actions = (
            archived_timeline.get("user_actions") or []
        )
        if not archived_actions:
            raise RuntimeError(
                "Exported Research Timeline has no user actions"
            )
        archived_correlation = (
            archived_actions[0].get("correlation") or {}
        )
        archived_window = (
            archived_correlation.get("window") or {}
        )
        if archived_correlation.get("causal_claim") is not False:
            raise RuntimeError(
                "Exported Timeline must not claim proven causality"
            )
        if (
            archived_correlation.get("attribution")
            != "temporal-only"
        ):
            raise RuntimeError(
                "Exported Timeline attribution is not temporal-only"
            )
        if (
            archived_window.get("exclusive_until_next_action")
            is not True
        ):
            raise RuntimeError(
                "Exported Timeline correlation window is not exclusive"
            )

        audit = audit_complete_research_zip(result.archive)
        print(json.dumps({
            "event": "semantic_audit",
            **audit.to_dict(),
        }, ensure_ascii=False))

        refined = read_refined_timeline_archive(
            result.archive
        )
        if refined.get("schema_version") != "0.4":
            raise RuntimeError(
                "Refined Research Timeline is not schema 0.4"
            )
        refined_actions = refined.get(
            "user_actions"
        ) or []
        if len(refined_actions) < 1:
            raise RuntimeError(
                "Refined Research Timeline has no user actions"
            )
        alignment = refined.get(
            "clock_alignment"
        ) or {}
        if alignment.get("method") != "adb-ntp-midpoint":
            raise RuntimeError(
                "High-resolution clock calibration is missing"
            )
        first_correlation = (
            refined_actions[0].get(
                "correlation"
            )
            or {}
        )
        window = first_correlation.get(
            "window"
        ) or {}
        if (
            window.get(
                "exclusive_until_next_action"
            )
            is not True
        ):
            raise RuntimeError(
                "Adaptive exclusive correlation window is missing"
            )

        if audit.screen_last_frame_gap_seconds > 4.0:
            raise RuntimeError(
                "Screen frame evidence did not reach the controlled "
                "late-session UI activity: "
                f"gap={audit.screen_last_frame_gap_seconds:.3f}s"
            )

        return 0
    except OrchestratorError as exc:
        print(json.dumps({
            "event": "orchestrator_error",
            "error": str(exc),
            "session_root": str(exc.session_root) if exc.session_root is not None else None,
            "archive": exc.archive,
        }, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
