from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from mobile_research.export import verify_research_zip
from mobile_research.orchestrator import (
    OrchestratorError,
    ResearchOrchestrator,
)
from mobile_research.session import SessionManager, SessionStatus


@dataclass(frozen=True)
class FakeDetails:
    serial: str = "emulator-5554"
    state: str = "device"
    kind: str = "emulator"
    android_release: str = "15"
    sdk_level: int = 35
    manufacturer: str = "Google"
    model: str = "AVD"
    abi: str = "x86_64"
    build_fingerprint: str = "test/fingerprint"
    is_root: bool = True

    def to_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


class FakeAdb:
    def __init__(self) -> None:
        self.launched: list[tuple[str, str]] = []
        self.force_stopped: list[tuple[str, str]] = []
        self.waited_for_stop: list[tuple[str, str]] = []
        self.order: list[str] = []
        self.launch_output = (
            "Status: ok\nActivity: com.example/.MainActivity\n"
        )

    def get_target_details(self, serial: str) -> FakeDetails:
        assert serial == "emulator-5554"
        return FakeDetails()

    def is_package_installed(
        self,
        serial: str,
        package_name: str,
    ) -> bool:
        return True

    def get_utc_time(self, serial: str) -> str:
        return "2026-09-13T19:00:00Z"

    def force_stop_package(
        self,
        serial: str,
        package_name: str,
    ) -> None:
        self.force_stopped.append(
            (serial, package_name)
        )
        self.order.append("force-stop")

    def wait_for_package_stopped(
        self,
        serial: str,
        package_name: str,
        *,
        timeout: float = 3.0,
    ) -> bool:
        self.waited_for_stop.append(
            (serial, package_name)
        )
        self.order.append("wait-stopped")
        return True

    def launch_package(
        self,
        serial: str,
        package_name: str,
    ) -> str:
        self.launched.append((serial, package_name))
        self.order.append("launch")
        return self.launch_output


class FakeMetadata:
    def __init__(
        self,
        adb: FakeAdb,
        session: SessionManager,
    ) -> None:
        self.session = session

    def collect(self) -> None:
        self.session.register_collector(
            "device_metadata",
            required=True,
            backend="fake",
        )
        files = (
            "getprop.txt",
            "package.txt",
            "package-paths.txt",
            "system.txt",
            "clock.txt",
        )
        for filename in files:
            relative = f"01_raw/device/{filename}"
            path = self.session.paths.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("data\n", encoding="utf-8")
            self.session.register_artifact(
                kind="device_metadata",
                relative_path=relative,
                source="device_metadata",
                raw=True,
            )
        self.session.update_collector(
            "device_metadata",
            "completed",
        )


class FakePreflight:
    def to_dict(self) -> dict[str, object]:
        return {
            "root": True,
            "tcpdump_path": "tcpdump",
        }


class FakeContinuous:
    def __init__(
        self,
        name: str,
        session: SessionManager,
        *,
        fail_health: bool = False,
        order: list[str] | None = None,
    ) -> None:
        self.name = name
        self.session = session
        self.fail_health = fail_health
        self.order = order
        self.started = False
        self.stopped = False

    def start(self) -> None:
        if self.order is not None:
            self.order.append(f"start:{self.name}")
        self.session.register_collector(
            self.name,
            required=True,
            backend="fake",
        )
        self._write_evidence()
        self.session.update_collector(
            self.name,
            "running",
        )
        self.started = True

    def check_health(self) -> bool:
        if self.fail_health:
            self.session.update_collector(
                self.name,
                "failed",
                error="synthetic collector failure",
            )
            self.fail_health = False
            return False
        return True

    def stop(self, grace_period: float = 3.0) -> None:
        self.stopped = True
        state = self.session.manifest["collectors"][self.name]
        if state["status"] != "failed":
            self.session.update_collector(
                self.name,
                "completed",
            )

    def _write_evidence(self) -> None:
        if self.name == "logcat":
            relative = "01_raw/logcat/logcat.txt"
            data = b"logcat\n"
        elif self.name == "screen_recording":
            relative = "01_raw/screen/screen-0001.mp4"
            data = b"mp4"
        elif self.name == "raw_network":
            relative = "01_raw/network/traffic.pcap"
            data = b"pcap-data"
        else:
            raise AssertionError(self.name)

        path = self.session.paths.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.session.register_artifact(
            kind=self.name,
            relative_path=relative,
            source=self.name,
            raw=True,
        )


class FakeNetwork(FakeContinuous):
    def preflight(self) -> FakePreflight:
        return FakePreflight()


def make_orchestrator(
    tmp_path: Path,
    *,
    fail_logcat_health: bool = False,
) -> tuple[ResearchOrchestrator, FakeAdb]:
    adb = FakeAdb()

    def metadata_factory(
        adb_value: Any,
        session: SessionManager,
    ) -> FakeMetadata:
        return FakeMetadata(adb_value, session)

    def logcat_factory(
        adb_value: Any,
        session: SessionManager,
    ) -> FakeContinuous:
        return FakeContinuous(
            "logcat",
            session,
            fail_health=fail_logcat_health,
            order=adb.order,
        )

    def screen_factory(
        adb_value: Any,
        session: SessionManager,
        chunk_seconds: int,
    ) -> FakeContinuous:
        assert chunk_seconds == 170
        return FakeContinuous(
            "screen_recording",
            session,
            order=adb.order,
        )

    def network_factory(
        adb_value: Any,
        session: SessionManager,
    ) -> FakeNetwork:
        return FakeNetwork(
            "raw_network",
            session,
            order=adb.order,
        )

    orchestrator = ResearchOrchestrator(
        adb,  # type: ignore[arg-type]
        "emulator-5554",
        "com.example.app",
        runtime_root=tmp_path / "sessions",
        output_path=tmp_path / "result.research.zip",
        metadata_factory=metadata_factory,  # type: ignore[arg-type]
        logcat_factory=logcat_factory,  # type: ignore[arg-type]
        screen_factory=screen_factory,  # type: ignore[arg-type]
        network_factory=network_factory,  # type: ignore[arg-type]
    )
    return orchestrator, adb


def test_end_to_end_orchestrator_complete(tmp_path: Path) -> None:
    orchestrator, adb = make_orchestrator(tmp_path)

    started = orchestrator.start()

    assert started.status == "active"
    assert adb.launched == [
        ("emulator-5554", "com.example.app")
    ]
    assert orchestrator.session is not None
    assert orchestrator.session.status == SessionStatus.ACTIVE

    recorded = orchestrator.record_user_action(
        "tap",
        details={
            "start_x": 10,
            "start_y": 20,
            "end_x": 10,
            "end_y": 20,
        },
    )
    assert recorded is True

    health = orchestrator.health_check()
    assert health.healthy is True

    result = orchestrator.stop_and_export()

    assert result.session_status == "complete"
    assert Path(result.archive).is_file()
    verification = verify_research_zip(result.archive)
    assert verification.valid is True
    assert verification.session_status == "complete"

    with zipfile.ZipFile(result.archive) as archive:
        actions_text = archive.read(
            "02_normalized/user-actions.jsonl"
        ).decode("utf-8")
        timeline = json.loads(
            archive.read(
                "02_normalized/research-timeline.json"
            )
        )
    assert '"action": "tap"' in actions_text
    assert timeline["summary"]["user_actions"] == 1
    assert any(
        event.get("kind") == "user_action"
        for event in timeline["events"]
    )

    events = (
        orchestrator.session.paths.root
        / ResearchOrchestrator.EVENTS_ARTIFACT
    ).read_text(encoding="utf-8")
    assert "capture_active" in events
    assert "package_launched" in events
    assert "capture_finished" in events


def test_health_failure_finishes_partial_and_exports(
    tmp_path: Path,
) -> None:
    orchestrator, _ = make_orchestrator(
        tmp_path,
        fail_logcat_health=True,
    )
    orchestrator.start()

    health = orchestrator.health_check()
    assert health.healthy is False
    assert health.collector_health["logcat"] is False

    result = orchestrator.stop_and_export()

    assert result.session_status == "partial"
    assert result.validation_issues > 0
    assert verify_research_zip(result.archive).session_status == (
        "partial"
    )


def test_start_failure_creates_failed_research_zip(
    tmp_path: Path,
) -> None:
    adb = FakeAdb()

    class FailingNetwork(FakeNetwork):
        def preflight(self) -> FakePreflight:
            raise RuntimeError("tcpdump unavailable")

    orchestrator = ResearchOrchestrator(
        adb,  # type: ignore[arg-type]
        "emulator-5554",
        "com.example.app",
        runtime_root=tmp_path / "sessions",
        output_path=tmp_path / "failed.research.zip",
        metadata_factory=lambda a, s: FakeMetadata(a, s),  # type: ignore[arg-type]
        logcat_factory=lambda a, s: FakeContinuous("logcat", s),  # type: ignore[arg-type]
        screen_factory=lambda a, s, c: FakeContinuous(
            "screen_recording", s
        ),  # type: ignore[arg-type]
        network_factory=lambda a, s: FailingNetwork(
            "raw_network", s
        ),  # type: ignore[arg-type]
    )

    with pytest.raises(OrchestratorError) as error:
        orchestrator.start()

    assert error.value.session_root is not None
    assert error.value.archive is not None
    verification = verify_research_zip(error.value.archive)
    assert verification.session_status == "failed"



def test_clean_launch_force_stops_after_collectors_before_launch(
    tmp_path: Path,
) -> None:
    adb = FakeAdb()

    def metadata_factory(a, s):
        assert adb.force_stopped == []
        return FakeMetadata(a, s)

    orchestrator = ResearchOrchestrator(
        adb,  # type: ignore[arg-type]
        "emulator-5554",
        "com.example.app",
        runtime_root=tmp_path / "sessions-clean",
        output_path=tmp_path / "clean.research.zip",
        launch_mode="clean",
        metadata_factory=metadata_factory,
        logcat_factory=lambda a, s: FakeContinuous(
            "logcat",
            s,
            order=adb.order,
        ),
        screen_factory=lambda a, s, c: FakeContinuous(
            "screen_recording",
            s,
            order=adb.order,
        ),
        network_factory=lambda a, s: FakeNetwork(
            "raw_network",
            s,
            order=adb.order,
        ),
    )

    orchestrator.start()

    assert adb.force_stopped == [
        ("emulator-5554", "com.example.app")
    ]
    assert adb.waited_for_stop == [
        ("emulator-5554", "com.example.app")
    ]
    assert adb.launched == [
        ("emulator-5554", "com.example.app")
    ]
    assert adb.order.index("start:raw_network") < adb.order.index(
        "force-stop"
    )
    assert adb.order.index("force-stop") < adb.order.index(
        "wait-stopped"
    )
    assert adb.order.index("wait-stopped") < adb.order.index("launch")

    events = (
        orchestrator.session.paths.root
        / ResearchOrchestrator.EVENTS_ARTIFACT
    ).read_text(encoding="utf-8")
    assert events.index("capture_active") < events.index(
        "package_force_stopped"
    )
    assert events.index("package_force_stopped") < events.index(
        "package_launch_requested"
    )
    assert events.index("package_launch_requested") < events.index(
        "package_launched"
    )


def test_clean_launch_rejects_reused_activity_instance(
    tmp_path: Path,
) -> None:
    adb = FakeAdb()
    adb.launch_output = (
        "Status: ok\n"
        "Warning: Activity not started, intent has been delivered "
        "to currently running top-most instance.\n"
    )
    orchestrator = ResearchOrchestrator(
        adb,  # type: ignore[arg-type]
        "emulator-5554",
        "com.example.app",
        runtime_root=tmp_path / "sessions-reused",
        output_path=tmp_path / "reused.research.zip",
        launch_mode="clean",
        metadata_factory=lambda a, s: FakeMetadata(a, s),
        logcat_factory=lambda a, s: FakeContinuous(
            "logcat",
            s,
        ),
        screen_factory=lambda a, s, c: FakeContinuous(
            "screen_recording",
            s,
        ),
        network_factory=lambda a, s: FakeNetwork(
            "raw_network",
            s,
        ),
    )

    with pytest.raises(
        OrchestratorError,
        match="already-running activity instance",
    ):
        orchestrator.start()
