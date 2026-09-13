from pathlib import Path

from mobile_research import cli


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
