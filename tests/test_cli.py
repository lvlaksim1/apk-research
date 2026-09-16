from pathlib import Path

from apk_research import cli


def test_parser_targets_json() -> None:
    parser = cli._build_parser()

    args = parser.parse_args(["targets", "--json"])

    assert args.command == "targets"
    assert args.json is True


def test_parser_session_create() -> None:
    parser = cli._build_parser()

    args = parser.parse_args(
        [
            "session-create",
            "emulator-5554",
            "com.example.app",
            "--root",
            "runtime",
            "--json",
        ]
    )

    assert args.command == "session-create"
    assert args.serial == "emulator-5554"
    assert args.package == "com.example.app"
    assert args.root == Path("runtime")
    assert args.json is True


def test_parser_metadata_collect() -> None:
    parser = cli._build_parser()

    args = parser.parse_args(
        ["metadata-collect", "runtime/session-1", "--json"]
    )

    assert args.command == "metadata-collect"
    assert args.session_root == Path("runtime/session-1")
    assert args.json is True


def test_parser_session_export() -> None:
    parser = cli._build_parser()

    args = parser.parse_args(
        [
            "session-export",
            "runtime/session-1",
            "--output",
            "result.zip",
            "--overwrite",
            "--json",
        ]
    )

    assert args.command == "session-export"
    assert args.session_root == Path("runtime/session-1")
    assert args.output == Path("result.zip")
    assert args.overwrite is True
    assert args.json is True


def test_parser_research_zip_verify() -> None:
    parser = cli._build_parser()

    args = parser.parse_args(
        ["research-zip-verify", "result.zip", "--json"]
    )

    assert args.command == "research-zip-verify"
    assert args.archive == Path("result.zip")
    assert args.json is True


def test_parser_run() -> None:
    parser = cli._build_parser()

    args = parser.parse_args(
        [
            "run",
            "emulator-5554",
            "com.example.app",
            "--root",
            "runtime",
            "--output",
            "result.zip",
            "--screen-chunk-seconds",
            "120",
            "--health-interval",
            "2.5",
            "--json",
        ]
    )

    assert args.command == "run"
    assert args.serial == "emulator-5554"
    assert args.package == "com.example.app"
    assert args.root == Path("runtime")
    assert args.output == Path("result.zip")
    assert args.screen_chunk_seconds == 120
    assert args.health_interval == 2.5
    assert args.json is True



def test_parser_research_zip_audit() -> None:
    parser = cli._build_parser()

    args = parser.parse_args(
        ["research-zip-audit", "result.zip", "--json"]
    )

    assert args.command == "research-zip-audit"
    assert args.archive == Path("result.zip")
    assert args.json is True
