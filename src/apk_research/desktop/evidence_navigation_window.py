from __future__ import annotations

from apk_research.desktop.evidence_window import (
    EvidenceResearchMainWindow,
)


class UnifiedEvidenceMainWindow(EvidenceResearchMainWindow):
    """Final Evidence Explorer navigation fixes for v0.17.0."""

    def _open_evidence_timeline(self) -> None:
        node = self._selected_evidence_node()
        action_id = self._node_action_id(node)
        archive = str(
            getattr(self, "_evidence_archive", "")
            or ""
        )
        if not action_id or not archive:
            return
        if (
            archive
            == str(
                getattr(
                    self,
                    "_timeline_archive",
                    "",
                )
                or ""
            )
            and self._select_timeline_action(
                action_id
            )
        ):
            return
        self._pending_timeline_action_id = action_id
        self.controller._thread(
            self._load_refined_timeline,
            archive,
        )
