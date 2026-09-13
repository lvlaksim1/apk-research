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

    def get_package_dump(self, serial: str, package_name: str) -> str:
        return (
            "Packages:\n"
            "  Package [com.example.app]\n"
            "    versionCode=123 minSdk=28 targetSdk=35\n"
            "    versionName=1.2.3\n"
            "    firstInstallTime=2026-09-13 17:00:00\n"
            "    lastUpdateTime=2026-09-13 17:30:00\n"
        )

    def get_package_paths(self, serial: str, package_name: str) -> str:
        return "package:/data/app/example/base.apk\n"

    def shell_output(self, serial: str, *arguments: str, timeout: float = 10.0) -> str:
        label = " ".join(arguments)
        if arguments and arguments[0] in self.optional_failures:
            from mobile_research.targets import AdbError

            raise AdbError(f"optional failure: {label}")
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
    assert len(result.raw_artifacts) == 5

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

    manifest = session.manifest
    state = manifest["collectors"]["device_metadata"]
    assert state["status"] == "completed"
    assert state["required"] is True
    assert state["backend"] == "adb"
    assert len(state["artifact_paths"]) == 6
    assert len(manifest["artifacts"]) == 6
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
