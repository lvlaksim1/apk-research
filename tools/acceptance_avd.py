from __future__ import annotations

import json
import sys
import time
import zipfile
from pathlib import Path

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
        time.sleep(1)
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
        if flow_inventory.get("schema_version") != "0.2":
            raise RuntimeError(
                "Network flow inventory is not schema 0.2"
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
