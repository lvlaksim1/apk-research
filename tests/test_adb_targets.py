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


def test_metadata_snapshot_adb_commands() -> None:
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
        ): _completed("[ro.build.version.release]: [15]\n"),
        (
            "-s",
            "emulator-5554",
            "shell",
            "dumpsys",
            "package",
            "com.example.app",
        ): _completed("versionName=1.0\n"),
        (
            "-s",
            "emulator-5554",
            "shell",
            "pm",
            "path",
            "com.example.app",
        ): _completed("package:/data/app/example/base.apk\n"),
        (
            "-s",
            "emulator-5554",
            "shell",
            "date",
            "-u",
            "+%Y-%m-%dT%H:%M:%SZ",
        ): _completed("2026-09-13T18:00:00Z\n"),
    }

    def runner(
        arguments: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        key = tuple(arguments)
        if key == (
            "-s",
            "emulator-5554",
            "shell",
            "getprop",
            "ro.kernel.qemu",
        ):
            return _completed("1\n")
        return responses[key]

    client = AdbClient(Path("adb"), runner=runner)

    assert "ro.build.version.release" in client.get_all_properties(
        "emulator-5554"
    )
    assert "versionName=1.0" in client.get_package_dump(
        "emulator-5554",
        "com.example.app",
    )
    assert client.get_package_paths(
        "emulator-5554",
        "com.example.app",
    ).startswith("package:")
    assert client.get_utc_time("emulator-5554") == (
        "2026-09-13T18:00:00Z"
    )


def test_remote_screen_recording_helpers(tmp_path: Path) -> None:
    local_file = tmp_path / "screen.mp4"
    responses = {
        ("devices", "-l"): _completed(
            "List of devices attached\n"
            "emulator-5554 device model:sdk_gphone transport_id:1\n"
        ),
        (
            "-s",
            "emulator-5554",
            "shell",
            "mkdir",
            "-p",
            "/data/local/tmp/mobile-research/session-1",
        ): _completed(),
        (
            "-s",
            "emulator-5554",
            "pull",
            (
                "/data/local/tmp/mobile-research/"
                "session-1/screen-0001.mp4"
            ),
            str(local_file),
        ): _completed(),
        (
            "-s",
            "emulator-5554",
            "shell",
            "rm",
            "-f",
            (
                "/data/local/tmp/mobile-research/"
                "session-1/screen-0001.mp4"
            ),
        ): _completed(),
        (
            "-s",
            "emulator-5554",
            "shell",
            "pidof",
            "screenrecord",
        ): _completed("321 654\n"),
        (
            "-s",
            "emulator-5554",
            "shell",
            "kill",
            "-2",
            "321",
        ): _completed(),
    }

    def runner(
        arguments: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return responses[tuple(arguments)]

    client = AdbClient(Path("adb"), runner=runner)

    client.make_remote_directory(
        "emulator-5554",
        "/data/local/tmp/mobile-research/session-1",
    )
    client.pull_file(
        "emulator-5554",
        (
            "/data/local/tmp/mobile-research/"
            "session-1/screen-0001.mp4"
        ),
        local_file,
    )
    client.remove_remote_file(
        "emulator-5554",
        (
            "/data/local/tmp/mobile-research/"
            "session-1/screen-0001.mp4"
        ),
    )

    assert client.get_process_ids(
        "emulator-5554",
        "screenrecord",
    ) == [321, 654]

    client.send_signal("emulator-5554", 321, 2)


def test_remote_research_path_rejects_escape() -> None:
    client = AdbClient(Path("adb"), runner=lambda args, timeout: _completed())

    with pytest.raises(ValueError):
        client.make_remote_directory(
            "emulator-5554",
            "/data/local/tmp/mobile-research/../escape",
        )


def test_get_uid_and_probe_executable() -> None:
    responses = {
        ("devices", "-l"): _completed(
            "List of devices attached\n"
            "emulator-5554 device model:sdk_gphone transport_id:1\n"
        ),
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
            "tcpdump",
            "--version",
        ): _completed(
            stdout="tcpdump version 4.99.5\n"
        ),
    }

    def runner(
        arguments: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return responses[tuple(arguments)]

    client = AdbClient(Path("adb"), runner=runner)

    assert client.get_uid("emulator-5554") == 0
    path, version = client.probe_executable(
        "emulator-5554",
        ("tcpdump",),
    )
    assert path == "tcpdump"
    assert version == "tcpdump version 4.99.5"


def test_probe_executable_falls_back_to_next_candidate() -> None:
    responses = {
        ("devices", "-l"): _completed(
            "List of devices attached\n"
            "emulator-5554 device model:sdk_gphone transport_id:1\n"
        ),
        (
            "-s",
            "emulator-5554",
            "shell",
            "tcpdump",
            "--version",
        ): _completed(
            stderr="not found\n",
            returncode=127,
        ),
        (
            "-s",
            "emulator-5554",
            "shell",
            "/system/xbin/tcpdump",
            "--version",
        ): _completed(
            stdout="tcpdump version 4.99.5\n"
        ),
    }

    def runner(
        arguments: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return responses[tuple(arguments)]

    client = AdbClient(Path("adb"), runner=runner)

    path, version = client.probe_executable(
        "emulator-5554",
        ("tcpdump", "/system/xbin/tcpdump"),
    )
    assert path == "/system/xbin/tcpdump"
    assert version == "tcpdump version 4.99.5"


def test_resolve_and_launch_package() -> None:
    responses = {
        ("devices", "-l"): _completed(
            "List of devices attached\n"
            "emulator-5554 device model:sdk_gphone transport_id:1\n"
        ),
        (
            "-s",
            "emulator-5554",
            "shell",
            "cmd",
            "package",
            "resolve-activity",
            "--brief",
            "-a",
            "android.intent.action.MAIN",
            "-c",
            "android.intent.category.LAUNCHER",
            "com.example.app",
        ): _completed("com.example.app/.MainActivity\n"),
        (
            "-s",
            "emulator-5554",
            "shell",
            "am",
            "start",
            "-W",
            "-n",
            "com.example.app/.MainActivity",
        ): _completed(
            "Status: ok\n"
            "Activity: com.example.app/.MainActivity\n"
        ),
    }

    def runner(
        arguments: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return responses[tuple(arguments)]

    client = AdbClient(Path("adb"), runner=runner)

    assert client.resolve_launch_activity(
        "emulator-5554",
        "com.example.app",
    ) == "com.example.app/.MainActivity"

    output = client.launch_package(
        "emulator-5554",
        "com.example.app",
    )
    assert "Status: ok" in output


def test_launch_package_rejects_missing_launcher() -> None:
    responses = {
        ("devices", "-l"): _completed(
            "List of devices attached\n"
            "emulator-5554 device model:sdk_gphone transport_id:1\n"
        ),
        (
            "-s",
            "emulator-5554",
            "shell",
            "cmd",
            "package",
            "resolve-activity",
            "--brief",
            "-a",
            "android.intent.action.MAIN",
            "-c",
            "android.intent.category.LAUNCHER",
            "com.example.app",
        ): _completed("No activity found\n"),
    }

    def runner(
        arguments: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return responses[tuple(arguments)]

    client = AdbClient(Path("adb"), runner=runner)

    with pytest.raises(AdbError, match="No launcher activity"):
        client.launch_package(
            "emulator-5554",
            "com.example.app",
        )


def test_package_check_returns_false_for_missing_package() -> None:
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
            "com.example.missing",
        ): _completed(returncode=1),
    }

    def runner(
        arguments: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return responses[tuple(arguments)]

    client = AdbClient(Path("adb"), runner=runner)

    assert client.is_package_installed(
        "emulator-5554",
        "com.example.missing",
    ) is False


def test_capture_shell_output_to_remote_file() -> None:
    responses = {
        ("devices", "-l"): _completed(
            "List of devices attached\n"
            "emulator-5554 device model:sdk_gphone transport_id:1\n"
        ),
        (
            "-s",
            "emulator-5554",
            "shell",
            "sh",
            "-c",
            (
                "dumpsys package com.example.app "
                ">/data/local/tmp/mobile-research/"
                "session-1/package-dump.txt"
            ),
        ): _completed(),
    }

    def runner(
        arguments: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return responses[tuple(arguments)]

    client = AdbClient(Path("adb"), runner=runner)
    client.capture_shell_output_to_file(
        "emulator-5554",
        (
            "/data/local/tmp/mobile-research/"
            "session-1/package-dump.txt"
        ),
        "dumpsys",
        "package",
        "com.example.app",
    )


def test_capture_shell_output_rejects_remote_escape() -> None:
    client = AdbClient(
        Path("adb"),
        runner=lambda args, timeout: _completed(),
    )

    with pytest.raises(ValueError):
        client.capture_shell_output_to_file(
            "emulator-5554",
            "/data/local/tmp/mobile-research/../escape.txt",
            "dumpsys",
            "package",
            "com.example.app",
        )
