from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = (
    ROOT
    / "android_sidecar"
    / "src"
)
DEFAULT_OUTPUT = (
    ROOT
    / "build"
    / "android-sidecar"
    / "apk-research-agent.jar"
)


def _android_roots() -> list[Path]:
    roots: list[Path] = []
    for variable in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        value = os.environ.get(variable)
        if value:
            path = Path(value)
            if path not in roots:
                roots.append(path)
    return roots


def _version_key(path: Path) -> tuple[int, ...]:
    values: list[int] = []
    for token in path.name.replace("-", ".").split("."):
        try:
            values.append(int(token))
        except ValueError:
            values.append(-1)
    return tuple(values)


def _find_d8() -> Path:
    names = ("d8.bat", "d8") if os.name == "nt" else ("d8", "d8.bat")
    candidates: list[Path] = []
    for root in _android_roots():
        base = root / "build-tools"
        if not base.is_dir():
            continue
        for version in base.iterdir():
            if not version.is_dir():
                continue
            for name in names:
                candidate = version / name
                if candidate.is_file():
                    candidates.append(candidate)
                    break
    if not candidates:
        found = shutil.which("d8")
        if found:
            return Path(found)
        raise RuntimeError(
            "Android d8 was not found; install Android build-tools"
        )
    return sorted(
        candidates,
        key=lambda path: _version_key(path.parent),
    )[-1]


def _find_android_jar() -> Path:
    candidates: list[Path] = []
    for root in _android_roots():
        base = root / "platforms"
        if not base.is_dir():
            continue
        candidates.extend(
            path
            for path in base.glob("android-*/android.jar")
            if path.is_file()
        )
    if not candidates:
        raise RuntimeError(
            "android.jar was not found; install an Android platform"
        )
    return sorted(
        candidates,
        key=lambda path: _version_key(path.parent),
    )[-1]


def _run_d8(d8: Path, arguments: list[str]) -> None:
    command = [str(d8), *arguments]
    if os.name == "nt" and d8.suffix.lower() in {".bat", ".cmd"}:
        comspec = os.environ.get("COMSPEC") or "cmd.exe"
        command = [
            comspec,
            "/d",
            "/s",
            "/c",
            subprocess.list2cmdline([str(d8), *arguments]),
        ]
    subprocess.run(command, check=True)


def build(output: Path) -> Path:
    sources = sorted(
        path
        for path in SOURCE_ROOT.rglob("*.java")
        if path.is_file()
    )
    if not sources:
        raise RuntimeError(
            f"Sidecar sources not found under: {SOURCE_ROOT}"
        )

    javac = shutil.which("javac")
    if not javac:
        raise RuntimeError("javac was not found")

    d8 = _find_d8()
    android_jar = _find_android_jar()

    with tempfile.TemporaryDirectory(
        prefix="apk-research-sidecar-"
    ) as temp_name:
        temp = Path(temp_name)
        classes = temp / "classes"
        dex = temp / "dex"
        classes.mkdir()
        dex.mkdir()

        subprocess.run(
            [
                javac,
                "-encoding",
                "UTF-8",
                "-source",
                "8",
                "-target",
                "8",
                "-classpath",
                str(android_jar),
                "-d",
                str(classes),
                *(str(path) for path in sources),
            ],
            check=True,
        )

        class_files = sorted(
            str(path)
            for path in classes.rglob("*.class")
        )
        if not class_files:
            raise RuntimeError("javac produced no class files")

        _run_d8(
            d8,
            [
                "--lib",
                str(android_jar),
                "--min-api",
                "21",
                "--output",
                str(dex),
                *class_files,
            ],
        )

        classes_dex = dex / "classes.dex"
        if not classes_dex.is_file():
            raise RuntimeError("d8 did not produce classes.dex")

        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".jar.tmp")
        temporary.unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(
                temporary,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.write(classes_dex, "classes.dex")
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)

    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    args = parser.parse_args()
    try:
        path = build(args.output.resolve())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
