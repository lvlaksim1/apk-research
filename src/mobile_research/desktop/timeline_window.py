from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from mobile_research.desktop.main_window import MainWindow
from mobile_research.timeline_reader import (
    read_refined_timeline_archive,
)


class TimelineMainWindow(MainWindow):
    """Main window with a compact timeline table."""

    def _build_results_tab(self):
        page = super()._build_results_tab()
        layout = page.layout()
        self.timeline_table = QTableWidget(0, 5)
        self.timeline_table.setHorizontalHeaderLabels(
            [
                "Время",
                "Тип",
                "Событие",
                "Network",
                "Logcat",
            ]
        )
        self.timeline_table.setVisible(False)
        layout.insertWidget(
            max(0, layout.count() - 1),
            self.timeline_table,
            2,
        )
        return page

    def _inspect_selected_timeline(
        self,
    ) -> None:
        path = self._selected_table_path(
            self.results_table
        )
        if not path:
            return
        self.controller._thread(
            self._load_refined_timeline,
            path,
        )

    def _load_refined_timeline(
        self,
        path,
    ) -> None:
        try:
            data = read_refined_timeline_archive(
                path
            )
            self.controller.timelineReady.emit(
                {
                    "mode": "timeline",
                    **data,
                }
            )
        except Exception as exc:
            self.controller.error.emit(
                str(exc)
                or exc.__class__.__name__
            )

    def _on_timeline_ready(self, data: dict) -> None:
        actions = {
            str(item.get("action_id") or ""): item
            for item in (data.get("user_actions") or [])
            if isinstance(item, dict)
        }
        events = [
            item
            for item in (data.get("events") or [])
            if isinstance(item, dict)
        ]
        self.timeline_table.setRowCount(len(events))
        for row, event in enumerate(events):
            action = actions.get(
                str(event.get("action_id") or ""),
                {},
            )
            correlation = (
                action.get("correlation")
                if isinstance(action, dict)
                else {}
            )
            if not isinstance(correlation, dict):
                correlation = {}
            network = correlation.get("network")
            if not isinstance(network, dict):
                network = {}
            logcat = correlation.get("logcat")
            if not isinstance(logcat, dict):
                logcat = {}
            time_value = str(
                event.get("target_utc")
                or event.get("host_utc")
                or ""
            )
            if "T" in time_value:
                time_value = time_value.split("T", 1)[1]
            values = [
                time_value.replace("Z", "")[:12],
                str(event.get("kind") or ""),
                str(event.get("name") or ""),
                (
                    (
                        f"{int(network.get('packet_count') or 0)} pkt"
                        f" • {correlation.get('causal_confidence', '')}"
                    ).rstrip(" •")
                    if network
                    else ""
                ),
                (
                    f"{int(logcat.get('relevant_entry_count') or 0)} relevant"
                    if logcat
                    else ""
                ),
            ]
            for column, value in enumerate(values):
                self.timeline_table.setItem(
                    row,
                    column,
                    QTableWidgetItem(value),
                )
        self.timeline_table.setVisible(True)
        self.timeline_table.resizeColumnsToContents()
        self.tabs.setCurrentIndex(1)
