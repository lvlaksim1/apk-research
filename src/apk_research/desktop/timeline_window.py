from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from apk_research.desktop.main_window import MainWindow
from apk_research.timeline_reader import (
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
                    "archive": str(path),
                    **data,
                }
            )
        except Exception as exc:
            self.controller.error.emit(
                str(exc)
                or exc.__class__.__name__
            )

    def _on_timeline_ready(self, data: dict) -> None:
        self._timeline_archive = str(
            data.get("archive") or ""
        )
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
            flow_ids = [
                str(value)
                for value in (
                    network.get("flow_ids") or []
                )
                if value
            ]
            event_flow_id = str(
                event.get("flow_id") or ""
            )
            if (
                event_flow_id
                and event_flow_id not in flow_ids
            ):
                flow_ids.insert(
                    0,
                    event_flow_id,
                )

            time_value = str(
                event.get("target_utc")
                or event.get("host_utc")
                or ""
            )
            if "T" in time_value:
                time_value = time_value.split("T", 1)[1]
            package_attribution = network.get(
                "package_attribution"
            )
            if not isinstance(
                package_attribution,
                dict,
            ):
                package_attribution = {}
            packet_counts = package_attribution.get(
                "packet_counts"
            )
            if not isinstance(packet_counts, dict):
                packet_counts = {}
            attributed_count = int(
                package_attribution.get(
                    "attributed_packet_count"
                )
                or 0
            )
            owner_breakdown = "/".join(
                str(int(packet_counts.get(key) or 0))
                for key in (
                    "EXACT",
                    "HIGH",
                    "MEDIUM",
                )
            )
            network_text = ""
            if network:
                network_text = (
                    f"{int(network.get('packet_count') or 0)} pkt"
                    + (
                        f" • {len(flow_ids)} flow"
                        if flow_ids
                        else ""
                    )
                    + (
                        f" • app {attributed_count}"
                        f" [{owner_breakdown}]"
                        if attributed_count
                        else ""
                    )
                    + (
                        f" • {correlation.get('causal_confidence', '')}"
                        if correlation.get(
                            "causal_confidence"
                        )
                        else ""
                    )
                )
            elif event_flow_id:
                network_text = event_flow_id

            values = [
                time_value.replace("Z", "")[:12],
                str(event.get("kind") or ""),
                str(event.get("name") or ""),
                network_text,
                (
                    f"{int(logcat.get('relevant_entry_count') or 0)} relevant"
                    if logcat
                    else ""
                ),
            ]
            row_data = {
                "event": event,
                "action": action,
                "correlation": correlation,
                "flow_ids": flow_ids,
                "archive": self._timeline_archive,
            }
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    row_data,
                )
                self.timeline_table.setItem(
                    row,
                    column,
                    item,
                )
        self.timeline_table.setVisible(True)
        self.timeline_table.resizeColumnsToContents()
        self.tabs.setCurrentIndex(1)
