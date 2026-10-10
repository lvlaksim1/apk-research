"""Build the Android-local HTTPS route executable from project C source.

The binary is a build output only and must not be committed. The Android NDK
is used by CI/Windows packaging; users do not need Android build tools.
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "android_route" / "https_route.c"
OUTPUT = ROOT / "build" / "android-route" / "apk-research-https-route"


def find_compiler() -> Path:
    candidates: list[Path] = []
    suffix = ".cmd" if os.name == "nt" else ""
    for name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(name)
        if not root:
            continue
        base = Path(root) / "ndk"
        if not base.is_dir():
            continue
        for ndk in sorted(base.iterdir(), reverse=True):
            for host in ("windows-x86_64", "linux-x86_64", "darwin-x86_64", "darwin-arm64"):
                compiler = (
                    ndk / "toolchains" / "llvm" / "prebuilt" / host /
                    "bin" / ("x86_64-linux-android24-clang" + suffix)
                )
                if compiler.is_file():
                    candidates.append(compiler)
    if not candidates:
        raise RuntimeError(
            "Android NDK x86_64 compiler not found. "
            "Build system must install NDK 27.2.12479018."
        )
    return candidates[0]


def build(output: Path = OUTPUT) -> Path:
    compiler = find_compiler()
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            str(compiler), "-std=c11", "-O2", "-Wall", "-Wextra",
            "-Werror", "-pthread", "-D_FORTIFY_SOURCE=2",
            "-o", str(output), str(SOURCE),
        ],
        capture_output=True, text=True, errors="replace", check=False,
        timeout=120,
    )
    if result.returncode:
        raise RuntimeError("Android transport build failed:\n" + result.stdout + result.stderr)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("Android transport output is missing or empty")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    options = parser.parse_args()
    path = build(options.output)
    print(f"ANDROID_HTTPS_ROUTE_BUILD=PASS bytes={path.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
