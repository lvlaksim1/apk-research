from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

import pytest

from mobile_research.targets import (
    AdbClient,
    AdbError,
    parse_adb_devices,
    validate_package_name,
)


def _completed(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["adb"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_parse_adb_devices_preserves_non_ready_targets() -> None:
    output = """List of devices attached
emulator-5554 device product:sdk_gphone64_x86_64 model:sdk_gphone64_x86_64 device:emu64xa transport_id:1
R58M123456 unauthorized usb:1-2 transport_id:2
10.0.0.2:5555 offline transport_id:3
"""

    targets = parse_adb_devices(output)

    assert [target.serial for target in targets] == [
        "emulator-5554",
        "R58M123456",
        "10.0.0.2:5555",
    ]
    assert targets[0].kind == "emulator"
    assert targets[1].state == "unauthorized"
    assert targets[2].state == "offline"


def test_validate_package_name() -> None:
    assert validate_package_name("com.example.app") == "com.example.app"

    with pytest.raises(ValueError):
        validate_package_name("com.example.app;id")


def test_list_targets_detects_physical_target() -> None:
    responses = {
        ("devices", "-l"): _completed(
            "List of devices attached\n"
            "ABC123 device model:Pixel_8 transport_id:1\n"
        ),
        (
            "-s",
            "ABC123",
            "shell",
            "getprop",
            "ro.kernel.qemu",
        ): _completed("\n"),
    }

    def runner(
        arguments: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return responses[tuple(arguments)]

    client = AdbClient(Path("adb"), runner=runner)

    targets = client.list_targets()

    assert len(targets) == 1
    assert targets[0].kind == "physical"


def test_get_target_details() -> None:
    responses = {
        ("devices", "-l"): _completed(
            "List of devices attached\n"
            "emulator-5554 device model:sdk_gphone transport_id:1\n"
        ),
        (
            "-s",
            "emulator-5554",
            "shell",
            "getprop",
            "ro.build.version.sdk",
        ): _completed("35\n"),
        (
            "-s",
            "emulator-5554",
            "shell",
            "id",
            "-u",
        ): _completed("0\n"),
        (
            "-s",
            "emulator-5554",
            "shell",
            "getprop",
            "ro.kernel.qemu",
        ): _completed("1\n"),
        (
            "-s",
            "emulator-5554",
            "shell",
            "getprop",
            "ro.build.version.release",
        ): _completed("15\n"),
        (
            "-s",
            "emulator-5554",
            "shell",
            "getprop",
            "ro.product.manufacturer",
        ): _completed("Google\n"),
        (
            "-s",
            "emulator-5554",
            "shell",
            "getprop",
            "ro.product.model",
        ): _completed("sdk_gphone\n"),
        (
            "-s",
            "emulator-5554",
            "shell",
            "getprop",
            "ro.product.cpu.abi",
        ): _completed("x86_64\n"),
        (
            "-s",
            "emulator-5554",
            "shell",
            "getprop",
            "ro.build.fingerprint",
        ): _completed("example/fingerprint\n"),
    }

    def runner(
        arguments: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return responses[tuple(arguments)]

    client = AdbClient(Path("adb"), runner=runner)
    details = client.get_target_details("emulator-5554")

    assert details.kind == "emulator"
    assert details.sdk_level == 35
    assert details.android_release == "15"
    assert details.is_root is True
    assert details.abi == "x86_64"


def test_package_check_requires_ready_target() -> None:
    responses = {
        ("devices", "-l"): _completed(
            "List of devices attached\n"
            "ABC123 offline transport_id:1\n"
        ),
    }

    def runner(
        arguments: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return responses[tuple(arguments)]

    client = AdbClient(Path("adb"), runner=runner)

    with pytest.raises(AdbError, match="not ready"):
        client.is_package_installed("ABC123", "com.example.app")


def test_package_check_detects_installed_package() -> None:
    responses = {
        ("devices", "-l"): _completed(
            "List of devices attached\n"
            "emulator-5554 device model:sdk_gphone transport_id:1\n"
        ),
        (
            "-s",
            "emulator-5554",
            "shell",
            "pm",
            "path",
            "com.example.app",
        ): _completed("package:/data/app/example/base.apk\n"),
    }

    def runner(
        arguments: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return responses[tuple(arguments)]

    client = AdbClient(Path("adb"), runner=runner)

    assert client.is_package_installed(
        "emulator-5554",
        "com.example.app",
    ) is True
