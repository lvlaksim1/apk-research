from pathlib import Path
import tomllib


def test_package_import() -> None:
    import mobile_research

    pyproject = tomllib.loads(
        Path("pyproject.toml").read_text(
            encoding="utf-8"
        )
    )
    assert (
        mobile_research.__version__
        == pyproject["project"]["version"]
    )
