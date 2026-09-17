from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
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

from apk_research.desktop.evidence_view_model import (
    build_evidence_model,
    format_evidence_details,
    node_search_text,
)
from apk_research.desktop.network_window import (
    ResearchMainWindow,
)
from apk_research.timeline import TIMELINE_ARTIFACT

_ROLE_NODE = int(Qt.ItemDataRole.UserRole)


class EvidenceResearchMainWindow(ResearchMainWindow):
    """Main desktop window with Unified Evidence Explorer."""

    evidenceReady = Signal(dict)

    def _build_ui(self) -> None:
        super()._build_ui()
        self.evidence_tab_index = self.tabs.insertTab(
            self.network_tab_index + 1,
            self._build_evidence_tab(),
            "Evidence",
        )

    def _build_results_tab(self):
        page = super()._build_results_tab()
        layout = page.layout()
        button_layout = layout.itemAt(0).layout()
        self.results_evidence = QPushButton(
            "Evidence Explorer"
        )
        button_layout.insertWidget(
            max(0, button_layout.count() - 1),
            self.results_evidence,
        )
        self.timeline_open_evidence = QPushButton(
            "Выбранное событие → Evidence"
        )
        self.timeline_open_evidence.setEnabled(False)
        layout.insertWidget(
            max(0, layout.count() - 1),
            self.timeline_open_evidence,
        )
        return page

    def _build_network_tab(self) -> QWidget:
        page = super()._build_network_tab()
        layout = page.layout()
        self.network_open_evidence = QPushButton(
            "Выбранный flow → Evidence"
        )
        self.network_open_evidence.setEnabled(False)
        layout.insertWidget(
            max(0, layout.count() - 1),
            self.network_open_evidence,
        )
        return page

    def _build_evidence_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        controls = QHBoxLayout()
        self.evidence_load_selected = QPushButton(
            "Открыть выбранный Research ZIP"
        )
        self.evidence_search = QLineEdit()
        self.evidence_search.setPlaceholderText(
            "Action / host / flow / process / PID / inode / IP / protocol"
        )
        controls.addWidget(self.evidence_load_selected)
        controls.addWidget(self.evidence_search, 1)
        layout.addLayout(controls)

        self.evidence_summary = QLabel(
            "Evidence Explorer: выберите Research ZIP"
        )
        self.evidence_summary.setWordWrap(True)
        layout.addWidget(self.evidence_summary)

        self.evidence_tree = QTreeWidget()
        self.evidence_tree.setColumnCount(3)
        self.evidence_tree.setHeaderLabels(
            [
                "Evidence path",
                "Type",
                "Provenance",
            ]
        )
        self.evidence_tree.setAlternatingRowColors(True)
        self.evidence_tree.setUniformRowHeights(True)
        self.evidence_tree.setRootIsDecorated(True)
        self.evidence_tree.header().setStretchLastSection(True)
        layout.addWidget(self.evidence_tree, 1)

        nav = QHBoxLayout()
        self.evidence_open_timeline = QPushButton(
            "Открыть в Timeline"
        )
        self.evidence_open_network = QPushButton(
            "Открыть flow в Network"
        )
        self.evidence_open_timeline.setEnabled(False)
        self.evidence_open_network.setEnabled(False)
        nav.addWidget(self.evidence_open_timeline)
        nav.addWidget(self.evidence_open_network)
        nav.addStretch(1)
        layout.addLayout(nav)

        self.evidence_details = QPlainTextEdit()
        self.evidence_details.setReadOnly(True)
        self.evidence_details.setMaximumHeight(270)
        self.evidence_details.setPlaceholderText(
            "Выберите узел evidence graph."
        )
        layout.addWidget(self.evidence_details)

        note = QLabel(
            "Explorer не создаёт новую forensic-истину: Action↔Flow остаётся temporal-only, "
            "а Raw locator указывает обратно на исходные PCAP/socket artifacts Research ZIP."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        return page

    def _connect_signals(self) -> None:
        super()._connect_signals()
        self.evidenceReady.connect(self._on_evidence_ready)
        self.results_evidence.clicked.connect(
            self._inspect_selected_evidence
        )
        self.evidence_load_selected.clicked.connect(
            self._inspect_selected_evidence
        )
        self.evidence_search.textChanged.connect(
            self._apply_evidence_filter
        )
        self.evidence_tree.itemSelectionChanged.connect(
            self._show_evidence_details
        )
        self.evidence_tree.itemDoubleClicked.connect(
            self._open_evidence_item
        )
        self.evidence_open_timeline.clicked.connect(
            self._open_evidence_timeline
        )
        self.evidence_open_network.clicked.connect(
            self._open_evidence_network
        )
        self.network_tree.itemSelectionChanged.connect(
            self._update_network_evidence_button
        )
        self.network_open_evidence.clicked.connect(
            self._open_network_selection_in_evidence
        )
        self.timeline_table.itemSelectionChanged.connect(
            self._update_timeline_evidence_button
        )
        self.timeline_open_evidence.clicked.connect(
            self._open_timeline_selection_in_evidence
        )

    def _inspect_selected_evidence(self) -> None:
        path = self._selected_table_path(self.results_table)
        if not path:
            return
        self._load_evidence_for_archive(str(path))

    def _load_evidence_for_archive(
        self,
        archive: str,
        *,
        pending_flow_id: str = "",
        pending_action_id: str = "",
    ) -> None:
        self._pending_evidence_flow_id = pending_flow_id
        self._pending_evidence_action_id = pending_action_id
        if (
            str(getattr(self, "_evidence_archive", "") or "")
            == str(archive)
            and hasattr(self, "_evidence_model")
        ):
            self.tabs.setCurrentIndex(self.evidence_tab_index)
            self._select_pending_evidence()
            return
        self.controller._thread(
            self._load_evidence_archive,
            Path(archive),
        )

    def _load_evidence_archive(self, archive: Path) -> None:
        try:
            with zipfile.ZipFile(archive) as handle:
                network = json.loads(
                    handle.read(
                        "02_normalized/network-flows.json"
                    ).decode("utf-8")
                )
                timeline = json.loads(
                    handle.read(TIMELINE_ARTIFACT).decode("utf-8")
                )
                try:
                    socket_attribution = json.loads(
                        handle.read(
                            "02_normalized/socket-attribution.json"
                        ).decode("utf-8")
                    )
                except KeyError:
                    socket_attribution = {}
            if not isinstance(network, dict):
                raise ValueError(
                    "Network inventory имеет неверный формат"
                )
            if not isinstance(timeline, dict):
                raise ValueError(
                    "Research Timeline имеет неверный формат"
                )
            flows = [
                item
                for item in network.get("flows") or []
                if isinstance(item, dict)
            ]
            actions = [
                item
                for item in timeline.get("user_actions") or []
                if isinstance(item, dict)
            ]
            model = build_evidence_model(
                flows,
                actions,
                package=str(network.get("package") or ""),
            )
            self.evidenceReady.emit(
                {
                    "archive": str(archive),
                    "network_schema_version": str(
                        network.get("schema_version") or ""
                    ),
                    "timeline_schema_version": str(
                        timeline.get("schema_version") or ""
                    ),
                    "socket_summary": (
                        socket_attribution.get("summary")
                        if isinstance(socket_attribution, dict)
                        else {}
                    )
                    or {},
                    "model": model,
                }
            )
        except KeyError as exc:
            self.controller.error.emit(
                f"В Research ZIP нет обязательного evidence artifact: {exc}"
            )
        except Exception as exc:
            self.controller.error.emit(
                str(exc) or exc.__class__.__name__
            )

    def _on_evidence_ready(self, data: dict) -> None:
        self._evidence_archive = str(data.get("archive") or "")
        model = data.get("model")
        if not isinstance(model, dict):
            model = {}
        self._evidence_model = model
        self.evidence_tree.clear()

        actions_root = self._tree_item(
            {
                "kind": "root",
                "label": "По действиям",
            },
            "По действиям",
            "Index",
            "Timeline → Host → Flow → Process/Socket → Raw",
        )
        self.evidence_tree.addTopLevelItem(actions_root)
        for action in model.get("actions") or []:
            if isinstance(action, dict):
                self._append_action_node(actions_root, action)

        hosts_root = self._tree_item(
            {
                "kind": "root",
                "label": "По хостам",
            },
            "По хостам",
            "Reverse index",
            "Host → Flow → Action / Process/Socket / Raw",
        )
        self.evidence_tree.addTopLevelItem(hosts_root)
        for host in model.get("hosts") or []:
            if isinstance(host, dict):
                self._append_host_node(hosts_root, host, include_actions=True)

        actions_root.setExpanded(True)
        hosts_root.setExpanded(True)
        self.evidence_tree.resizeColumnToContents(0)
        self.evidence_tree.resizeColumnToContents(1)
        socket_summary = data.get("socket_summary")
        if not isinstance(socket_summary, dict):
            socket_summary = {}
        self.evidence_summary.setText(
            f"{model.get('package') or '—'}"
            f" • Network schema {data.get('network_schema_version') or '—'}"
            f" • Timeline schema {data.get('timeline_schema_version') or '—'}"
            f" • {int(model.get('action_count') or 0)} actions"
            f" • {int(model.get('host_count') or 0)} hosts"
            f" • {int(model.get('flow_count') or 0)} flows"
            f" • {int(socket_summary.get('snapshot_count') or 0)} socket snapshots"
        )
        self.tabs.setCurrentIndex(self.evidence_tab_index)
        self._apply_evidence_filter()
        self._select_pending_evidence()

    def _tree_item(
        self,
        node: dict[str, Any],
        label: str,
        kind: str,
        provenance: str,
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label, kind, provenance])
        item.setData(0, _ROLE_NODE, node)
        return item

    def _append_action_node(
        self,
        parent: QTreeWidgetItem,
        action: dict[str, Any],
    ) -> None:
        item = self._tree_item(
            action,
            str(action.get("label") or action.get("action_id") or "action"),
            "Action",
            str(action.get("correlation_type") or "temporal-only"),
        )
        parent.addChild(item)
        for host in action.get("hosts") or []:
            if isinstance(host, dict):
                self._append_host_node(item, host, include_actions=False)

    def _append_host_node(
        self,
        parent: QTreeWidgetItem,
        host: dict[str, Any],
        *,
        include_actions: bool,
    ) -> None:
        item = self._tree_item(
            host,
            str(host.get("host") or "unknown-host"),
            "Host",
            f"{int(host.get('flow_count') or 0)} normalized flow",
        )
        parent.addChild(item)
        for flow_node in host.get("flow_nodes") or []:
            if isinstance(flow_node, dict):
                self._append_flow_node(
                    item,
                    flow_node,
                    include_actions=include_actions,
                )

    def _append_flow_node(
        self,
        parent: QTreeWidgetItem,
        flow_node: dict[str, Any],
        *,
        include_actions: bool,
    ) -> None:
        flow = flow_node.get("flow")
        if not isinstance(flow, dict):
            flow = {}
        owner = flow_node.get("owner")
        if not isinstance(owner, dict):
            owner = {}
        item = self._tree_item(
            flow_node,
            str(flow_node.get("flow_id") or "flow"),
            "Flow",
            f"{str(flow.get('protocol') or '').upper()} • {str(owner.get('confidence') or 'UNKNOWN')}",
        )
        parent.addChild(item)

        if include_actions:
            action_index = (
                self._evidence_model.get("action_index")
                if isinstance(getattr(self, "_evidence_model", None), dict)
                else {}
            )
            if not isinstance(action_index, dict):
                action_index = {}
            for action_id in flow_node.get("action_ids") or []:
                action = action_index.get(str(action_id))
                action_node = {
                    "kind": "action",
                    "action_id": str(action_id),
                    "label": str(
                        next(
                            (
                                value
                                for value in flow_node.get("action_labels") or []
                                if str(action_id) in str(value)
                            ),
                            str(action_id),
                        )
                    ),
                    "action": action if isinstance(action, dict) else {},
                    "flow_ids": [str(flow_node.get("flow_id") or "")],
                    "correlation_type": "temporal-only",
                    "causal_claim": False,
                }
                item.addChild(
                    self._tree_item(
                        action_node,
                        str(action_node.get("label") or action_id),
                        "Action link",
                        "temporal-only",
                    )
                )

        for process_node in flow_node.get("process_nodes") or []:
            if not isinstance(process_node, dict):
                continue
            process_node = {
                **process_node,
                "flow_id": str(flow_node.get("flow_id") or ""),
            }
            processes = process_node.get("processes") or []
            label = (
                ", ".join(str(value) for value in processes)
                or "Socket attribution"
            )
            if process_node.get("inode") is not None:
                label += f" • inode {process_node.get('inode')}"
            process_item = self._tree_item(
                process_node,
                label,
                "Process/Socket",
                str(process_node.get("confidence") or "UNKNOWN"),
            )
            item.addChild(process_item)
            socket_locator = process_node.get("raw_locator")
            if isinstance(socket_locator, dict):
                raw_socket = {
                    "kind": "raw",
                    "flow_id": str(flow_node.get("flow_id") or ""),
                    "locator": socket_locator,
                }
                process_item.addChild(
                    self._tree_item(
                        raw_socket,
                        str(socket_locator.get("artifact") or "socket-snapshots"),
                        "Raw",
                        "socket snapshot locator",
                    )
                )

        locator = flow_node.get("raw_locator")
        if isinstance(locator, dict):
            raw_pcap = {
                "kind": "raw",
                "flow_id": str(flow_node.get("flow_id") or ""),
                "locator": locator,
            }
            item.addChild(
                self._tree_item(
                    raw_pcap,
                    str(locator.get("artifact") or "traffic.pcap"),
                    "Raw",
                    "time + canonical 5-tuple locator",
                )
            )

    def _selected_evidence_node(self) -> dict[str, Any] | None:
        items = self.evidence_tree.selectedItems()
        if not items:
            return None
        value = items[0].data(0, _ROLE_NODE)
        return value if isinstance(value, dict) else None

    @staticmethod
    def _node_flow_id(node: dict[str, Any] | None) -> str:
        if not isinstance(node, dict):
            return ""
        flow_id = str(node.get("flow_id") or "")
        if flow_id:
            return flow_id
        locator = node.get("locator")
        if isinstance(locator, dict):
            return str(locator.get("flow_id") or "")
        return ""

    @staticmethod
    def _node_action_id(node: dict[str, Any] | None) -> str:
        if not isinstance(node, dict):
            return ""
        return str(node.get("action_id") or "")

    def _show_evidence_details(self) -> None:
        node = self._selected_evidence_node()
        if node is None:
            self.evidence_details.clear()
            self.evidence_open_timeline.setEnabled(False)
            self.evidence_open_network.setEnabled(False)
            return
        self.evidence_details.setPlainText(
            format_evidence_details(node)
        )
        self.evidence_open_timeline.setEnabled(
            bool(self._node_action_id(node))
        )
        self.evidence_open_network.setEnabled(
            bool(self._node_flow_id(node))
        )

    def _open_evidence_item(
        self,
        item: QTreeWidgetItem,
        column: int,
    ) -> None:
        del column
        node = item.data(0, _ROLE_NODE)
        if not isinstance(node, dict):
            return
        if self._node_flow_id(node):
            self._open_evidence_network()
        elif self._node_action_id(node):
            self._open_evidence_timeline()

    def _open_evidence_network(self) -> None:
        node = self._selected_evidence_node()
        flow_id = self._node_flow_id(node)
        archive = str(getattr(self, "_evidence_archive", "") or "")
        if not flow_id or not archive:
            return
        if (
            archive == str(getattr(self, "_network_archive", "") or "")
            and self._select_network_flow(flow_id)
        ):
            return
        self._pending_network_flow_id = flow_id
        self.controller.inspect_network(archive)

    def _open_evidence_timeline(self) -> None:
        node = self._selected_evidence_node()
        action_id = self._node_action_id(node)
        archive = str(getattr(self, "_evidence_archive", "") or "")
        if not action_id or not archive:
            return
        self._open_action_in_timeline(action_id)

    def _apply_evidence_filter(self) -> None:
        if not hasattr(self, "evidence_tree"):
            return
        query = self.evidence_search.text().strip().lower()
        for root_index in range(self.evidence_tree.topLevelItemCount()):
            root = self.evidence_tree.topLevelItem(root_index)
            self._filter_evidence_item(root, query, is_root=True)

    def _filter_evidence_item(
        self,
        item: QTreeWidgetItem,
        query: str,
        *,
        is_root: bool = False,
    ) -> bool:
        node = item.data(0, _ROLE_NODE)
        own_match = (
            not query
            or is_root
            or (
                isinstance(node, dict)
                and query in node_search_text(node)
            )
            or query in item.text(0).lower()
            or query in item.text(1).lower()
            or query in item.text(2).lower()
        )
        child_match = False
        for index in range(item.childCount()):
            if self._filter_evidence_item(
                item.child(index),
                query,
            ):
                child_match = True
        visible = own_match or child_match
        item.setHidden(not visible)
        if query and child_match:
            item.setExpanded(True)
        return visible

    def _find_evidence_item(
        self,
        *,
        flow_id: str = "",
        action_id: str = "",
    ) -> QTreeWidgetItem | None:
        stack = [
            self.evidence_tree.topLevelItem(index)
            for index in range(self.evidence_tree.topLevelItemCount())
        ]
        while stack:
            item = stack.pop(0)
            node = item.data(0, _ROLE_NODE)
            if isinstance(node, dict):
                if flow_id and self._node_flow_id(node) == flow_id:
                    return item
                if action_id and self._node_action_id(node) == action_id:
                    return item
            stack.extend(
                item.child(index)
                for index in range(item.childCount())
            )
        return None

    def _select_pending_evidence(self) -> None:
        flow_id = str(getattr(self, "_pending_evidence_flow_id", "") or "")
        action_id = str(getattr(self, "_pending_evidence_action_id", "") or "")
        if not flow_id and not action_id:
            return
        item = self._find_evidence_item(
            flow_id=flow_id,
            action_id=action_id,
        )
        self._pending_evidence_flow_id = ""
        self._pending_evidence_action_id = ""
        if item is None:
            return
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        item.setHidden(False)
        self.evidence_tree.setCurrentItem(item)
        self.evidence_tree.scrollToItem(item)
        self.tabs.setCurrentIndex(self.evidence_tab_index)

    def _update_network_evidence_button(self) -> None:
        data = self._selected_network_data()
        flow = data[1] if data else None
        self.network_open_evidence.setEnabled(
            isinstance(flow, dict)
            and bool(flow.get("flow_id"))
        )

    def _open_network_selection_in_evidence(self) -> None:
        data = self._selected_network_data()
        if not data:
            return
        _, flow = data
        if not isinstance(flow, dict):
            return
        flow_id = str(flow.get("flow_id") or "")
        archive = str(getattr(self, "_network_archive", "") or "")
        if flow_id and archive:
            self._load_evidence_for_archive(
                archive,
                pending_flow_id=flow_id,
            )

    def _timeline_selected_row_data(self) -> dict[str, Any] | None:
        row = self.timeline_table.currentRow()
        if row < 0:
            return None
        item = self.timeline_table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, dict) else None

    def _update_timeline_evidence_button(self) -> None:
        row_data = self._timeline_selected_row_data()
        action = row_data.get("action") if isinstance(row_data, dict) else None
        action_id = (
            str(action.get("action_id") or "")
            if isinstance(action, dict)
            else ""
        )
        self.timeline_open_evidence.setEnabled(bool(action_id))

    def _open_timeline_selection_in_evidence(self) -> None:
        row_data = self._timeline_selected_row_data()
        if not isinstance(row_data, dict):
            return
        action = row_data.get("action")
        if not isinstance(action, dict):
            return
        action_id = str(action.get("action_id") or "")
        archive = str(row_data.get("archive") or "")
        if action_id and archive:
            self._load_evidence_for_archive(
                archive,
                pending_action_id=action_id,
            )
