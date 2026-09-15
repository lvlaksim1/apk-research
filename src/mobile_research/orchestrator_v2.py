from __future__ import annotations

from mobile_research.orchestrator import (
    OrchestratorError,
    ResearchOrchestrator,
    StopResult,
)
from mobile_research.session import SessionStatus
from mobile_research.timeline_engine import build_research_timeline


class TimelineResearchOrchestrator(ResearchOrchestrator):
    """Research orchestrator using the v0.9.1 timeline engine."""

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
