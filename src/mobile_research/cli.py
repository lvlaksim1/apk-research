from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any

from mobile_research.targets import AdbClient, AdbError


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mobile-research",
        description="Mobile Research command-line interface",
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


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        client = AdbClient.from_environment(args.adb)

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
    except (AdbError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    parser.error(f"Unknown command: {args.command}")
    return 2
