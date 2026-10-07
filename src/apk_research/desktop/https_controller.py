from __future__ import annotations

from apk_research.desktop.controller import DesktopController
from apk_research.https_capture import StagedHttpsCapture
from apk_research.orchestrator import ResearchOrchestrator
from apk_research.targets import AdbClient


class HttpsDesktopController(DesktopController):
    """Desktop controller that wraps the normal research run in HTTPS interception."""

    def _research_worker(self) -> None:
        orchestrator: ResearchOrchestrator | None = None
        https_capture: StagedHttpsCapture | None = None
        try:
            self._set_busy(True)
            assert self.package_name is not None
            client = AdbClient(
                self.runtime.paths.adb
            )

            self.log.emit(
                "Подготовка HTTPS-перехвата: "
                "запуск локального прокси и системного исследовательского CA."
            )
            https_capture = StagedHttpsCapture(
                client,
                self.runtime.SERIAL,
                self.package_name,
            )
            https_capture.start()
            self.log.emit(
                "HTTPS-перехват активен. "
                "Трафик эмулятора направлен через локальный прокси."
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
                "PCAP и HTTPS-перехват активны."
            )
            while not self._stop_research.wait(1.0):
                health = (
                    orchestrator.health_check()
                )
                payload = health.to_dict()
                payload["https_interception"] = (
                    https_capture.collector.check_health()
                )
                payload["healthy"] = bool(
                    payload.get("healthy")
                    and payload["https_interception"]
                )
                self.researchHealth.emit(
                    payload
                )

            https_result: dict[str, object] = {}
            try:
                https_result = https_capture.stop()
            except Exception as exc:
                message = (
                    str(exc)
                    or exc.__class__.__name__
                )
                if orchestrator.session is not None:
                    orchestrator.session.record_error(
                        "https_intercept:stop",
                        message,
                    )
                self.log.emit(
                    "HTTPS-перехват завершён с ошибкой: "
                    + message
                )

            if orchestrator.session is not None:
                https_capture.attach_to_session(
                    orchestrator.session
                )

            result = (
                orchestrator.stop_and_export()
            )
            payload = self._research_payload(result)
            payload["https_interception"] = https_result
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

            if https_capture is not None:
                try:
                    https_capture.stop()
                except Exception as cleanup_exc:
                    self.log.emit(
                        "Ошибка остановки HTTPS-перехвата: "
                        + (
                            str(cleanup_exc)
                            or cleanup_exc.__class__.__name__
                        )
                    )
                if (
                    orchestrator is not None
                    and orchestrator.session is not None
                ):
                    try:
                        https_capture.attach_to_session(
                            orchestrator.session
                        )
                    except Exception as attach_exc:
                        self.log.emit(
                            "Не удалось приложить HTTPS-доказательства: "
                            + (
                                str(attach_exc)
                                or attach_exc.__class__.__name__
                            )
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
                    "\n\napk-research остановила collectors "
                    "и сохранила аварийный Research ZIP."
                )
            self.error.emit(message)
        finally:
            if https_capture is not None:
                https_capture.cleanup()
            self._set_screen_presentation_hold(False)
            self.orchestrator = None
            self._set_busy(False)
