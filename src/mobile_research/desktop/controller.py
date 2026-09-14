from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

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
from mobile_research.session import (
    default_runtime_root,
)
from mobile_research.targets import AdbClient


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
    screenFrame = Signal(bytes)
    operationBusy = Signal(bool)
    archiveInspection = Signal(dict)
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

    @property
    def component_state(self):
        return self.runtime.components.state()

    @property
    def session_root(self) -> Path:
        return default_runtime_root()

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

    def start_research(self) -> None:
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

    def tap(self, x: int, y: int) -> None:
        self._thread_quiet(
            self.runtime.tap,
            x,
            y,
        )

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: int,
    ) -> None:
        self._thread_quiet(
            self.runtime.swipe,
            x1,
            y1,
            x2,
            y2,
            duration,
        )

    def keyevent(self, keycode: int) -> None:
        self._thread_quiet(
            self.runtime.keyevent,
            keycode,
        )

    def text_input(self, value: str) -> None:
        self._thread_quiet(
            self.runtime.text,
            value,
        )

    def close(self) -> None:
        self._stop_research.set()
        self._stop_screen.set()
        self.runtime.stop()

    def _prepare_environment_worker(self) -> None:
        try:
            self._set_busy(True)
            self.runtime.ensure_ready(
                self._progress_callback
            )
            self._start_screen_stream()
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
            self.runtime.ensure_ready(
                self._progress_callback
            )
            self._start_screen_stream()
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

    def _start_screen_stream(self) -> None:
        if (
            self._screen_thread is not None
            and self._screen_thread.is_alive()
        ):
            return
        self._stop_screen.clear()
        self._screen_thread = threading.Thread(
            target=self._screen_worker,
            daemon=True,
            name="mobile-research-screen",
        )
        self._screen_thread.start()

    def _screen_worker(self) -> None:
        while not self._stop_screen.is_set():
            try:
                frame = (
                    self.runtime.screenshot_png()
                )
                if frame:
                    self.screenFrame.emit(frame)
            except Exception:
                pass
            self._stop_screen.wait(0.30)

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

    def _thread_quiet(
        self,
        function,
        *args,
    ) -> None:
        def worker() -> None:
            try:
                function(*args)
            except Exception:
                pass

        self._thread(worker)
