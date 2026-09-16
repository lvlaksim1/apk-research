from __future__ import annotations

import json
import os
import re
import statistics
import time
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from mobile_research.collectors import (
    DeviceMetadataCollector,
    LogcatCollector,
    RawNetworkCollector,
    ScreenRecordingCollector,
    SocketAttributionCollector,
)
from mobile_research.export import ExportResult, export_research_zip
from mobile_research.session import (
    SessionManager,
    SessionStatus,
    TERMINAL_STATUSES,
)
from mobile_research.targets import AdbClient, AdbError, validate_package_name
from mobile_research.timeline import USER_ACTIONS_ARTIFACT
from mobile_research.timeline_engine import build_research_timeline

Clock = Callable[[], datetime]


class CollectorLike(Protocol):
    def start(self) -> None: ...
    def check_health(self) -> bool: ...
    def stop(self, grace_period: float = 3.0) -> Any: ...


class NetworkCollectorLike(CollectorLike, Protocol):
    def preflight(self) -> Any: ...


class AttributionCollectorLike(CollectorLike, Protocol):
    def preflight(self) -> Any: ...


class MetadataCollectorLike(Protocol):
    def collect(self) -> Any: ...


MetadataFactory = Callable[
    [AdbClient, SessionManager],
    MetadataCollectorLike,
]
CollectorFactory = Callable[
    [AdbClient, SessionManager],
    CollectorLike,
]
NetworkFactory = Callable[
    [AdbClient, SessionManager],
    NetworkCollectorLike,
]
AttributionFactory = Callable[
    [AdbClient, SessionManager],
    AttributionCollectorLike,
]
ScreenFactory = Callable[
    [AdbClient, SessionManager, int],
    CollectorLike,
]
Exporter = Callable[..., ExportResult]
EventObserver = Callable[[dict[str, object]], None]


class OrchestratorError(RuntimeError):
    """Raised when an end-to-end research session cannot proceed."""

    def __init__(
        self,
        message: str,
        *,
        session_root: Path | None = None,
        archive: str | None = None,
    ) -> None:
        super().__init__(message)
        self.session_root = session_root
        self.archive = archive


@dataclass(frozen=True)
class StartResult:
    session_id: str
    session_root: str
    status: str
    package: str
    serial: str

    def to_dict(self) -> dict[str, str]:
        return {
            "session_id": self.session_id,
            "session_root": self.session_root,
            "status": self.status,
            "package": self.package,
            "serial": self.serial,
        }


@dataclass(frozen=True)
class HealthResult:
    healthy: bool
    collector_health: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        return {
            "healthy": self.healthy,
            "collector_health": dict(self.collector_health),
        }


@dataclass(frozen=True)
class StopResult:
    session_id: str
    session_root: str
    session_status: str
    archive: str
    validation_issues: int

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "session_root": self.session_root,
            "session_status": self.session_status,
            "archive": self.archive,
            "validation_issues": self.validation_issues,
        }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_user_action_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )
    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )
    return parsed.astimezone(
        timezone.utc
    )


def _launch_reused_existing_instance(output: str) -> bool:
    normalized = output.lower()
    return (
        "activity not started" in normalized
        or (
            "intent has been delivered" in normalized
            and "running" in normalized
        )
    )


def _launch_state(output: str) -> str | None:
    match = re.search(
        r"(?im)^LaunchState:\s*([A-Za-z_]+)\s*$",
        output,
    )
    return match.group(1).upper() if match else None


def _metadata_factory(
    adb: AdbClient,
    session: SessionManager,
) -> MetadataCollectorLike:
    return DeviceMetadataCollector(adb, session)


def _logcat_factory(
    adb: AdbClient,
    session: SessionManager,
) -> CollectorLike:
    return LogcatCollector(adb, session)


def _network_factory(
    adb: AdbClient,
    session: SessionManager,
) -> NetworkCollectorLike:
    return RawNetworkCollector(adb, session)


def _attribution_factory(
    adb: AdbClient,
    session: SessionManager,
) -> AttributionCollectorLike:
    return SocketAttributionCollector(adb, session)


def _screen_factory(
    adb: AdbClient,
    session: SessionManager,
    chunk_seconds: int,
) -> CollectorLike:
    return ScreenRecordingCollector(
        adb,
        session,
        chunk_seconds=chunk_seconds,
    )


class ResearchOrchestrator:
    """Coordinates one v0.1 AVD-RESEARCH session end to end."""

    EVENTS_ARTIFACT = "02_normalized/session-events.jsonl"
    USER_ACTIONS_ARTIFACT = USER_ACTIONS_ARTIFACT
    CLOCK_CALIBRATION_ARTIFACT = (
        "02_normalized/clock-calibration.json"
    )
    LAUNCH_ARTIFACT = "01_raw/device/package-launch.txt"

    def __init__(
        self,
        adb: AdbClient,
        serial: str,
        package_name: str,
        *,
        runtime_root: str | os.PathLike[str] | None = None,
        output_path: str | os.PathLike[str] | None = None,
        overwrite_output: bool = False,
        screen_chunk_seconds: int = 170,
        clock: Clock = _utc_now,
        metadata_factory: MetadataFactory = _metadata_factory,
        logcat_factory: CollectorFactory = _logcat_factory,
        screen_factory: ScreenFactory = _screen_factory,
        network_factory: NetworkFactory = _network_factory,
        attribution_factory: AttributionFactory = _attribution_factory,
        exporter: Exporter = export_research_zip,
        launch_mode: str = "continue",
        event_observer: EventObserver | None = None,
    ) -> None:
        self.adb = adb
        self.serial = serial.strip()
        self.package_name = validate_package_name(package_name)
        self.runtime_root = runtime_root
        self.output_path = output_path
        self.overwrite_output = overwrite_output
        self.screen_chunk_seconds = screen_chunk_seconds
        self.clock = clock

        self.metadata_factory = metadata_factory
        self.logcat_factory = logcat_factory
        self.screen_factory = screen_factory
        self.network_factory = network_factory
        self.attribution_factory = attribution_factory
        self.exporter = exporter
        if launch_mode not in {
            "clean",
            "continue",
        }:
            raise ValueError(
                "launch_mode must be 'clean' or 'continue'"
            )
        self.launch_mode = launch_mode
        self.event_observer = event_observer

        self.session: SessionManager | None = None
        self.logcat: CollectorLike | None = None
        self.screen: CollectorLike | None = None
        self.network: NetworkCollectorLike | None = None
        self.attribution: AttributionCollectorLike | None = None
        self._started_collectors: list[tuple[str, CollectorLike]] = []
        self._event_registered = False
        self._user_action_registered = False
        self._launch_registered = False
        self._user_action_lock = threading.Lock()
        self._user_action_sequence = 0
        self._user_actions_enabled = False
        self._clock_calibration_registered = False

    def start(self) -> StartResult:
        if self.session is not None:
            raise OrchestratorError("Research session was already created")

        try:
            details = self.adb.get_target_details(self.serial)
            if not self.adb.is_package_installed(
                self.serial,
                self.package_name,
            ):
                raise OrchestratorError(
                    f"Package {self.package_name!r} is not installed "
                    f"on target {self.serial}"
                )

            self.session = SessionManager.create(
                self.runtime_root,
                target=details.to_dict(),
                package={"name": self.package_name},
            )
            self._ensure_event_log()
            self._ensure_user_action_log()
            self._event(
                "session_created",
                target_utc=self._target_time_best_effort(),
                details={
                    "launch_mode": self.launch_mode,
                },
            )

            self.session.begin_preflight()
            self._event("preflight_started")

            metadata = self.metadata_factory(
                self.adb,
                self.session,
            )
            metadata.collect()
            self._event("device_metadata_completed")

            self.network = self.network_factory(
                self.adb,
                self.session,
            )
            network_preflight = self.network.preflight()
            self._event(
                "raw_network_preflight_completed",
                details=(
                    network_preflight.to_dict()
                    if hasattr(network_preflight, "to_dict")
                    else None
                ),
            )

            self.attribution = self.attribution_factory(
                self.adb,
                self.session,
            )
            attribution_preflight = self.attribution.preflight()
            self._event(
                "socket_attribution_preflight_completed",
                details=(
                    attribution_preflight.to_dict()
                    if hasattr(attribution_preflight, "to_dict")
                    else None
                ),
            )

            self.logcat = self.logcat_factory(
                self.adb,
                self.session,
            )
            self.screen = self.screen_factory(
                self.adb,
                self.session,
                self.screen_chunk_seconds,
            )

            self.session.mark_ready()
            self._event("preflight_completed")

            self.session.begin_start()
            self._start_collector("logcat", self.logcat)
            self._start_collector("screen_recording", self.screen)
            self._start_collector("raw_network", self.network)
            self._start_collector(
                "socket_attribution",
                self.attribution,
            )

            self.session.mark_active()
            self._event(
                "capture_active",
                target_utc=self._target_time_best_effort(),
            )
            self._calibrate_clock()

            if self.launch_mode == "clean":
                self._event(
                    "package_clean_restart_requested",
                    target_utc=self._target_time_best_effort(),
                    details={
                        "strategy": "single-adb-shell-stop-start",
                        "activity_transition_animation": "disabled",
                    },
                )

            self._event(
                "package_launch_requested",
                target_utc=self._target_time_best_effort(),
                details={"launch_mode": self.launch_mode},
            )
            if self.launch_mode == "clean":
                launch_output = self.adb.clean_launch_package(
                    self.serial,
                    self.package_name,
                )
            else:
                launch_output = self.adb.launch_package(
                    self.serial,
                    self.package_name,
                )
            self._write_launch_output(launch_output)
            if self.launch_mode == "clean":
                if _launch_reused_existing_instance(
                    launch_output
                ):
                    raise OrchestratorError(
                        "Clean launch invariant failed: Android reused "
                        "an already-running activity instance"
                    )
                launch_state = _launch_state(launch_output)
                if launch_state != "COLD":
                    raise OrchestratorError(
                        "Clean launch invariant failed: Android did not "
                        f"report a COLD launch (LaunchState={launch_state!r})"
                    )
            self._event(
                "package_launched",
                target_utc=self._target_time_best_effort(),
            )
            self._user_actions_enabled = True
            self._event(
                "user_action_capture_enabled",
                target_utc=self._target_time_best_effort(),
            )

            return StartResult(
                session_id=self.session.session_id,
                session_root=str(self.session.paths.root),
                status=self.session.status.value,
                package=self.package_name,
                serial=self.serial,
            )
        except Exception as exc:
            if isinstance(exc, OrchestratorError):
                message = str(exc)
            else:
                message = str(exc) or exc.__class__.__name__

            archive = self._abort_and_export(
                source="orchestrator:start",
                message=message,
            )
            raise OrchestratorError(
                message,
                session_root=(
                    self.session.paths.root
                    if self.session is not None
                    else None
                ),
                archive=archive,
            ) from exc

    def record_user_action(
        self,
        action: str,
        *,
        details: dict[str, object] | None = None,
        host_started_utc: str | None = None,
        host_utc: str | None = None,
    ) -> bool:
        session = self.session
        if (
            session is None
            or session.status != SessionStatus.ACTIVE
            or not self._user_actions_enabled
        ):
            return False

        normalized_action = action.strip()
        if not normalized_action:
            raise ValueError(
                "User action name cannot be empty"
            )

        ended = (
            host_utc
            or _iso_utc(self.clock())
        )
        started = (
            host_started_utc
            or ended
        )
        # Validate timestamp shape before writing it into evidence.
        _parse_user_action_utc(started)
        _parse_user_action_utc(ended)

        with self._user_action_lock:
            self._user_action_sequence += 1
            value: dict[str, object] = {
                "action_id": (
                    f"action-"
                    f"{self._user_action_sequence:06d}"
                ),
                "sequence": self._user_action_sequence,
                "action": normalized_action,
                "host_started_utc": started,
                "host_utc": ended,
            }
            if details is not None:
                value["details"] = details

            path = (
                session.paths.root
                / self.USER_ACTIONS_ARTIFACT
            )
            with path.open(
                "a",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        return True

    def _calibrate_clock(self) -> None:
        session = self._require_session()
        sampler = getattr(
            self.adb,
            "get_unix_time_ns",
            None,
        )
        if sampler is None:
            self._event(
                "clock_calibration_unavailable",
                details={
                    "reason": (
                        "ADB client has no nanosecond clock sampler"
                    )
                },
            )
            return

        samples: list[dict[str, object]] = []
        for index in range(9):
            before_utc_ns = time.time_ns()
            before_mono_ns = time.monotonic_ns()
            try:
                target_ns = int(
                    sampler(self.serial)
                )
            except Exception as exc:
                samples.append(
                    {
                        "index": index,
                        "error": (
                            str(exc)
                            or exc.__class__.__name__
                        ),
                    }
                )
                continue
            after_mono_ns = time.monotonic_ns()
            rtt_ns = max(
                0,
                after_mono_ns - before_mono_ns,
            )
            host_midpoint_ns = (
                before_utc_ns
                + rtt_ns // 2
            )
            offset_ns = (
                target_ns - host_midpoint_ns
            )
            samples.append(
                {
                    "index": index,
                    "target_unix_ns": target_ns,
                    "host_midpoint_unix_ns": (
                        host_midpoint_ns
                    ),
                    "round_trip_ns": rtt_ns,
                    "offset_ns": offset_ns,
                }
            )

        valid = [
            sample
            for sample in samples
            if "offset_ns" in sample
        ]
        if not valid:
            self._event(
                "clock_calibration_failed",
                details={
                    "samples": len(samples),
                },
            )
            return

        selected = sorted(
            valid,
            key=lambda item: int(
                item["round_trip_ns"]
            ),
        )[: min(5, len(valid))]
        offset_ns = int(
            statistics.median(
                int(item["offset_ns"])
                for item in selected
            )
        )
        median_rtt_ns = int(
            statistics.median(
                int(item["round_trip_ns"])
                for item in selected
            )
        )
        calibration = {
            "schema_version": "0.1",
            "method": "adb-ntp-midpoint",
            "sample_count": len(valid),
            "selected_count": len(selected),
            "target_minus_host_ns": offset_ns,
            "target_minus_host_seconds": (
                offset_ns / 1_000_000_000
            ),
            "median_selected_rtt_ns": (
                median_rtt_ns
            ),
            "estimated_uncertainty_ns": (
                median_rtt_ns // 2
            ),
            "samples": samples,
            "selected_indices": [
                int(item["index"])
                for item in selected
            ],
        }

        path = (
            session.paths.root
            / self.CLOCK_CALIBRATION_ARTIFACT
        )
        temporary = path.with_suffix(
            path.suffix + ".tmp"
        )
        with temporary.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            json.dump(
                calibration,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

        if not self._clock_calibration_registered:
            session.register_artifact(
                kind="clock_calibration",
                relative_path=(
                    self.CLOCK_CALIBRATION_ARTIFACT
                ),
                source="orchestrator",
                raw=False,
            )
            self._clock_calibration_registered = True

        self._event(
            "clock_calibrated",
            details={
                "method": calibration["method"],
                "sample_count": len(valid),
                "selected_count": len(selected),
                "target_minus_host_seconds": (
                    calibration[
                        "target_minus_host_seconds"
                    ]
                ),
                "estimated_uncertainty_ns": (
                    calibration[
                        "estimated_uncertainty_ns"
                    ]
                ),
            },
        )

    def health_check(self) -> HealthResult:
        session = self._require_session()
        if session.status != SessionStatus.ACTIVE:
            raise OrchestratorError(
                "Health check requires active session; current status is "
                f"{session.status.value!r}"
            )

        health: dict[str, bool] = {}
        for name, collector in self._started_collectors:
            try:
                healthy = collector.check_health()
            except Exception as exc:
                healthy = False
                session.record_error(
                    f"orchestrator:health:{name}",
                    str(exc) or exc.__class__.__name__,
                )
            health[name] = healthy

        overall = all(health.values()) if health else False
        if not overall:
            self._event(
                "collector_health_degraded",
                details={"collectors": health},
            )

        return HealthResult(
            healthy=overall,
            collector_health=health,
        )

    def stop_and_export(self) -> StopResult:
        session = self._require_session()

        if session.status == SessionStatus.ACTIVE:
            self._event(
                "stop_requested",
                target_utc=self._target_time_best_effort(),
            )
            session.begin_stop()
        elif session.status not in {
            SessionStatus.STOPPING,
            SessionStatus.FAILED,
        }:
            raise OrchestratorError(
                "Cannot stop research session from state "
                f"{session.status.value!r}"
            )

        self._stop_started_collectors()

        if session.status == SessionStatus.STOPPING:
            session.finish()

        self._event(
            "capture_finished",
            target_utc=self._target_time_best_effort(),
            details={"status": session.status.value},
        )

        build_research_timeline(session)
        export_result = self.exporter(
            session,
            self.output_path,
            overwrite=self.overwrite_output,
        )

        return StopResult(
            session_id=session.session_id,
            session_root=str(session.paths.root),
            session_status=session.status.value,
            archive=export_result.archive,
            validation_issues=len(
                export_result.validation.issues
            ),
        )

    def run_interactive(
        self,
        *,
        health_interval: float = 1.0,
        on_started: Callable[[StartResult], None] | None = None,
    ) -> StopResult:
        if health_interval <= 0:
            raise ValueError("health_interval must be positive")

        started = self.start()
        if on_started is not None:
            on_started(started)

        try:
            while True:
                time.sleep(health_interval)
                self.health_check()
        except KeyboardInterrupt:
            return self.stop_and_export()

    def _start_collector(
        self,
        name: str,
        collector: CollectorLike,
    ) -> None:
        collector.start()
        self._started_collectors.append((name, collector))
        self._event(f"{name}_started")

    def _stop_started_collectors(self) -> None:
        session = self._require_session()

        for name, collector in reversed(self._started_collectors):
            try:
                collector.stop()
                self._event(f"{name}_stopped")
            except Exception as exc:
                session.record_error(
                    f"orchestrator:stop:{name}",
                    str(exc) or exc.__class__.__name__,
                )
                self._event(
                    f"{name}_stop_failed",
                    details={
                        "error": str(exc)
                        or exc.__class__.__name__,
                    },
                )

        self._started_collectors.clear()

    def _abort_and_export(
        self,
        *,
        source: str,
        message: str,
    ) -> str | None:
        session = self.session
        if session is None:
            return None

        if session.status not in TERMINAL_STATUSES:
            try:
                session.fail(source, message)
            except Exception:
                pass

        try:
            self._stop_started_collectors()
        except Exception:
            pass

        if session.status not in TERMINAL_STATUSES:
            return None

        try:
            build_research_timeline(session)
            result = self.exporter(
                session,
                self.output_path,
                overwrite=self.overwrite_output,
            )
            return result.archive
        except Exception:
            return None

    def _ensure_event_log(self) -> None:
        session = self._require_session()
        path = session.paths.root / self.EVENTS_ARTIFACT
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)

        if not self._event_registered:
            session.register_artifact(
                kind="session_events",
                relative_path=self.EVENTS_ARTIFACT,
                source="orchestrator",
                raw=False,
            )
            self._event_registered = True

    def _ensure_user_action_log(self) -> None:
        session = self._require_session()
        path = (
            session.paths.root
            / self.USER_ACTIONS_ARTIFACT
        )
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.touch(exist_ok=True)

        if not self._user_action_registered:
            session.register_artifact(
                kind="user_actions",
                relative_path=(
                    self.USER_ACTIONS_ARTIFACT
                ),
                source="desktop-input",
                raw=False,
            )
            self._user_action_registered = True

    def _event(
        self,
        event: str,
        *,
        target_utc: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        session = self._require_session()
        self._ensure_event_log()

        value: dict[str, object] = {
            "host_utc": _iso_utc(self.clock()),
            "target_utc": target_utc,
            "event": event,
        }
        if details is not None:
            value["details"] = details

        path = session.paths.root / self.EVENTS_ARTIFACT
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        observer = self.event_observer
        if observer is not None:
            try:
                observer(dict(value))
            except Exception:
                # UI/presentation observers must never alter evidence capture.
                pass

    def _write_launch_output(self, output: str) -> None:
        session = self._require_session()
        path = session.paths.root / self.LAUNCH_ARTIFACT
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(output)
            if output and not output.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        if not self._launch_registered:
            session.register_artifact(
                kind="package_launch",
                relative_path=self.LAUNCH_ARTIFACT,
                source="orchestrator",
                raw=True,
            )
            self._launch_registered = True

    def _target_time_best_effort(self) -> str | None:
        try:
            return self.adb.get_utc_time(self.serial)
        except AdbError:
            return None

    def _require_session(self) -> SessionManager:
        if self.session is None:
            raise OrchestratorError(
                "Research session has not been created"
            )
        return self.session
