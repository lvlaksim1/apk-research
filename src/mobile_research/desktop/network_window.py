from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mobile_research.desktop.timeline_window import (
    TimelineMainWindow,
)


def _size_text(value: int) -> str:
    number = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB"):
        if number < 1024 or unit == "GB":
            return f"{number:.1f} {unit}"
        number /= 1024
    return f"{value} B"


def _time_text(value: object) -> str:
    text = str(value or "")
    if "T" in text:
        text = text.split("T", 1)[1]
    return text.replace("Z", "")[:12]


def _endpoint(ip_value: object, port_value: object) -> str:
    ip_text = str(ip_value or "—")
    if port_value in {None, ""}:
        return ip_text
    return f"{ip_text}:{port_value}"


class ResearchMainWindow(TimelineMainWindow):
    """Timeline + first-class Network Analyzer."""

    def _build_ui(self) -> None:
        super()._build_ui()
        self.network_tab_index = self.tabs.insertTab(
            2,
            self._build_network_tab(),
            "Network",
        )

    def _build_results_tab(self):
        page = super()._build_results_tab()
        layout = page.layout()
        button_layout = layout.itemAt(0).layout()
        self.results_network = QPushButton(
            "Network Analyzer"
        )
        button_layout.insertWidget(
            max(0, button_layout.count() - 1),
            self.results_network,
        )
        return page

    def _build_network_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        controls = QHBoxLayout()
        self.network_load_selected = QPushButton(
            "Открыть выбранный Research ZIP"
        )
        self.network_owner_filter = QComboBox()
        self.network_owner_filter.addItem(
            "Все соединения",
            "all",
        )
        self.network_owner_filter.addItem(
            "Исследуемое приложение",
            "app",
        )
        self.network_owner_filter.addItem(
            "Unknown",
            "unknown",
        )
        self.network_protocol_filter = QComboBox()
        self.network_protocol_filter.addItem(
            "TCP + UDP",
            "all",
        )
        self.network_protocol_filter.addItem(
            "TCP",
            "tcp",
        )
        self.network_protocol_filter.addItem(
            "UDP",
            "udp",
        )
        self.network_search = QLineEdit()
        self.network_search.setPlaceholderText(
            "Host / IP / process / DNS / SNI"
        )
        controls.addWidget(
            self.network_load_selected
        )
        controls.addSpacing(12)
        controls.addWidget(QLabel("Owner"))
        controls.addWidget(
            self.network_owner_filter
        )
        controls.addWidget(QLabel("Protocol"))
        controls.addWidget(
            self.network_protocol_filter
        )
        controls.addWidget(
            self.network_search,
            1,
        )
        layout.addLayout(controls)

        self.network_summary = QLabel(
            "Network Analyzer: выберите Research ZIP"
        )
        self.network_summary.setWordWrap(True)
        layout.addWidget(self.network_summary)

        self.network_table = QTableWidget(
            0,
            9,
        )
        self.network_table.setHorizontalHeaderLabels(
            [
                "Время",
                "Owner",
                "Host",
                "Protocol",
                "Local",
                "Remote",
                "↑",
                "↓",
                "Confidence",
            ]
        )
        self.network_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.network_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.network_table.horizontalHeader().setStretchLastSection(
            True
        )
        layout.addWidget(
            self.network_table,
            1,
        )

        self.network_details = QPlainTextEdit()
        self.network_details.setReadOnly(True)
        self.network_details.setMaximumHeight(220)
        layout.addWidget(self.network_details)
        return page

    def _connect_signals(self) -> None:
        super()._connect_signals()
        self.controller.networkReady.connect(
            self._on_network_ready
        )
        self.results_network.clicked.connect(
            self._inspect_selected_network
        )
        self.network_load_selected.clicked.connect(
            self._inspect_selected_network
        )
        self.network_owner_filter.currentIndexChanged.connect(
            self._apply_network_filters
        )
        self.network_protocol_filter.currentIndexChanged.connect(
            self._apply_network_filters
        )
        self.network_search.textChanged.connect(
            self._apply_network_filters
        )
        self.network_table.itemSelectionChanged.connect(
            self._show_network_details
        )
        self.timeline_table.cellDoubleClicked.connect(
            self._open_timeline_flow
        )
        self.network_table.cellDoubleClicked.connect(
            self._open_network_timeline
        )

    def _inspect_selected_network(self) -> None:
        path = self._selected_table_path(
            self.results_table
        )
        if not path:
            return
        self.controller.inspect_network(path)

    def _on_network_ready(
        self,
        data: dict,
    ) -> None:
        self._network_inventory = data
        self._network_archive = str(
            data.get("archive") or ""
        )
        flows = [
            item
            for item in data.get("flows") or []
            if isinstance(item, dict)
        ]
        summary = (
            data.get("summary")
            if isinstance(data.get("summary"), dict)
            else {}
        )
        package = str(
            data.get("package") or "—"
        )
        schema = str(
            data.get("schema_version") or "—"
        )
        self.network_summary.setText(
            f"{package} • schema {schema} • "
            f"{int(summary.get('flow_count') or len(flows))} flows • "
            f"app {int(summary.get('attributed_flow_count') or 0)} • "
            f"unknown {int(summary.get('unknown_flow_count') or 0)} • "
            f"non-TCP/UDP "
            f"{int(summary.get('non_tcp_udp_packet_count') or 0)} pkt • "
            f"↑ {_size_text(int(summary.get('outbound_bytes') or 0))} • "
            f"↓ {_size_text(int(summary.get('inbound_bytes') or 0))}"
        )

        self.network_table.setRowCount(
            len(flows)
        )
        for row, flow in enumerate(flows):
            owner = (
                flow.get("owner")
                if isinstance(flow.get("owner"), dict)
                else {}
            )
            confidence = str(
                owner.get("confidence") or "UNKNOWN"
            )
            owner_name = (
                str(owner.get("package") or "")
                if confidence != "UNKNOWN"
                else "Unknown"
            )
            if not owner_name:
                owner_name = "Unknown"
            sni = [
                str(value)
                for value in flow.get("tls_sni") or []
                if value
            ]
            dns = [
                str(value)
                for value in flow.get("dns_queries") or []
                if value
            ]
            host = (
                sni[0]
                if sni
                else dns[0]
                if dns
                else str(flow.get("remote_ip") or "—")
            )
            values = [
                _time_text(
                    flow.get("first_target_utc")
                ),
                owner_name,
                host,
                str(flow.get("protocol") or "").upper(),
                _endpoint(
                    flow.get("local_ip"),
                    flow.get("local_port"),
                ),
                _endpoint(
                    flow.get("remote_ip"),
                    flow.get("remote_port"),
                ),
                _size_text(
                    int(flow.get("outbound_bytes") or 0)
                ),
                _size_text(
                    int(flow.get("inbound_bytes") or 0)
                ),
                confidence,
            ]
            searchable = " ".join(
                [
                    *values,
                    json.dumps(
                        flow,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                ]
            ).lower()
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    flow,
                )
                item.setData(
                    int(Qt.ItemDataRole.UserRole) + 1,
                    searchable,
                )
                self.network_table.setItem(
                    row,
                    column,
                    item,
                )

        self.network_table.resizeColumnsToContents()
        self._apply_network_filters()
        self.tabs.setCurrentIndex(
            self.network_tab_index
        )
        pending_flow_id = str(
            getattr(
                self,
                "_pending_network_flow_id",
                "",
            )
            or ""
        )
        if pending_flow_id:
            self._pending_network_flow_id = ""
            self._select_network_flow(
                pending_flow_id
            )

    def _apply_network_filters(self) -> None:
        if not hasattr(self, "network_table"):
            return
        owner_filter = str(
            self.network_owner_filter.currentData()
            or "all"
        )
        protocol_filter = str(
            self.network_protocol_filter.currentData()
            or "all"
        )
        query = self.network_search.text().strip().lower()

        visible = 0
        for row in range(
            self.network_table.rowCount()
        ):
            first = self.network_table.item(row, 0)
            flow = (
                first.data(Qt.ItemDataRole.UserRole)
                if first is not None
                else {}
            )
            if not isinstance(flow, dict):
                flow = {}
            owner = (
                flow.get("owner")
                if isinstance(flow.get("owner"), dict)
                else {}
            )
            confidence = str(
                owner.get("confidence") or "UNKNOWN"
            )
            owner_ok = (
                owner_filter == "all"
                or (
                    owner_filter == "app"
                    and confidence != "UNKNOWN"
                )
                or (
                    owner_filter == "unknown"
                    and confidence == "UNKNOWN"
                )
            )
            protocol = str(
                flow.get("protocol") or ""
            ).lower()
            protocol_ok = (
                protocol_filter == "all"
                or protocol == protocol_filter
            )
            searchable = (
                str(
                    first.data(
                        int(Qt.ItemDataRole.UserRole) + 1
                    )
                    or ""
                )
                if first is not None
                else ""
            )
            query_ok = (
                not query
                or query in searchable
            )
            show = (
                owner_ok
                and protocol_ok
                and query_ok
            )
            self.network_table.setRowHidden(
                row,
                not show,
            )
            if show:
                visible += 1
        if hasattr(self, "_network_inventory"):
            base = self.network_summary.text().split(
                " • показано "
            )[0]
            self.network_summary.setText(
                f"{base} • показано {visible}"
            )

    def _select_network_flow(
        self,
        flow_id: str,
    ) -> bool:
        for row in range(
            self.network_table.rowCount()
        ):
            item = self.network_table.item(
                row,
                0,
            )
            flow = (
                item.data(
                    Qt.ItemDataRole.UserRole
                )
                if item is not None
                else None
            )
            if (
                isinstance(flow, dict)
                and str(
                    flow.get("flow_id") or ""
                )
                == flow_id
            ):
                self.network_table.setRowHidden(
                    row,
                    False,
                )
                self.network_table.selectRow(row)
                self.network_table.scrollToItem(
                    item
                )
                self.tabs.setCurrentIndex(
                    self.network_tab_index
                )
                return True
        return False

    def _select_timeline_action(
        self,
        action_id: str,
    ) -> bool:
        for row in range(
            self.timeline_table.rowCount()
        ):
            item = self.timeline_table.item(
                row,
                0,
            )
            row_data = (
                item.data(
                    Qt.ItemDataRole.UserRole
                )
                if item is not None
                else None
            )
            if not isinstance(row_data, dict):
                continue
            event = row_data.get("event")
            if (
                isinstance(event, dict)
                and str(
                    event.get("action_id")
                    or ""
                )
                == action_id
            ):
                self.timeline_table.selectRow(
                    row
                )
                self.timeline_table.scrollToItem(
                    item
                )
                self.tabs.setCurrentIndex(1)
                return True
        return False

    def _open_timeline_flow(
        self,
        row: int,
        column: int,
    ) -> None:
        del column
        item = self.timeline_table.item(
            row,
            0,
        )
        row_data = (
            item.data(Qt.ItemDataRole.UserRole)
            if item is not None
            else None
        )
        if not isinstance(row_data, dict):
            return
        flow_ids = [
            str(value)
            for value in (
                row_data.get("flow_ids")
                or []
            )
            if value
        ]
        if not flow_ids:
            return
        flow_id = flow_ids[0]
        archive = str(
            row_data.get("archive") or ""
        )
        if (
            archive
            and archive
            == str(
                getattr(
                    self,
                    "_network_archive",
                    "",
                )
                or ""
            )
            and self._select_network_flow(
                flow_id
            )
        ):
            return
        if not archive:
            return
        self._pending_network_flow_id = (
            flow_id
        )
        self.controller.inspect_network(
            archive
        )

    def _open_network_timeline(
        self,
        row: int,
        column: int,
    ) -> None:
        del column
        item = self.network_table.item(
            row,
            0,
        )
        flow = (
            item.data(Qt.ItemDataRole.UserRole)
            if item is not None
            else None
        )
        if not isinstance(flow, dict):
            return
        action_ids = [
            str(value)
            for value in (
                flow.get(
                    "correlated_action_ids"
                )
                or []
            )
            if value
        ]
        if not action_ids:
            return
        action_id = action_ids[0]
        archive = str(
            getattr(
                self,
                "_network_archive",
                "",
            )
            or ""
        )
        if (
            archive
            and archive
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
        if not archive:
            return
        self._pending_timeline_action_id = (
            action_id
        )
        self.controller._thread(
            self._load_refined_timeline,
            archive,
        )

    def _on_timeline_ready(
        self,
        data: dict,
    ) -> None:
        super()._on_timeline_ready(data)
        pending_action_id = str(
            getattr(
                self,
                "_pending_timeline_action_id",
                "",
            )
            or ""
        )
        if pending_action_id:
            self._pending_timeline_action_id = ""
            self._select_timeline_action(
                pending_action_id
            )

    def _show_network_details(self) -> None:
        row = self.network_table.currentRow()
        if row < 0:
            self.network_details.clear()
            return
        item = self.network_table.item(row, 0)
        flow = (
            item.data(Qt.ItemDataRole.UserRole)
            if item is not None
            else None
        )
        if not isinstance(flow, dict):
            self.network_details.clear()
            return
        self.network_details.setPlainText(
            json.dumps(
                flow,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
