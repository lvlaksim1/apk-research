from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from apk_research.collectors import DeviceMetadataCollector, MetadataCollectorError
from apk_research.export import (
    ExportError,
    audit_complete_research_zip,
    export_research_zip,
    verify_research_zip,
)
from apk_research.orchestrator import OrchestratorError, ResearchOrchestrator
from apk_research.session import SessionError, SessionManager
from apk_research.targets import AdbClient, AdbError


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apk-research",
        description="apk-research command-line interface",
    )
    parser.add_argument(
        "--adb",
        help="Explicit path to adb.exe/adb. Otherwise ADB is auto-discovered.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    targets_parser = subparsers.add_parser(
        "targets",
        help="List Android targets visible through ADB.",
    )
    targets_parser.add_argument("--json", action="store_true")

    info_parser = subparsers.add_parser(
        "target-info",
        help="Read detailed metadata from one ready ADB target.",
    )
    info_parser.add_argument("serial")
    info_parser.add_argument("--json", action="store_true")

    package_parser = subparsers.add_parser(
        "package-check",
        help="Check whether an Android package is installed on a target.",
    )
    package_parser.add_argument("serial")
    package_parser.add_argument("package")
    package_parser.add_argument("--json", action="store_true")

    session_parser = subparsers.add_parser(
        "session-create",
        help="Create a Research Session for a ready target and installed package.",
    )
    session_parser.add_argument("serial")
    session_parser.add_argument("package")
    session_parser.add_argument(
        "--root",
        type=Path,
        help="Runtime sessions root. Defaults to apk-research local app data.",
    )
    session_parser.add_argument("--json", action="store_true")

    status_parser = subparsers.add_parser(
        "session-status",
        help="Read a Research Session manifest from disk.",
    )
    status_parser.add_argument("session_root", type=Path)
    status_parser.add_argument("--json", action="store_true")

    metadata_parser = subparsers.add_parser(
        "metadata-collect",
        help="Capture raw device/package metadata for an existing session.",
    )
    metadata_parser.add_argument("session_root", type=Path)
    metadata_parser.add_argument("--json", action="store_true")

    export_parser = subparsers.add_parser(
        "session-export",
        help="Validate a terminal session and create a verified Research ZIP.",
    )
    export_parser.add_argument("session_root", type=Path)
    export_parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Destination ZIP. Defaults to <session-id>.research.zip "
            "beside the session directory."
        ),
    )
    export_parser.add_argument("--overwrite", action="store_true")
    export_parser.add_argument("--json", action="store_true")

    verify_parser = subparsers.add_parser(
        "research-zip-verify",
        help="Verify CRC, checksum coverage, and SHA-256 inside a Research ZIP.",
    )
    verify_parser.add_argument("archive", type=Path)
    verify_parser.add_argument("--json", action="store_true")

    audit_parser = subparsers.add_parser(
        "research-zip-audit",
        help=(
            "Perform semantic/timeline audit of a complete Research ZIP."
        ),
    )
    audit_parser.add_argument("archive", type=Path)
    audit_parser.add_argument("--json", action="store_true")

    run_parser = subparsers.add_parser(
        "run",
        help=(
            "Run one interactive v0.1 research session until Ctrl+C, "
            "then export a verified Research ZIP."
        ),
    )
    run_parser.add_argument("serial")
    run_parser.add_argument("package")
    run_parser.add_argument("--root", type=Path)
    run_parser.add_argument("--output", type=Path)
    run_parser.add_argument("--overwrite", action="store_true")
    run_parser.add_argument(
        "--screen-chunk-seconds",
        type=int,
        default=170,
    )
    run_parser.add_argument(
        "--health-interval",
        type=float,
        default=1.0,
    )
    run_parser.add_argument("--json", action="store_true")

    return parser


def _targets_command(client: AdbClient, as_json: bool) -> int:
    targets = client.list_targets()

    if as_json:
        _print_json([asdict(target) for target in targets])
        return 0

    if not targets:
        print("No ADB targets found.")
        return 0

    for target in targets:
        model = target.model or "-"
        print(
            f"{target.serial}\t{target.state}\t{target.kind}\tmodel={model}"
        )
    return 0


def _target_info_command(
    client: AdbClient,
    serial: str,
    as_json: bool,
) -> int:
    details = client.get_target_details(serial)

    if as_json:
        _print_json(details.to_dict())
        return 0

    for key, value in details.to_dict().items():
        print(f"{key}: {value}")
    return 0


def _package_check_command(
    client: AdbClient,
    serial: str,
    package_name: str,
    as_json: bool,
) -> int:
    installed = client.is_package_installed(serial, package_name)
    result = {
        "serial": serial,
        "package": package_name,
        "installed": installed,
    }

    if as_json:
        _print_json(result)
    else:
        print(
            f"{package_name}: "
            f"{'installed' if installed else 'not installed'} on {serial}"
        )

    return 0 if installed else 1


def _session_create_command(
    client: AdbClient,
    serial: str,
    package_name: str,
    root: Path | None,
    as_json: bool,
) -> int:
    details = client.get_target_details(serial)
    if not client.is_package_installed(serial, package_name):
        raise SessionError(
            f"Package {package_name!r} is not installed on target {serial}"
        )

    manager = SessionManager.create(
        root,
        target=details.to_dict(),
        package={"name": package_name},
    )

    result = {
        "session_id": manager.session_id,
        "status": manager.status.value,
        "session_root": str(manager.paths.root),
        "manifest": str(manager.paths.manifest),
    }

    if as_json:
        _print_json(result)
    else:
        print(f"session_id: {result['session_id']}")
        print(f"status: {result['status']}")
        print(f"session_root: {result['session_root']}")
        print(f"manifest: {result['manifest']}")

    return 0


def _session_status_command(
    session_root: Path,
    as_json: bool,
) -> int:
    manager = SessionManager.load(session_root)

    if as_json:
        _print_json(manager.manifest)
    else:
        print(f"session_id: {manager.session_id}")
        print(f"status: {manager.status.value}")
        print(f"degraded: {manager.degraded}")
        print(f"manifest: {manager.paths.manifest}")

    return 0


def _metadata_collect_command(
    client: AdbClient,
    session_root: Path,
    as_json: bool,
) -> int:
    manager = SessionManager.load(session_root)
    collector = DeviceMetadataCollector(client, manager)
    result = collector.collect()

    if as_json:
        _print_json(result.to_dict())
    else:
        print(f"collector: {result.collector}")
        print(f"status: {result.status}")
        print(f"raw_artifacts: {len(result.raw_artifacts)}")
        print(f"normalized_artifact: {result.normalized_artifact}")

    return 0


def _session_export_command(
    session_root: Path,
    output: Path | None,
    overwrite: bool,
    as_json: bool,
) -> int:
    manager = SessionManager.load(session_root)
    result = export_research_zip(
        manager,
        output,
        overwrite=overwrite,
    )

    if as_json:
        _print_json(result.to_dict())
    else:
        print(f"archive: {result.archive}")
        print(f"session_id: {result.session_id}")
        print(f"session_status: {result.session_status}")
        print(f"files: {result.file_count}")
        print(f"checksums: {result.checksum_entries}")
        print(
            "validation_issues: "
            f"{len(result.validation.issues)}"
        )

    return 0


def _research_zip_verify_command(
    archive: Path,
    as_json: bool,
) -> int:
    result = verify_research_zip(archive)

    if as_json:
        _print_json(result.to_dict())
    else:
        print(f"archive: {result.archive}")
        print(f"valid: {result.valid}")
        print(f"session_id: {result.session_id}")
        print(f"session_status: {result.session_status}")
        print(f"files: {result.file_count}")
        print(f"checksums: {result.checksum_entries}")

    return 0


def _research_zip_audit_command(
    archive: Path,
    as_json: bool,
) -> int:
    result = audit_complete_research_zip(archive)

    if as_json:
        _print_json(result.to_dict())
    else:
        print(f"archive: {result.archive}")
        print(f"session_id: {result.session_id}")
        print(f"package: {result.package}")
        print(f"packet_count: {result.packet_count}")
        print(f"logcat_entries: {result.logcat_entries}")
        print(f"screen_frames: {result.screen_frames}")
        print(
            "max_clock_skew_seconds: "
            f"{result.max_clock_skew_seconds:.3f}"
        )
        print(
            "screen_last_frame_gap_seconds: "
            f"{result.screen_last_frame_gap_seconds:.3f}"
        )

    return 0


def _run_command(
    client: AdbClient,
    serial: str,
    package_name: str,
    root: Path | None,
    output: Path | None,
    overwrite: bool,
    screen_chunk_seconds: int,
    health_interval: float,
    as_json: bool,
) -> int:
    orchestrator = ResearchOrchestrator(
        client,
        serial,
        package_name,
        runtime_root=root,
        output_path=output,
        overwrite_output=overwrite,
        screen_chunk_seconds=screen_chunk_seconds,
    )

    def on_started(started) -> None:
        if not as_json:
            print(f"session_id: {started.session_id}")
            print(f"session_root: {started.session_root}")
            print("capture: active")
            print("Press Ctrl+C to stop and export.")

    result = orchestrator.run_interactive(
        health_interval=health_interval,
        on_started=on_started,
    )

    if as_json:
        _print_json(result.to_dict())
    else:
        print(f"session_status: {result.session_status}")
        print(f"archive: {result.archive}")
        print(
            "validation_issues: "
            f"{result.validation_issues}"
        )

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "session-status":
            return _session_status_command(
                args.session_root,
                args.json,
            )
        if args.command == "session-export":
            return _session_export_command(
                args.session_root,
                args.output,
                args.overwrite,
                args.json,
            )
        if args.command == "research-zip-verify":
            return _research_zip_verify_command(
                args.archive,
                args.json,
            )
        if args.command == "research-zip-audit":
            return _research_zip_audit_command(
                args.archive,
                args.json,
            )

        client = AdbClient.from_environment(args.adb)

        if args.command == "run":
            return _run_command(
                client,
                args.serial,
                args.package,
                args.root,
                args.output,
                args.overwrite,
                args.screen_chunk_seconds,
                args.health_interval,
                args.json,
            )

        if args.command == "metadata-collect":
            return _metadata_collect_command(
                client,
                args.session_root,
                args.json,
            )

        if args.command == "targets":
            return _targets_command(client, args.json)
        if args.command == "target-info":
            return _target_info_command(client, args.serial, args.json)
        if args.command == "package-check":
            return _package_check_command(
                client,
                args.serial,
                args.package,
                args.json,
            )
        if args.command == "session-create":
            return _session_create_command(
                client,
                args.serial,
                args.package,
                args.root,
                args.json,
            )
    except (
        AdbError,
        ExportError,
        MetadataCollectorError,
        OrchestratorError,
        SessionError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    parser.error(f"Unknown command: {args.command}")
    return 2
