from __future__ import annotations

import json
import math
import queue
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Qt, Signal

from mobile_research.desktop.android_runtime import (
    AndroidRuntime,
)
from mobile_research.export import (
    audit_complete_research_zip,
    verify_research_zip,
)
from mobile_research.orchestrator import (
    ResearchOrchestrator,
)
from mobile_research.targets import AdbClient
from mobile_research.timeline import TIMELINE_ARTIFACT


class DesktopController(QObject):
    """Threaded controller; long operations never run on the GUI thread."""

    progress = Signal(str, object, object)
    log = Signal(str)
    error = Signal(str)
    environmentReady = Signal(dict)
    apkReady = Signal(str, str)
    researchStarted = Signal(dict)
    researchFinished = Signal(dict)
    researchHealth = Signal(dict)
    screenFrame = Signal(object)
    operationBusy = Signal(bool)
    archiveInspection = Signal(dict)
    timelineReady = Signal(dict)
    networkReady = Signal(dict)
    diagnosticsReady = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.runtime = AndroidRuntime()
        self.apk_path: Path | None = None
        self.package_name: str | None = None
        self.orchestrator: (
            ResearchOrchestrator | None
        ) = None
        self._stop_research = threading.Event()
        self._stop_screen = threading.Event()
        self._screen_thread: (
            threading.Thread | None
        ) = None
        self._research_thread: (
            threading.Thread | None
        ) = None
        self._clean_launch = True
        self._gesture_start_point: (
            tuple[int, int] | None
        ) = None
        self._gesture_started_utc: str | None = None
        self._gesture_started_ns = 0
        self._input_queue: queue.Queue[
            tuple[str, tuple] | None
        ] = queue.Queue()
        self._input_thread = threading.Thread(
            target=self._input_worker,
            daemon=True,
        )
        self._input_thread.start()
        self._frame_lock = threading.Lock()
        self._screen_ready = threading.Event()
        self._screen_error = ""
        self._input_error_reported = False
        self._latest_frame = None
        self._latest_frame_id = 0
        self._published_frame_id = 0
        self._screen_presentation_hold = False
        self._frame_timer = QTimer(self)
        self._frame_timer.setTimerType(
            Qt.TimerType.PreciseTimer
        )
        self._frame_timer.setInterval(16)
        self._frame_timer.timeout.connect(
            self._publish_latest_frame
        )
        self._frame_timer.start()

    @property
    def component_state(self):
        return self.runtime.components.state()

    def prepare_apk(self, apk_path: str) -> None:
        path = Path(
            apk_path
        ).expanduser().resolve()
        self._thread(
            self._prepare_apk_worker,
            path,
        )

    def prepare_environment(self) -> None:
        self._thread(
            self._prepare_environment_worker
        )

    def start_research(
        self,
        clean_launch: bool = True,
    ) -> None:
        self._clean_launch = bool(clean_launch)
        if (
            self.apk_path is None
            or not self.package_name
        ):
            self.error.emit(
                "Сначала выберите и подготовьте APK"
            )
            return
        if (
            self._research_thread is not None
            and self._research_thread.is_alive()
        ):
            return
        self._stop_research.clear()
        self._research_thread = threading.Thread(
            target=self._research_worker,
            daemon=True,
            name="mobile-research-session",
        )
        self._research_thread.start()

    def stop_research(self) -> None:
        self._stop_research.set()
        self.log.emit(
            "Запрошено завершение исследования…"
        )

    def inspect_archive(
        self,
        archive_path: str,
        *,
        audit: bool,
    ) -> None:
        self._thread(
            self._inspect_archive_worker,
            Path(archive_path),
            audit,
        )

    def inspect_timeline(
        self,
        archive_path: str,
    ) -> None:
        self._thread(
            self._inspect_timeline_worker,
            Path(archive_path),
        )

    def inspect_network(
        self,
        archive_path: str,
    ) -> None:
        self._thread(
            self._inspect_network_worker,
            Path(archive_path),
        )

    def refresh_diagnostics(self) -> None:
        self._thread(
            self._diagnostics_worker
        )

    def reset_android(self) -> None:
        self._thread(
            self._reset_android_worker
        )

    def repair_components(self) -> None:
        self._thread(
            self._repair_components_worker
        )

    def touch_down(self, x: int, y: int) -> None:
        self._gesture_start_point = (
            int(x),
            int(y),
        )
        self._gesture_started_utc = (
            self._host_utc_now()
        )
        self._gesture_started_ns = (
            time.monotonic_ns()
        )
        self._queue_input(
            "touch_down",
            x,
            y,
        )

    def touch_move(self, x: int, y: int) -> None:
        self._queue_input(
            "touch_move",
            x,
            y,
        )

    def touch_up(self, x: int, y: int) -> None:
        self._queue_input(
            "touch_up",
            x,
            y,
        )
        ended_utc = self._host_utc_now()
        started = (
            self._gesture_start_point
            or (int(x), int(y))
        )
        started_utc = (
            self._gesture_started_utc
            or ended_utc
        )
        duration_ms = 0
        if self._gesture_started_ns:
            duration_ms = max(
                0,
                round(
                    (
                        time.monotonic_ns()
                        - self._gesture_started_ns
                    )
                    / 1_000_000
                ),
            )
        distance = math.hypot(
            int(x) - started[0],
            int(y) - started[1],
        )
        action = (
            "tap"
            if distance <= 12
            and duration_ms <= 750
            else "swipe"
        )
        self._record_user_action(
            action,
            {
                "source": "pointer",
                "start_x": started[0],
                "start_y": started[1],
                "end_x": int(x),
                "end_y": int(y),
                "duration_ms": duration_ms,
                "distance_px": round(
                    distance,
                    2,
                ),
            },
            host_started_utc=started_utc,
            host_utc=ended_utc,
        )
        self._gesture_start_point = None
        self._gesture_started_utc = None
        self._gesture_started_ns = 0

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: int,
    ) -> None:
        timestamp = self._host_utc_now()
        self._record_user_action(
            "swipe",
            {
                "source": "wheel",
                "start_x": int(x1),
                "start_y": int(y1),
                "end_x": int(x2),
                "end_y": int(y2),
                "duration_ms": int(duration),
                "distance_px": round(
                    math.hypot(
                        int(x2) - int(x1),
                        int(y2) - int(y1),
                    ),
                    2,
                ),
            },
            host_started_utc=timestamp,
            host_utc=timestamp,
        )
        self._queue_input(
            "swipe",
            x1,
            y1,
            x2,
            y2,
            duration,
        )

    def keyevent(self, keycode: int) -> None:
        timestamp = self._host_utc_now()
        self._record_user_action(
            "key",
            {
                "keycode": int(keycode),
                "key": {
                    3: "HOME",
                    4: "BACK",
                    19: "DPAD_UP",
                    20: "DPAD_DOWN",
                    21: "DPAD_LEFT",
                    22: "DPAD_RIGHT",
                    61: "TAB",
                    66: "ENTER",
                    67: "BACKSPACE",
                }.get(
                    int(keycode),
                    f"KEYCODE_{int(keycode)}",
                ),
            },
            host_started_utc=timestamp,
            host_utc=timestamp,
        )
        self._queue_input(
            "keyevent",
            keycode,
        )

    def text_input(self, value: str) -> None:
        timestamp = self._host_utc_now()
        self._record_user_action(
            "text_input",
            {
                "text": str(value),
                "length": len(str(value)),
            },
            host_started_utc=timestamp,
            host_utc=timestamp,
        )
        self._queue_input(
            "text",
            value,
        )

    def close(self) -> None:
        self._stop_research.set()
        self._stop_screen.set()
        self._input_queue.put(None)
        self.runtime.stop()

    def _prepare_environment_worker(self) -> None:
        try:
            self._set_busy(True)
            self._input_error_reported = False
            self.runtime.ensure_ready(
                self._progress_callback,
                self._display_ready_callback,
            )
            self._start_screen_stream(
                wait_for_first_frame=True,
            )
            self.environmentReady.emit(
                self.runtime.diagnostics()
            )
            self.log.emit(
                "Research Android готов к работе"
            )
        except Exception as exc:
            self.error.emit(
                str(exc)
                or exc.__class__.__name__
            )
        finally:
            self._set_busy(False)

    def _prepare_apk_worker(
        self,
        path: Path,
    ) -> None:
        try:
            self._set_busy(True)
            self.apk_path = path
            self.package_name = None
            self._input_error_reported = False
            self.runtime.ensure_ready(
                self._progress_callback,
                self._display_ready_callback,
            )
            self._start_screen_stream(
                wait_for_first_frame=True,
            )
            package = self.runtime.install_apk(
                path,
                self._progress_callback,
            )
            self.package_name = package
            self.apkReady.emit(
                str(path),
                package,
            )
            self.environmentReady.emit(
                self.runtime.diagnostics()
            )
            self.log.emit(
                f"Готово к исследованию: {package}"
            )
        except Exception as exc:
            self.error.emit(
                str(exc)
                or exc.__class__.__name__
            )
        finally:
            self._set_busy(False)

    def _research_worker(self) -> None:
        orchestrator: ResearchOrchestrator | None = None
        try:
            self._set_busy(True)
            assert self.package_name is not None
            client = AdbClient(
                self.runtime.paths.adb
            )
            orchestrator = ResearchOrchestrator(
                client,
                self.runtime.SERIAL,
                self.package_name,
                launch_mode=(
                    "clean"
                    if self._clean_launch
                    else "continue"
                ),
                event_observer=self._on_orchestrator_event,
            )
            self.orchestrator = orchestrator
            started = orchestrator.start()
            self.researchStarted.emit(
                started.to_dict()
            )
            self.log.emit(
                "Исследование запущено. "
                "Все collectors активны."
            )
            while not self._stop_research.wait(1.0):
                health = (
                    orchestrator.health_check()
                )
                self.researchHealth.emit(
                    health.to_dict()
                )
            result = (
                orchestrator.stop_and_export()
            )
            payload = self._research_payload(result)
            self.researchFinished.emit(payload)
            self.log.emit(
                "Research ZIP создан: "
                f"{result.archive}"
            )
        except Exception as exc:
            message = (
                str(exc)
                or exc.__class__.__name__
            )
            recovered = False
            if orchestrator is not None:
                recovered = self._salvage_research(
                    orchestrator,
                    message,
                    existing_archive=getattr(
                        exc,
                        "archive",
                        None,
                    ),
                )
            if recovered:
                message += (
                    "\n\nMobile Research остановила collectors "
                    "и сохранила аварийный Research ZIP."
                )
            self.error.emit(message)
        finally:
            self._set_screen_presentation_hold(False)
            self.orchestrator = None
            self._set_busy(False)

    def _research_payload(
        self,
        result,
        *,
        recovered_error: str | None = None,
    ) -> dict:
        payload = result.to_dict()
        if recovered_error:
            payload["recovered_after_error"] = (
                recovered_error
            )
        try:
            audit = audit_complete_research_zip(
                Path(result.archive)
            )
            payload["audit"] = audit.to_dict()
        except Exception as exc:
            payload["audit_error"] = str(exc)
        try:
            timeline = self._read_timeline_archive(
                Path(result.archive)
            )
            payload["timeline_summary"] = (
                timeline.get("summary", {})
            )
        except Exception as exc:
            payload["timeline_error"] = str(exc)
        return payload

    def _salvage_research(
        self,
        orchestrator: ResearchOrchestrator,
        message: str,
        *,
        existing_archive: str | None = None,
    ) -> bool:
        session = getattr(
            orchestrator,
            "session",
            None,
        )
        status = getattr(
            getattr(session, "status", None),
            "value",
            "",
        )

        if existing_archive:
            payload = {
                "session_id": getattr(
                    session,
                    "session_id",
                    "",
                ),
                "session_root": str(
                    getattr(
                        getattr(session, "paths", None),
                        "root",
                        "",
                    )
                ),
                "session_status": status or "failed",
                "archive": existing_archive,
                "validation_issues": None,
                "recovered_after_error": message,
            }
            try:
                audit = audit_complete_research_zip(
                    Path(existing_archive)
                )
                payload["audit"] = audit.to_dict()
            except Exception as exc:
                payload["audit_error"] = str(exc)
            self.researchFinished.emit(payload)
            self.log.emit(
                "Failed Research ZIP уже сохранён: "
                f"{existing_archive}"
            )
            return True

        if status not in {
            "active",
            "stopping",
            "failed",
        }:
            return False

        try:
            result = orchestrator.stop_and_export()
            payload = self._research_payload(
                result,
                recovered_error=message,
            )
            self.researchFinished.emit(payload)
            self.log.emit(
                "Аварийное завершение сохранено: "
                f"{result.archive}"
            )
            return True
        except Exception as exc:
            self.log.emit(
                "Не удалось сохранить аварийный "
                "Research ZIP: "
                + (
                    str(exc)
                    or exc.__class__.__name__
                )
            )
            return False

    def _inspect_archive_worker(
        self,
        archive: Path,
        audit: bool,
    ) -> None:
        try:
            if audit:
                result = (
                    audit_complete_research_zip(
                        archive
                    )
                )
                payload = {
                    "mode": "audit",
                    **result.to_dict(),
                }
            else:
                result = verify_research_zip(
                    archive
                )
                payload = {
                    "mode": "verify",
                    **result.to_dict(),
                }
            self.archiveInspection.emit(
                payload
            )
        except Exception as exc:
            self.error.emit(
                str(exc)
                or exc.__class__.__name__
            )

    def _inspect_timeline_worker(
        self,
        archive: Path,
    ) -> None:
        try:
            timeline = self._read_timeline_archive(
                archive
            )
            self.timelineReady.emit(
                {
                    "mode": "timeline",
                    **timeline,
                }
            )
        except Exception as exc:
            self.error.emit(
                str(exc)
                or exc.__class__.__name__
            )

    @staticmethod
    def _read_timeline_archive(
        archive: Path,
    ) -> dict:
        with zipfile.ZipFile(
            archive
        ) as handle:
            value = json.loads(
                handle.read(
                    TIMELINE_ARTIFACT
                ).decode("utf-8")
            )
        if not isinstance(value, dict):
            raise ValueError(
                "Research Timeline имеет неверный формат"
            )
        return value

    def _inspect_network_worker(
        self,
        archive: Path,
    ) -> None:
        try:
            timeline_actions: list[dict] = []
            timeline_schema = ""
            with zipfile.ZipFile(archive) as handle:
                value = json.loads(
                    handle.read(
                        "02_normalized/network-flows.json"
                    ).decode("utf-8")
                )
                try:
                    timeline = json.loads(
                        handle.read(
                            TIMELINE_ARTIFACT
                        ).decode("utf-8")
                    )
                except KeyError:
                    timeline = {}
                if isinstance(timeline, dict):
                    timeline_schema = str(
                        timeline.get(
                            "schema_version"
                        )
                        or ""
                    )
                    timeline_actions = [
                        item
                        for item in (
                            timeline.get(
                                "user_actions"
                            )
                            or []
                        )
                        if isinstance(
                            item,
                            dict,
                        )
                    ]
            if not isinstance(value, dict):
                raise ValueError(
                    "Network inventory имеет неверный формат"
                )
            self.networkReady.emit(
                {
                    "mode": "network",
                    "archive": str(archive),
                    "timeline_schema_version": (
                        timeline_schema
                    ),
                    "timeline_actions": (
                        timeline_actions
                    ),
                    **value,
                }
            )
        except KeyError:
            self.error.emit(
                "В Research ZIP нет network-flows.json"
            )
        except Exception as exc:
            self.error.emit(
                str(exc)
                or exc.__class__.__name__
            )

    def _diagnostics_worker(self) -> None:
        try:
            data = self.runtime.diagnostics()
            if self.runtime.paths.adb.is_file():
                try:
                    client = AdbClient(
                        self.runtime.paths.adb
                    )
                    data["targets"] = [
                        target.to_dict()
                        for target in (
                            client.list_targets()
                        )
                    ]
                    if data.get("device_online"):
                        data["target_info"] = (
                            client.get_target_details(
                                self.runtime.SERIAL
                            ).to_dict()
                        )
                except Exception as exc:
                    data["adb_error"] = str(exc)
            self.diagnosticsReady.emit(
                data
            )
        except Exception as exc:
            self.error.emit(
                str(exc)
                or exc.__class__.__name__
            )

    def _reset_android_worker(self) -> None:
        try:
            self._set_busy(True)
            self._stop_screen.set()
            self.runtime.reset_userdata()
            self.log.emit(
                "Android userdata очищены. "
                "Следующий запуск будет чистым."
            )
            self.environmentReady.emit(
                self.runtime.diagnostics()
            )
        except Exception as exc:
            self.error.emit(
                str(exc)
                or exc.__class__.__name__
            )
        finally:
            self._set_busy(False)

    def _repair_components_worker(self) -> None:
        try:
            self._set_busy(True)
            self._stop_screen.set()
            self.runtime.stop()
            self.runtime.components.remove_all()
            self.package_name = None
            self.log.emit(
                "Android-компоненты удалены. "
                "При следующей подготовке Mobile Research "
                "загрузит их заново."
            )
            self.environmentReady.emit(
                self.runtime.diagnostics()
            )
        except Exception as exc:
            self.error.emit(
                str(exc)
                or exc.__class__.__name__
            )
        finally:
            self._set_busy(False)

    def _start_screen_stream(
        self,
        *,
        wait_for_first_frame: bool = False,
    ) -> None:
        if (
            self._screen_thread is not None
            and self._screen_thread.is_alive()
        ):
            if wait_for_first_frame:
                self._wait_for_first_frame()
            return

        self._stop_screen.clear()
        self._screen_ready.clear()
        self._screen_error = ""
        self._screen_thread = threading.Thread(
            target=self._screen_worker,
            daemon=True,
            name="mobile-research-screen",
        )
        self._screen_thread.start()
        if wait_for_first_frame:
            self._wait_for_first_frame()

    def _wait_for_first_frame(self) -> None:
        if not self._screen_ready.wait(15.0):
            raise RuntimeError(
                "Обязательный gRPC/MMAP framebuffer "
                "не выдал первый кадр за 15 секунд "
                "после завершения подготовки Android"
            )
        if self._screen_error:
            raise RuntimeError(
                self._screen_error
            )

    def _screen_worker(self) -> None:
        first_frame = False
        try:
            for frame in self.runtime.screen_frames(
                self._stop_screen,
                width=405,
                height=720,
            ):
                if self._stop_screen.is_set():
                    break
                with self._frame_lock:
                    self._latest_frame = frame
                    self._latest_frame_id += 1
                if not first_frame:
                    first_frame = True
                    self._screen_ready.set()
        except Exception as exc:
            if self._stop_screen.is_set():
                return
            message = (
                "Обязательный gRPC/MMAP framebuffer "
                "остановлен: "
                + (str(exc) or exc.__class__.__name__)
            )
            self._screen_error = message
            self._screen_ready.set()
            if first_frame:
                self.error.emit(message)
        finally:
            if (
                not first_frame
                and not self._stop_screen.is_set()
                and not self._screen_error
            ):
                self._screen_error = (
                    "Обязательный gRPC/MMAP framebuffer "
                    "завершился до первого кадра"
                )
                self._screen_ready.set()

    def _set_screen_presentation_hold(
        self,
        value: bool,
    ) -> bool:
        with self._frame_lock:
            previous = self._screen_presentation_hold
            self._screen_presentation_hold = bool(value)
        return previous

    def _on_orchestrator_event(
        self,
        value: dict[str, object],
    ) -> None:
        event = str(value.get("event") or "")
        if event == "package_clean_restart_requested":
            self._set_screen_presentation_hold(True)
            self.log.emit(
                "Чистый запуск: live preview удерживает последний кадр; "
                "RAW screenrecord продолжает запись."
            )
            return
        if event == "package_launched":
            if self._set_screen_presentation_hold(False):
                self.log.emit(
                    "Чистый запуск завершён: live preview снова в реальном времени."
                )

    def _publish_latest_frame(self) -> None:
        with self._frame_lock:
            if self._screen_presentation_hold:
                return
            if (
                self._latest_frame is None
                or self._latest_frame_id
                == self._published_frame_id
            ):
                return
            frame = self._latest_frame
            self._published_frame_id = (
                self._latest_frame_id
            )
        self.screenFrame.emit(frame)

    def _display_ready_callback(self) -> None:
        # Start presentation as early as possible so boot frames can appear,
        # but do not gate startup before Android has completed boot/root setup.
        self._start_screen_stream(
            wait_for_first_frame=False,
        )

    def _progress_callback(
        self,
        message: str,
        current: int | None,
        total: int | None,
    ) -> None:
        self.progress.emit(
            message,
            current,
            total,
        )
        if current is None:
            self.log.emit(message)

    def _set_busy(self, value: bool) -> None:
        self.operationBusy.emit(value)

    def _thread(
        self,
        function,
        *args,
    ) -> None:
        thread = threading.Thread(
            target=function,
            args=args,
            daemon=True,
        )
        thread.start()

    @staticmethod
    def _host_utc_now() -> str:
        return (
            datetime.now(
                timezone.utc
            )
            .isoformat()
            .replace("+00:00", "Z")
        )

    def _record_user_action(
        self,
        action: str,
        details: dict[str, object],
        *,
        host_started_utc: str,
        host_utc: str,
    ) -> None:
        orchestrator = self.orchestrator
        if orchestrator is None:
            return
        try:
            orchestrator.record_user_action(
                action,
                details=details,
                host_started_utc=(
                    host_started_utc
                ),
                host_utc=host_utc,
            )
        except Exception as exc:
            self.log.emit(
                "Не удалось записать user action: "
                + (
                    str(exc)
                    or exc.__class__.__name__
                )
            )

    def _queue_input(
        self,
        method: str,
        *args,
    ) -> None:
        self._input_queue.put(
            (method, tuple(args))
        )

    def _input_worker(self) -> None:
        while True:
            item = self._input_queue.get()
            if item is None:
                return
            method, args = item
            try:
                function = getattr(
                    self.runtime,
                    method,
                )
                function(*args)
            except Exception as exc:
                if self._input_error_reported:
                    continue
                self._input_error_reported = True
                self.error.emit(
                    "Обязательный gRPC input transport "
                    "остановлен: "
                    + (str(exc) or exc.__class__.__name__)
                )
