from __future__ import annotations

import json
import sys
import time
import zipfile
from pathlib import Path

from mobile_research.export import (
    audit_complete_research_zip,
    verify_research_zip,
)
from mobile_research.orchestrator import OrchestratorError, ResearchOrchestrator
from mobile_research.targets import AdbClient, AdbError
from mobile_research.timeline_reader import (
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
ARCHIVE = OUTPUT_ROOT / "mobile-research-acceptance.research.zip"


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

    orchestrator = ResearchOrchestrator(
        client,
        SERIAL,
        package_name,
        runtime_root=SESSION_ROOT,
        output_path=ARCHIVE,
        overwrite_output=True,
        screen_chunk_seconds=30,
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
            archived_timeline = json.loads(
                archive.read(
                    "02_normalized/research-timeline.json"
                )
            )
        if archived_timeline.get("schema_version") != "0.3":
            raise RuntimeError(
                "Exported Research Timeline is not schema 0.3"
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
