from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mobile_research.desktop.network_view_model import (
    action_label,
    build_action_index,
    endpoint_text,
    flow_confidence,
    flow_host,
    flow_matches,
    flow_owner,
    format_flow_details,
    group_flows_by_host,
    size_text,
    summarize_flows,
    time_text,
)
from mobile_research.desktop.timeline_window import (
    TimelineMainWindow,
)


_ROLE_KIND = int(Qt.ItemDataRole.UserRole)
_ROLE_DATA = _ROLE_KIND + 1
_KIND_HOST = "host"
_KIND_FLOW = "flow"


def _count_text(
    value: int,
    noun: str,
) -> str:
    return f"{int(value)} {noun}"


def _confidence_text(
    summary: dict[str, Any],
) -> str:
    counts = (
        summary.get("confidence_counts")
        if isinstance(
            summary.get("confidence_counts"),
            dict,
        )
        else {}
    )
    parts = [
        f"{key} {int(counts.get(key) or 0)}"
        for key in (
            "EXACT",
            "HIGH",
            "MEDIUM",
            "UNKNOWN",
        )
        if int(counts.get(key) or 0) > 0
    ]
    return " / ".join(parts) or "UNKNOWN"


class ResearchMainWindow(TimelineMainWindow):
    """Timeline + host-oriented Network Analyzer."""

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
            "Host / IP / process / DNS / SNI / action"
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

        self.network_tree = QTreeWidget()
        self.network_table = self.network_tree
        self.network_tree.setColumnCount(9)
        self.network_tree.setHeaderLabels(
            [
                "Host / Flow",
                "Owner",
                "Protocol",
                "Local",
                "Remote",
                "↑",
                "↓",
                "Confidence",
                "Timeline",
            ]
        )
        self.network_tree.setAlternatingRowColors(
            True
        )
        self.network_tree.setUniformRowHeights(
            True
        )
        self.network_tree.setRootIsDecorated(True)
        self.network_tree.setExpandsOnDoubleClick(
            False
        )
        self.network_tree.header().setStretchLastSection(
            True
        )
        layout.addWidget(
            self.network_tree,
            1,
        )

        hint = QLabel(
            "Раскройте хост, чтобы увидеть соединения. "
            "Двойной клик по flow открывает связанное действие Timeline."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        action_row = QHBoxLayout()
        action_row.addWidget(
            QLabel("Связанные действия Timeline")
        )
        self.network_action_select = QComboBox()
        self.network_action_select.setEnabled(
            False
        )
        self.network_open_timeline = QPushButton(
            "Открыть в Timeline"
        )
        self.network_open_timeline.setEnabled(
            False
        )
        action_row.addWidget(
            self.network_action_select,
            1,
        )
        action_row.addWidget(
            self.network_open_timeline
        )
        layout.addLayout(action_row)

        self.network_details = QPlainTextEdit()
        self.network_details.setReadOnly(True)
        self.network_details.setMaximumHeight(
            280
        )
        self.network_details.setPlaceholderText(
            "Выберите хост или соединение."
        )
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
        self.network_tree.itemSelectionChanged.connect(
            self._show_network_details
        )
        self.network_tree.itemDoubleClicked.connect(
            self._open_network_item
        )
        self.network_open_timeline.clicked.connect(
            self._open_selected_network_timeline
        )
        self.timeline_table.cellDoubleClicked.connect(
            self._open_timeline_flow
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
        self._network_package = str(
            data.get("package") or ""
        )
        self._network_actions = [
            item
            for item in (
                data.get("timeline_actions")
                or []
            )
            if isinstance(item, dict)
        ]
        self._network_action_index = (
            build_action_index(
                self._network_actions
            )
        )
        flows = [
            item
            for item in data.get("flows") or []
            if isinstance(item, dict)
        ]
        self._network_groups = (
            group_flows_by_host(flows)
        )
        summary = (
            data.get("summary")
            if isinstance(
                data.get("summary"),
                dict,
            )
            else {}
        )
        schema = str(
            data.get("schema_version") or "—"
        )
        host_count = len(
            self._network_groups
        )
        self._network_summary_base = (
            f"{self._network_package or '—'}"
            f" • schema {schema}"
            f" • {host_count} hosts"
            f" • {int(summary.get('flow_count') or len(flows))} flows"
            f" • app {int(summary.get('attributed_flow_count') or 0)}"
            f" • unknown {int(summary.get('unknown_flow_count') or 0)}"
            f" • non-TCP/UDP "
            f"{int(summary.get('non_tcp_udp_packet_count') or 0)} pkt"
            f" • ↑ {size_text(int(summary.get('outbound_bytes') or 0))}"
            f" • ↓ {size_text(int(summary.get('inbound_bytes') or 0))}"
        )
        self.network_summary.setText(
            self._network_summary_base
        )

        self.network_tree.clear()
        for group in self._network_groups:
            host_item = QTreeWidgetItem()
            host_item.setData(
                0,
                _ROLE_KIND,
                _KIND_HOST,
            )
            host_item.setData(
                0,
                _ROLE_DATA,
                group,
            )
            self.network_tree.addTopLevelItem(
                host_item
            )
            self._set_host_item(
                host_item,
                group,
                group.get("flows") or [],
            )

            for flow in group.get("flows") or []:
                child = QTreeWidgetItem()
                child.setData(
                    0,
                    _ROLE_KIND,
                    _KIND_FLOW,
                )
                child.setData(
                    0,
                    _ROLE_DATA,
                    flow,
                )
                host_item.addChild(child)
                self._set_flow_item(
                    child,
                    flow,
                )

        self.network_tree.resizeColumnToContents(0)
        self.network_tree.resizeColumnToContents(1)
        self.network_tree.resizeColumnToContents(2)
        self._apply_network_filters()
        if (
            self.network_tree.topLevelItemCount()
            == 1
        ):
            self.network_tree.topLevelItem(
                0
            ).setExpanded(True)
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

    def _set_host_item(
        self,
        item: QTreeWidgetItem,
        group: dict[str, Any],
        flows: list[dict[str, Any]],
    ) -> None:
        summary = summarize_flows(flows)
        remote_ips = (
            summary.get("remote_ips") or []
        )
        remote_text = (
            str(remote_ips[0])
            if len(remote_ips) == 1
            else (
                f"{len(remote_ips)} remote IP"
                if remote_ips
                else "—"
            )
        )
        values = [
            str(group.get("host") or "unknown-host"),
            str(summary.get("owner_text") or "Unknown"),
            " + ".join(
                summary.get("protocols") or []
            )
            or "—",
            _count_text(
                summary.get("flow_count") or 0,
                "соединений",
            ),
            remote_text,
            size_text(
                int(
                    summary.get(
                        "outbound_bytes"
                    )
                    or 0
                )
            ),
            size_text(
                int(
                    summary.get(
                        "inbound_bytes"
                    )
                    or 0
                )
            ),
            _confidence_text(summary),
            _count_text(
                len(
                    summary.get(
                        "action_ids"
                    )
                    or []
                ),
                "действий",
            ),
        ]
        for column, value in enumerate(values):
            item.setText(
                column,
                value,
            )

    def _set_flow_item(
        self,
        item: QTreeWidgetItem,
        flow: dict[str, Any],
    ) -> None:
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
        label = (
            f"{time_text(flow.get('first_target_utc'))}"
            f" • {flow.get('flow_id') or 'flow'}"
        )
        values = [
            label,
            flow_owner(flow),
            str(
                flow.get("protocol") or ""
            ).upper(),
            endpoint_text(
                flow.get("local_ip"),
                flow.get("local_port"),
            ),
            endpoint_text(
                flow.get("remote_ip"),
                flow.get("remote_port"),
            ),
            size_text(
                int(
                    flow.get(
                        "outbound_bytes"
                    )
                    or 0
                )
            ),
            size_text(
                int(
                    flow.get(
                        "inbound_bytes"
                    )
                    or 0
                )
            ),
            flow_confidence(flow),
            (
                _count_text(
                    len(action_ids),
                    "действий",
                )
                if action_ids
                else "—"
            ),
        ]
        for column, value in enumerate(values):
            item.setText(
                column,
                value,
            )

    def _apply_network_filters(self) -> None:
        if not hasattr(
            self,
            "network_tree",
        ):
            return
        owner_filter = str(
            self.network_owner_filter.currentData()
            or "all"
        )
        protocol_filter = str(
            self.network_protocol_filter.currentData()
            or "all"
        )
        query = (
            self.network_search.text()
            .strip()
            .lower()
        )
        package = str(
            getattr(
                self,
                "_network_package",
                "",
            )
            or ""
        )

        visible_hosts = 0
        visible_flows = 0
        for group_index in range(
            self.network_tree.topLevelItemCount()
        ):
            host_item = (
                self.network_tree.topLevelItem(
                    group_index
                )
            )
            group = host_item.data(
                0,
                _ROLE_DATA,
            )
            if not isinstance(group, dict):
                host_item.setHidden(True)
                continue
            visible_group_flows: list[
                dict[str, Any]
            ] = []
            for child_index in range(
                host_item.childCount()
            ):
                child = host_item.child(
                    child_index
                )
                flow = child.data(
                    0,
                    _ROLE_DATA,
                )
                show = (
                    isinstance(flow, dict)
                    and flow_matches(
                        flow,
                        owner_filter=owner_filter,
                        protocol_filter=protocol_filter,
                        query=query,
                        package=package,
                    )
                )
                child.setHidden(
                    not show
                )
                if show:
                    visible_group_flows.append(
                        flow
                    )
                    visible_flows += 1

            host_item.setHidden(
                not visible_group_flows
            )
            if visible_group_flows:
                visible_hosts += 1
                self._set_host_item(
                    host_item,
                    group,
                    visible_group_flows,
                )
                if query:
                    host_item.setExpanded(
                        True
                    )

        base = str(
            getattr(
                self,
                "_network_summary_base",
                "",
            )
        )
        if base:
            self.network_summary.setText(
                f"{base} • показано "
                f"{visible_hosts} hosts / "
                f"{visible_flows} flows"
            )

    def _select_network_flow(
        self,
        flow_id: str,
    ) -> bool:
        for group_index in range(
            self.network_tree.topLevelItemCount()
        ):
            host_item = (
                self.network_tree.topLevelItem(
                    group_index
                )
            )
            for child_index in range(
                host_item.childCount()
            ):
                child = host_item.child(
                    child_index
                )
                flow = child.data(
                    0,
                    _ROLE_DATA,
                )
                if (
                    isinstance(flow, dict)
                    and str(
                        flow.get(
                            "flow_id"
                        )
                        or ""
                    )
                    == flow_id
                ):
                    host_item.setHidden(
                        False
                    )
                    child.setHidden(False)
                    host_item.setExpanded(
                        True
                    )
                    self.network_tree.setCurrentItem(
                        child
                    )
                    self.network_tree.scrollToItem(
                        child
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
            item.data(
                Qt.ItemDataRole.UserRole
            )
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

    def _open_network_item(
        self,
        item: QTreeWidgetItem,
        column: int,
    ) -> None:
        del column
        kind = str(
            item.data(
                0,
                _ROLE_KIND,
            )
            or ""
        )
        if kind == _KIND_HOST:
            item.setExpanded(
                not item.isExpanded()
            )
            return
        if kind != _KIND_FLOW:
            return
        flow = item.data(
            0,
            _ROLE_DATA,
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
        if action_ids:
            self._open_action_in_timeline(
                action_ids[0]
            )

    def _open_selected_network_timeline(
        self,
    ) -> None:
        action_id = str(
            self.network_action_select.currentData()
            or ""
        )
        if action_id:
            self._open_action_in_timeline(
                action_id
            )

    def _open_action_in_timeline(
        self,
        action_id: str,
    ) -> None:
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

    def _selected_network_data(
        self,
    ) -> tuple[
        str,
        dict[str, Any] | None,
    ]:
        item = self.network_tree.currentItem()
        if item is None:
            return "", None
        kind = str(
            item.data(
                0,
                _ROLE_KIND,
            )
            or ""
        )
        value = item.data(
            0,
            _ROLE_DATA,
        )
        return (
            kind,
            value
            if isinstance(value, dict)
            else None,
        )

    def _show_network_details(self) -> None:
        kind, value = (
            self._selected_network_data()
        )
        self.network_action_select.clear()
        self.network_action_select.setEnabled(
            False
        )
        self.network_open_timeline.setEnabled(
            False
        )
        if value is None:
            self.network_details.clear()
            return

        action_index = getattr(
            self,
            "_network_action_index",
            {},
        )
        action_ids: list[str] = []
        if kind == _KIND_FLOW:
            self.network_details.setPlainText(
                format_flow_details(
                    value,
                    action_index,
                )
            )
            action_ids = [
                str(item)
                for item in (
                    value.get(
                        "correlated_action_ids"
                    )
                    or []
                )
                if item
            ]
        elif kind == _KIND_HOST:
            flows = [
                item
                for item in (
                    value.get("flows") or []
                )
                if isinstance(
                    item,
                    dict,
                )
            ]
            summary = summarize_flows(
                flows
            )
            action_ids = [
                str(item)
                for item in (
                    summary.get(
                        "action_ids"
                    )
                    or []
                )
                if item
            ]
            confidence = (
                _confidence_text(
                    summary
                )
            )
            details = [
                f"Хост: {value.get('host') or 'unknown-host'}",
                "",
                "Сводка",
                (
                    f"  Соединений: "
                    f"{summary.get('flow_count') or 0}"
                ),
                (
                    f"  Протоколы: "
                    f"{' + '.join(summary.get('protocols') or []) or '—'}"
                ),
                (
                    f"  Owner: "
                    f"{summary.get('owner_text') or 'Unknown'}"
                ),
                (
                    f"  Confidence: {confidence}"
                ),
                (
                    f"  Трафик: "
                    f"↑ {size_text(int(summary.get('outbound_bytes') or 0))}"
                    f"  ↓ {size_text(int(summary.get('inbound_bytes') or 0))}"
                ),
                (
                    f"  Пакеты: "
                    f"{int(summary.get('packet_count') or 0)}"
                ),
                (
                    f"  Remote IP: "
                    f"{', '.join(summary.get('remote_ips') or []) or '—'}"
                ),
                "",
                "Timeline",
                (
                    f"  Связанных действий: "
                    f"{len(action_ids)}"
                ),
            ]
            for action_id in action_ids:
                details.append(
                    "  • "
                    + action_label(
                        action_id,
                        action_index,
                    )
                )
            if not action_ids:
                details.append(
                    "  В temporal window действий не найдено."
                )
            self.network_details.setPlainText(
                "\n".join(details)
            )
        else:
            self.network_details.clear()
            return

        for action_id in action_ids:
            self.network_action_select.addItem(
                action_label(
                    action_id,
                    action_index,
                ),
                action_id,
            )
        enabled = bool(action_ids)
        self.network_action_select.setEnabled(
            enabled
        )
        self.network_open_timeline.setEnabled(
            enabled
        )
