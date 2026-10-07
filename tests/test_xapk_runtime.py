from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

from apk_research.desktop.android_runtime import (
    AndroidRuntime,
    AndroidRuntimeError,
)
from apk_research.desktop.components import ComponentManager


def _runtime(tmp_path: Path) -> AndroidRuntime:
    manager = ComponentManager(tmp_path / "runtime")
    manager.paths.adb.parent.mkdir(parents=True, exist_ok=True)
    manager.paths.adb.write_bytes(b"adb")
    manager.paths.aapt2.parent.mkdir(parents=True, exist_ok=True)
    manager.paths.aapt2.write_bytes(b"aapt2")
    return AndroidRuntime(manager)


def test_install_xapk_uses_install_multiple_and_pushes_obb(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime = _runtime(tmp_path)
    archive_path = tmp_path / "sample.xapk"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("base.apk", b"base")
        archive.writestr(
            "splits/config.arm64_v8a.apk",
            b"split",
        )
        archive.writestr(
            "Android/obb/com.example.app/"
            "main.42.com.example.app.obb",
            b"obb",
        )

    commands: list[list[str]] = []
    shell_commands: list[tuple[str, ...]] = []

    def fake_run(command, *, timeout, check=True):
        cmd = [str(item) for item in command]
        commands.append(cmd)
        if "aapt2" in Path(cmd[0]).name.lower():
            name = Path(cmd[-1]).name
            if name == "base.apk":
                stdout = (
                    "package: name='com.example.app' "
                    "versionCode='42' versionName='1.0'\n"
                )
            else:
                stdout = (
                    "package: name='com.example.app' "
                    "versionCode='42' versionName='1.0' "
                    "split='config.arm64_v8a'\n"
                )
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=stdout,
                stderr="",
            )
        if "install-multiple" in cmd:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="Success\n",
                stderr="",
            )
        if "push" in cmd:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="1 file pushed\n",
                stderr="",
            )
        raise AssertionError(cmd)

    def fake_shell(*args, timeout=15.0, check=True):
        shell_commands.append(tuple(str(item) for item in args))
        return subprocess.CompletedProcess(
            ["adb", "shell", *args],
            0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(runtime, "_run", fake_run)
    monkeypatch.setattr(runtime, "_adb_shell", fake_shell)
    monkeypatch.setattr(
        runtime,
        "device_abis",
        lambda: ("arm64-v8a",),
    )

    package = runtime.install_package(archive_path)

    assert package == "com.example.app"
    install = next(
        command
        for command in commands
        if "install-multiple" in command
    )
    base_index = next(
        index
        for index, value in enumerate(install)
        if value.endswith("base.apk")
    )
    split_index = next(
        index
        for index, value in enumerate(install)
        if value.endswith("config.arm64_v8a.apk")
    )
    assert base_index < split_index
    assert "-r" in install
    assert "-t" in install
    assert "-g" in install

    assert shell_commands == [
        (
            "mkdir",
            "-p",
            "/sdcard/Android/obb/com.example.app",
        )
    ]
    push = next(command for command in commands if "push" in command)
    assert push[-1].endswith(
        "/Android/obb/com.example.app/"
        "main.42.com.example.app.obb"
    )


def test_install_xapk_rejects_mixed_packages_before_install(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime = _runtime(tmp_path)
    archive_path = tmp_path / "mixed.xapk"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("base.apk", b"base")
        archive.writestr("split.apk", b"split")

    install_called = False

    def fake_run(command, *, timeout, check=True):
        nonlocal install_called
        cmd = [str(item) for item in command]
        if "aapt2" in Path(cmd[0]).name.lower():
            name = Path(cmd[-1]).name
            package = (
                "com.example.one"
                if name == "base.apk"
                else "com.example.two"
            )
            split = (
                ""
                if name == "base.apk"
                else " split='config.arm64_v8a'"
            )
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=(
                    f"package: name='{package}' "
                    f"versionCode='1'{split}\n"
                ),
                stderr="",
            )
        if "install" in " ".join(cmd):
            install_called = True
        raise AssertionError(cmd)

    monkeypatch.setattr(runtime, "_run", fake_run)
    monkeypatch.setattr(
        runtime,
        "device_abis",
        lambda: ("x86_64",),
    )

    with pytest.raises(
        AndroidRuntimeError,
        match="разных package name",
    ):
        runtime.install_package(archive_path)

    assert install_called is False


def test_single_apk_keeps_single_install_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime = _runtime(tmp_path)
    apk = tmp_path / "app.apk"
    apk.write_bytes(b"apk")
    commands: list[list[str]] = []

    def fake_run(command, *, timeout, check=True):
        cmd = [str(item) for item in command]
        commands.append(cmd)
        if "aapt2" in Path(cmd[0]).name.lower():
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=(
                    "package: name='com.example.app' "
                    "versionCode='1'\n"
                ),
                stderr="",
            )
        if "install" in cmd:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="Success\n",
                stderr="",
            )
        raise AssertionError(cmd)

    monkeypatch.setattr(runtime, "_run", fake_run)
    monkeypatch.setattr(
        runtime,
        "device_abis",
        lambda: ("x86_64",),
    )

    assert runtime.install_package(apk) == "com.example.app"
    install = next(command for command in commands if "install" in command)
    assert "install-multiple" not in install


def test_install_xapk_filters_incompatible_abi_split(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime = _runtime(tmp_path)
    archive_path = tmp_path / "multi-abi.xapk"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("base.apk", b"base")
        archive.writestr("config.arm64_v8a.apk", b"arm64")
        archive.writestr("config.x86_64.apk", b"x86")

    commands: list[list[str]] = []

    def fake_run(command, *, timeout, check=True):
        cmd = [str(item) for item in command]
        commands.append(cmd)
        if "aapt2" in Path(cmd[0]).name.lower():
            name = Path(cmd[-1]).name
            if name == "base.apk":
                output = (
                    "package: name='com.example.app' "
                    "versionCode='42'\n"
                )
            elif "arm64" in name:
                output = (
                    "package: name='com.example.app' "
                    "versionCode='42' split='config.arm64_v8a'\n"
                    "native-code: 'arm64-v8a'\n"
                )
            else:
                output = (
                    "package: name='com.example.app' "
                    "versionCode='42' split='config.x86_64'\n"
                    "native-code: 'x86_64'\n"
                )
            return subprocess.CompletedProcess(
                cmd, 0, stdout=output, stderr=""
            )
        if "install-multiple" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="Success\n", stderr=""
            )
        raise AssertionError(cmd)

    monkeypatch.setattr(runtime, "_run", fake_run)
    monkeypatch.setattr(
        runtime,
        "device_abis",
        lambda: ("x86_64", "x86"),
    )

    assert runtime.install_package(archive_path) == "com.example.app"
    install = next(
        command
        for command in commands
        if "install-multiple" in command
    )
    assert any(
        value.endswith("config.x86_64.apk")
        for value in install
    )
    assert not any(
        value.endswith("config.arm64_v8a.apk")
        for value in install
    )
