from pathlib import Path
import tomllib


def test_package_import() -> None:
    import apk_research

    pyproject = tomllib.loads(
        Path("pyproject.toml").read_text(
            encoding="utf-8"
        )
    )
    assert (
        apk_research.__version__
        == pyproject["project"]["version"]
    )
