from mobile_research import cli


def test_parser_requires_subcommand() -> None:
    parser = cli._build_parser()

    args = parser.parse_args(["targets", "--json"])

    assert args.command == "targets"
    assert args.json is True
