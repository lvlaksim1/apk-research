from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mobile_research.collectors import (
    DeviceMetadataCollector,
    MetadataCollectorError,
)
from mobile_research.session import SessionManager


class TestClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


class FakeAdb:
    def __init__(self) -> None:
        self.optional_failures: set[str] = set()
        self.installed = True
        self.remote_dirs: list[str] = []
        self.removed: list[str] = []
        self.captured_commands: list[tuple[str, ...]] = []
        self.capture_failures: set[tuple[str, ...]] = set()
        self.shell_commands: list[tuple[str, ...]] = []
        self.package_dump = (
            "Packages:\n"
            "  Package [com.example.app]\n"
            "    versionCode=123 minSdk=28 targetSdk=35\n"
            "    versionName=1.2.3\n"
            "    firstInstallTime=2026-09-13 17:00:00\n"
            "    lastUpdateTime=2026-09-13 17:30:00\n"
        )

    def ensure_ready(self, serial: str) -> None:
        assert serial == "emulator-5554"

    def is_package_installed(self, serial: str, package_name: str) -> bool:
        assert serial == "emulator-5554"
        assert package_name == "com.example.app"
        return self.installed

    def get_utc_time(self, serial: str) -> str:
        return "2026-09-13T18:00:00Z"

    def get_all_properties(self, serial: str) -> str:
        return (
            "[ro.build.version.release]: [15]\n"
            "[ro.build.version.sdk]: [35]\n"
            "[ro.product.manufacturer]: [Google]\n"
            "[ro.product.model]: [sdk_gphone64_x86_64]\n"
            "[ro.product.cpu.abi]: [x86_64]\n"
            "[ro.build.fingerprint]: [example/fingerprint]\n"
        )

    def get_package_paths(self, serial: str, package_name: str) -> str:
        return "package:/data/app/example/base.apk\n"

    def make_remote_directory(
        self,
        serial: str,
        remote_path: str,
    ) -> None:
        self.remote_dirs.append(remote_path)

    def capture_shell_output_to_file(
        self,
        serial: str,
        remote_path: str,
        *arguments: str,
        timeout: float = 60.0,
    ) -> None:
        command = tuple(arguments)
        self.captured_commands.append(command)
        if command in self.capture_failures:
            from mobile_research.targets import AdbError

            raise AdbError(
                "simulated package dump timeout: "
                + " ".join(command)
            )

    def pull_file(
        self,
        serial: str,
        remote_path: str,
        local_path: Path,
        *,
        timeout: float = 120.0,
    ) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(
            self.package_dump,
            encoding="utf-8",
        )

    def remove_remote_file(
        self,
        serial: str,
        remote_path: str,
    ) -> None:
        self.removed.append(remote_path)

    def shell_output(self, serial: str, *arguments: str, timeout: float = 10.0) -> str:
        self.shell_commands.append(tuple(arguments))
        label = " ".join(arguments)
        if arguments and arguments[0] in self.optional_failures:
            from mobile_research.targets import AdbError

            raise AdbError(f"optional failure: {label}")
        if arguments[:5] == (
            "cmd",
            "package",
            "list",
            "packages",
            "--show-versioncode",
        ):
            return "package:com.example.app versionCode:123\n"
        return f"{label} output\n"


def create_session(tmp_path: Path) -> SessionManager:
    return SessionManager.create(
        tmp_path,
        target={
            "serial": "emulator-5554",
            "kind": "emulator",
        },
        package={"name": "com.example.app"},
        clock=TestClock(),
        session_id_factory=lambda: "metadata-session",
    )


def test_metadata_collector_writes_raw_and_normalized_files(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    collector = DeviceMetadataCollector(
        FakeAdb(),
        session,
        clock=TestClock(),
    )

    result = collector.collect()

    assert result.status == "completed"
    assert len(result.raw_artifacts) == 6

    for relative_path in result.raw_artifacts:
        assert (session.paths.root / relative_path).is_file()

    normalized_path = session.paths.root / result.normalized_artifact
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))

    assert normalized["target"]["android_release"] == "15"
    assert normalized["target"]["sdk_level"] == "35"
    assert normalized["package"]["version_name"] == "1.2.3"
    assert normalized["package"]["version_code"] == "123"
    assert normalized["package"]["paths"] == [
        "/data/app/example/base.apk"
    ]
    assert (
        "cmd",
        "package",
        "dump",
        "com.example.app",
    ) in collector.adb.captured_commands
    assert collector.adb.remote_dirs == [
        "/data/local/tmp/mobile-research/metadata-session"
    ]

    manifest = session.manifest
    state = manifest["collectors"]["device_metadata"]
    assert state["status"] == "completed"
    assert state["required"] is True
    assert state["backend"] == "adb"
    assert len(state["artifact_paths"]) == 7
    assert len(manifest["artifacts"]) == 7
    assert session.degraded is False


def test_optional_system_command_failure_does_not_fail_collector(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    adb.optional_failures.add("getenforce")

    result = DeviceMetadataCollector(
        adb,
        session,
        clock=TestClock(),
    ).collect()

    assert result.status == "completed"
    assert session.degraded is False

    normalized = json.loads(
        (session.paths.root / result.normalized_artifact).read_text(
            encoding="utf-8"
        )
    )
    assert normalized["optional_command_errors"][0]["command"] == "selinux"

    system_text = (
        session.paths.raw_device / "system.txt"
    ).read_text(encoding="utf-8")
    assert "ERROR:" in system_text


def test_missing_package_marks_collector_failed_and_degraded(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    adb.installed = False

    with pytest.raises(MetadataCollectorError, match="not installed"):
        DeviceMetadataCollector(
            adb,
            session,
            clock=TestClock(),
        ).collect()

    collector_state = session.manifest["collectors"]["device_metadata"]
    assert collector_state["status"] == "failed"
    assert session.degraded is True
    assert session.manifest["errors"][-1]["source"] == (
        "collector:device_metadata"
    )


def test_metadata_collector_cannot_run_twice_in_same_session(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    collector = DeviceMetadataCollector(adb, session, clock=TestClock())
    collector.collect()

    with pytest.raises(MetadataCollectorError, match="already registered"):
        DeviceMetadataCollector(
            adb,
            session,
            clock=TestClock(),
        ).collect()


def test_large_package_dump_uses_remote_file_transport(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    adb.package_dump = (
        "Packages:\n"
        "  Package [com.example.app]\n"
        "    versionCode=123\n"
        "    versionName=1.2.3\n"
        + ("X" * 250_000)
        + "\n"
    )

    result = DeviceMetadataCollector(
        adb,
        session,
        clock=TestClock(),
    ).collect()

    package_file = (
        session.paths.raw_device / "package.txt"
    )
    assert result.status == "completed"
    assert package_file.stat().st_size > 250_000
    assert adb.captured_commands == [
        (
            "cmd",
            "package",
            "dump",
            "com.example.app",
        )
    ]



def test_package_dump_timeout_uses_bounded_fallback(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    primary = (
        "cmd",
        "package",
        "dump",
        "com.example.app",
    )
    fallback = (
        "dumpsys",
        "-t",
        "5",
        "package",
        "com.example.app",
    )
    adb.capture_failures.add(primary)

    result = DeviceMetadataCollector(
        adb,
        session,
        clock=TestClock(),
    ).collect()

    assert result.status == "completed"
    assert adb.captured_commands == [
        primary,
        fallback,
    ]
    assert session.degraded is False

    normalized = json.loads(
        (
            session.paths.normalized_dir
            / "target.json"
        ).read_text(encoding="utf-8")
    )
    assert normalized["package_dump"]["complete"] is True
    assert (
        normalized["package_dump"]["method"]
        == "dumpsys-package"
    )


def test_package_dump_failure_degrades_but_does_not_abort_metadata(
    tmp_path: Path,
) -> None:
    session = create_session(tmp_path)
    adb = FakeAdb()
    primary = (
        "cmd",
        "package",
        "dump",
        "com.example.app",
    )
    fallback = (
        "dumpsys",
        "-t",
        "5",
        "package",
        "com.example.app",
    )
    adb.capture_failures.update(
        {
            primary,
            fallback,
        }
    )

    result = DeviceMetadataCollector(
        adb,
        session,
        clock=TestClock(),
    ).collect()

    assert result.status == "completed"
    assert session.degraded is False
    state = session.manifest["collectors"]["device_metadata"]
    assert state["status"] == "completed"
    assert session.manifest["errors"] == []

    package_text = (
        session.paths.raw_device
        / "package.txt"
    ).read_text(encoding="utf-8")
    assert package_text.startswith(
        "PACKAGE DUMP UNAVAILABLE"
    )

    normalized = json.loads(
        (
            session.paths.normalized_dir
            / "target.json"
        ).read_text(encoding="utf-8")
    )
    assert normalized["package_dump"]["complete"] is False
    assert normalized["package_dump"]["method"] == "unavailable"
    assert normalized["package_dump"]["required_for_complete_session"] is False
    assert normalized["package"]["version_code"] == "123"
    assert (
        session.paths.raw_device / "package-summary.txt"
    ).read_text(encoding="utf-8").startswith(
        "package:com.example.app versionCode:123"
    )
