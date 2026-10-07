from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from apk_research.desktop.evidence_v024_model import (
    build_evidence_model_v024,
    format_process_index_details,
)
from apk_research.desktop.packet_window import PacketInspectorMainWindow
from apk_research.desktop.screen_evidence import (
    build_screen_evidence_index,
    format_screen_locator,
    locate_screen_moment,
)
from apk_research.desktop.unified_session_model import (
    build_unified_session_model,
    format_session_row_details,
    row_search_text,
    rows_near_target,
)
from apk_research.timeline import TIMELINE_ARTIFACT

_ROLE_UNIFIED_ROW = int(Qt.ItemDataRole.UserRole)
_ROLE_EVIDENCE_NODE = int(Qt.ItemDataRole.UserRole)


class UnifiedEvidenceV024MainWindow(PacketInspectorMainWindow):
    """v0.24 cross-navigation over screen, action, flow, packet and owner evidence."""

    unifiedReady = Signal(dict)

    def _build_ui(self) -> None:
        super()._build_ui()
        self.unified_tab_index = self.tabs.addTab(
            self._build_unified_tab(),
            "Session Evidence",
        )

    def _build_results_tab(self):
        page = super()._build_results_tab()
        layout = page.layout()
        button_layout = layout.itemAt(0).layout()
        self.results_unified = QPushButton("Session Evidence")
        button_layout.insertWidget(
            max(0, button_layout.count() - 1),
            self.results_unified,
        )
        self.timeline_open_screen = QPushButton(
            "Выбранное событие → экран"
        )
        self.timeline_open_screen.setEnabled(False)
        layout.insertWidget(
            max(0, layout.count() - 1),
            self.timeline_open_screen,
        )
        return page

    def _build_evidence_tab(self) -> QWidget:
        page = super()._build_evidence_tab()
        layout = page.layout()
        nav = QHBoxLayout()
        self.evidence_open_session = QPushButton(
            "Выбранное → Session Evidence"
        )
        self.evidence_open_screen = QPushButton(
            "Выбранное → экран"
        )
        self.evidence_open_session.setEnabled(False)
        self.evidence_open_screen.setEnabled(False)
        nav.addWidget(self.evidence_open_session)
        nav.addWidget(self.evidence_open_screen)
        nav.addStretch(1)
        layout.insertLayout(
            max(0, layout.count() - 2),
            nav,
        )
        return page

    def _build_packet_tab(self) -> QWidget:
        page = super()._build_packet_tab()
        layout = page.layout()
        nav = QHBoxLayout()
        self.packet_open_evidence = QPushButton("Flow → Evidence")
        self.packet_open_screen = QPushButton("Пакет → экран")
        self.packet_open_evidence.setEnabled(False)
        self.packet_open_screen.setEnabled(False)
        nav.addWidget(self.packet_open_evidence)
        nav.addWidget(self.packet_open_screen)
        nav.addStretch(1)
        layout.insertLayout(
            max(0, layout.count() - 2),
            nav,
        )
        return page

    def _build_unified_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        controls = QHBoxLayout()
        self.unified_load_selected = QPushButton(
            "Открыть выбранный Research ZIP"
        )
        self.unified_search = QLineEdit()
        self.unified_search.setPlaceholderText(
            "время / действие / flow / процесс / PID / inode / IP / протокол"
        )
        controls.addWidget(self.unified_load_selected)
        controls.addWidget(self.unified_search, 1)
        layout.addLayout(controls)

        self.unified_summary = QLabel(
            "Session Evidence: выберите Research ZIP"
        )
        self.unified_summary.setWordWrap(True)
        layout.addWidget(self.unified_summary)

        self.unified_table = QTableWidget(0, 8)
        self.unified_table.setHorizontalHeaderLabels(
            [
                "Target UTC",
                "Тип",
                "Событие",
                "Action",
                "Flows",
                "Packets",
                "Screen",
                "Связь / сила",
            ]
        )
        self.unified_table.setAlternatingRowColors(True)
        self.unified_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.unified_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.unified_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.unified_table.verticalHeader().setVisible(False)
        self.unified_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.unified_table, 1)

        nav = QHBoxLayout()
        self.unified_open_timeline = QPushButton("→ Timeline")
        self.unified_open_evidence = QPushButton("→ Evidence")
        self.unified_open_packets = QPushButton("→ Packets")
        self.unified_near_screen = QPushButton("Экран → события ±2с")
        for button in (
            self.unified_open_timeline,
            self.unified_open_evidence,
            self.unified_open_packets,
            self.unified_near_screen,
        ):
            button.setEnabled(False)
            nav.addWidget(button)
        nav.addStretch(1)
        layout.addLayout(nav)

        self.unified_details = QPlainTextEdit()
        self.unified_details.setReadOnly(True)
        self.unified_details.setMaximumHeight(350)
        self.unified_details.setPlaceholderText(
            "Выберите событие. Здесь показываются связи, provenance и screen locator."
        )
        layout.addWidget(self.unified_details)

        note = QLabel(
            "v0.24 — единая навигация по существующим доказательствам. "
            "RAW остаётся авторитетным источником; Action↔Flow/Packet остаётся temporal-only; "
            "связи с экраном являются time-aligned navigation и не доказывают причинность."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        return page

    def _connect_signals(self) -> None:
        super()._connect_signals()
        self.unifiedReady.connect(self._on_unified_ready)
        self.results_unified.clicked.connect(
            self._inspect_selected_unified
        )
        self.unified_load_selected.clicked.connect(
            self._inspect_selected_unified
        )
        self.unified_search.textChanged.connect(
            self._apply_unified_filter
        )
        self.unified_table.itemSelectionChanged.connect(
            self._on_unified_selection_changed
        )
        self.unified_table.itemDoubleClicked.connect(
            self._open_unified_default
        )
        self.unified_open_timeline.clicked.connect(
            self._open_unified_timeline
        )
        self.unified_open_evidence.clicked.connect(
            self._open_unified_evidence
        )
        self.unified_open_packets.clicked.connect(
            self._open_unified_packets
        )
        self.unified_near_screen.clicked.connect(
            self._show_screen_vicinity
        )

        self.packet_table.itemSelectionChanged.connect(
            self._update_v024_packet_buttons
        )
        self.packet_open_evidence.clicked.connect(
            self._open_packet_flow_in_evidence
        )
        self.packet_open_screen.clicked.connect(
            self._open_packet_screen
        )

        self.timeline_table.itemSelectionChanged.connect(
            self._update_timeline_screen_button
        )
        self.timeline_open_screen.clicked.connect(
            self._open_timeline_screen
        )

        self.evidence_tree.itemSelectionChanged.connect(
            self._update_v024_evidence_buttons
        )
        self.evidence_open_session.clicked.connect(
            self._open_evidence_session
        )
        self.evidence_open_screen.clicked.connect(
            self._open_evidence_screen
        )

    def _inspect_selected_unified(self) -> None:
        path = self._selected_table_path(self.results_table)
        if not path:
            return
        self._load_unified_for_archive(str(path))

    @staticmethod
    def _read_optional_json(
        handle: zipfile.ZipFile,
        name: str,
    ) -> dict[str, Any]:
        try:
            value = json.loads(handle.read(name).decode("utf-8"))
        except KeyError:
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _read_optional_jsonl(
        handle: zipfile.ZipFile,
        name: str,
    ) -> list[dict[str, Any]]:
        try:
            content = handle.read(name).decode("utf-8")
        except KeyError:
            return []
        result = []
        for line in content.splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                result.append(value)
        return result

    def _load_unified_for_archive(
        self,
        archive: str,
        *,
        pending_target_utc: str = "",
        pending_action_id: str = "",
        pending_flow_id: str = "",
        direct_screen_target_utc: str = "",
    ) -> None:
        self._pending_unified_target_utc = pending_target_utc
        self._pending_unified_action_id = pending_action_id
        self._pending_unified_flow_id = pending_flow_id
        self._pending_direct_screen_target_utc = direct_screen_target_utc
        if (
            str(getattr(self, "_unified_archive", "") or "") == archive
            and isinstance(getattr(self, "_unified_model", None), dict)
        ):
            self.tabs.setCurrentIndex(self.unified_tab_index)
            self._select_pending_unified()
            return
        self.unified_summary.setText("Чтение связанных evidence artifacts…")
        self.controller._thread(
            self._load_unified_worker,
            Path(archive),
        )

    def _load_unified_worker(self, archive: Path) -> None:
        try:
            with zipfile.ZipFile(archive) as handle:
                network = json.loads(
                    handle.read("02_normalized/network-flows.json").decode("utf-8")
                )
                timeline = json.loads(
                    handle.read(TIMELINE_ARTIFACT).decode("utf-8")
                )
                continuous = self._read_optional_json(
                    handle,
                    "02_normalized/continuous-screen.json",
                )
                canonical = self._read_optional_json(
                    handle,
                    "02_normalized/screen.json",
                )
                packet_rows = self._read_optional_jsonl(
                    handle,
                    "02_normalized/continuous-screen-packets.jsonl",
                )
            if not isinstance(network, dict) or not isinstance(timeline, dict):
                raise ValueError("Research ZIP evidence schema is invalid")
            flows = [
                value
                for value in network.get("flows") or []
                if isinstance(value, dict)
            ]
            screen_index = build_screen_evidence_index(
                continuous,
                canonical,
                packet_rows,
            )
            model = build_unified_session_model(
                timeline=timeline,
                flows=flows,
                screen_index=screen_index,
                package=str(network.get("package") or ""),
            )
            self.unifiedReady.emit(
                {
                    "archive": str(archive),
                    "model": model,
                }
            )
        except Exception as exc:
            self.controller.error.emit(
                str(exc) or exc.__class__.__name__
            )

    def _on_unified_ready(self, data: dict) -> None:
        self._unified_archive = str(data.get("archive") or "")
        model = data.get("model")
        self._unified_model = model if isinstance(model, dict) else {}
        rows = [
            row
            for row in self._unified_model.get("rows") or []
            if isinstance(row, dict)
        ]
        self.unified_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            screen = row.get("screen")
            screen_text = "—"
            if isinstance(screen, dict):
                continuous = screen.get("continuous")
                canonical = screen.get("canonical")
                if isinstance(continuous, dict):
                    screen_text = f"C#{continuous.get('sequence') or '—'}"
                if isinstance(canonical, dict):
                    if canonical.get("covered"):
                        screen_text += f" / HD#{canonical.get('chunk_index') or '—'}"
                    elif canonical:
                        screen_text += " / HD gap"
            values = [
                str(row.get("target_utc") or row.get("host_utc") or ""),
                str(row.get("kind") or ""),
                str(row.get("name") or ""),
                str(row.get("action_id") or ""),
                ", ".join(str(value) for value in row.get("flow_ids") or []),
                str(int(row.get("packet_count") or 0)),
                screen_text,
                f"{row.get('relation_type') or '—'} / {row.get('relation_strength') or '—'}",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(_ROLE_UNIFIED_ROW, row)
                self.unified_table.setItem(row_index, column, item)
        self.unified_table.resizeColumnsToContents()
        self.unified_summary.setText(
            f"{self._unified_model.get('package') or '—'}"
            f" • {int(self._unified_model.get('row_count') or 0)} events"
            f" • {int(self._unified_model.get('action_count') or 0)} actions"
            f" • {int(self._unified_model.get('flow_count') or 0)} flows"
            f" • screen {'yes' if self._unified_model.get('screen_available') else 'no'}"
            f" • mapping {self._unified_model.get('screen_mapping_method') or '—'}"
            f" / {self._unified_model.get('screen_mapping_confidence') or '—'}"
        )
        self.tabs.setCurrentIndex(self.unified_tab_index)
        self._apply_unified_filter()
        self._select_pending_unified()
        if rows and self.unified_table.currentRow() < 0:
            self.unified_table.selectRow(0)

    def _selected_unified_row(self) -> dict[str, Any] | None:
        row = self.unified_table.currentRow()
        if row < 0:
            return None
        item = self.unified_table.item(row, 0)
        if item is None:
            return None
        value = item.data(_ROLE_UNIFIED_ROW)
        return value if isinstance(value, dict) else None

    def _on_unified_selection_changed(self) -> None:
        row = self._selected_unified_row()
        if row is None:
            self.unified_details.clear()
            for button in (
                self.unified_open_timeline,
                self.unified_open_evidence,
                self.unified_open_packets,
                self.unified_near_screen,
            ):
                button.setEnabled(False)
            return
        self.unified_details.setPlainText(format_session_row_details(row))
        self.unified_open_timeline.setEnabled(bool(row.get("action_id")))
        self.unified_open_evidence.setEnabled(
            bool(row.get("action_id") or row.get("flow_ids"))
        )
        self.unified_open_packets.setEnabled(bool(row.get("flow_ids")))
        self.unified_near_screen.setEnabled(
            isinstance(row.get("screen"), dict)
            and bool(row.get("target_utc"))
        )

    def _apply_unified_filter(self) -> None:
        if not hasattr(self, "unified_table"):
            return
        query = self.unified_search.text().strip().lower()
        for row_index in range(self.unified_table.rowCount()):
            item = self.unified_table.item(row_index, 0)
            row = item.data(_ROLE_UNIFIED_ROW) if item is not None else None
            visible = (
                not query
                or (isinstance(row, dict) and query in row_search_text(row))
            )
            self.unified_table.setRowHidden(row_index, not visible)

    def _open_unified_default(self, item, column: int) -> None:
        del item, column
        row = self._selected_unified_row()
        if not isinstance(row, dict):
            return
        if row.get("flow_ids"):
            self._open_unified_evidence()
        elif row.get("action_id"):
            self._open_unified_timeline()

    def _open_unified_timeline(self) -> None:
        row = self._selected_unified_row()
        if not isinstance(row, dict):
            return
        action_id = str(row.get("action_id") or "")
        if not action_id:
            return
        archive = str(getattr(self, "_unified_archive", "") or "")
        if (
            archive == str(getattr(self, "_timeline_archive", "") or "")
            and self._select_timeline_action(action_id)
        ):
            return
        self._pending_timeline_action_id = action_id
        self.controller._thread(self._load_refined_timeline, archive)

    def _open_unified_evidence(self) -> None:
        row = self._selected_unified_row()
        if not isinstance(row, dict):
            return
        archive = str(getattr(self, "_unified_archive", "") or "")
        flow_ids = [str(value) for value in row.get("flow_ids") or [] if value]
        self._load_evidence_for_archive(
            archive,
            pending_flow_id=flow_ids[0] if flow_ids else "",
            pending_action_id=str(row.get("action_id") or ""),
        )

    def _open_unified_packets(self) -> None:
        row = self._selected_unified_row()
        if not isinstance(row, dict):
            return
        flow_ids = [str(value) for value in row.get("flow_ids") or [] if value]
        model = getattr(self, "_unified_model", None)
        flow_index = model.get("flow_index") if isinstance(model, dict) else {}
        if not flow_ids or not isinstance(flow_index, dict):
            return
        flow = flow_index.get(flow_ids[0])
        archive = str(getattr(self, "_unified_archive", "") or "")
        if isinstance(flow, dict) and archive:
            self._load_packet_flow(archive, flow)

    def _show_screen_vicinity(self) -> None:
        row = self._selected_unified_row()
        model = getattr(self, "_unified_model", None)
        if not isinstance(row, dict) or not isinstance(model, dict):
            return
        target_utc = str(row.get("target_utc") or "")
        if not target_utc:
            return
        screen = row.get("screen")
        nearby = rows_near_target(model, target_utc, radius_seconds=2.0)
        lines = [format_screen_locator(screen), "", "Nearby evidence ±2s:"]
        for candidate in nearby[:30]:
            lines.append(
                f"  {float(candidate.get('delta_seconds') or 0.0):+.3f}s"
                f" • {candidate.get('kind') or 'event'}"
                f" • {candidate.get('name') or '—'}"
                f" • action {candidate.get('action_id') or '—'}"
                f" • flows {','.join(str(value) for value in candidate.get('flow_ids') or []) or '—'}"
            )
        self.unified_details.setPlainText("\n".join(lines))

    def _select_pending_unified(self) -> None:
        model = getattr(self, "_unified_model", None)
        if not isinstance(model, dict):
            return
        action_id = str(getattr(self, "_pending_unified_action_id", "") or "")
        flow_id = str(getattr(self, "_pending_unified_flow_id", "") or "")
        target_utc = str(getattr(self, "_pending_unified_target_utc", "") or "")
        direct_target = str(getattr(self, "_pending_direct_screen_target_utc", "") or "")
        self._pending_unified_action_id = ""
        self._pending_unified_flow_id = ""
        self._pending_unified_target_utc = ""
        self._pending_direct_screen_target_utc = ""

        best_row = -1
        best_delta: float | None = None
        from datetime import datetime

        def parse(value: str):
            if not value:
                return None
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None

        target_dt = parse(target_utc or direct_target)
        for row_index in range(self.unified_table.rowCount()):
            item = self.unified_table.item(row_index, 0)
            row = item.data(_ROLE_UNIFIED_ROW) if item is not None else None
            if not isinstance(row, dict):
                continue
            if action_id and str(row.get("action_id") or "") == action_id:
                best_row = row_index
                break
            if flow_id and flow_id in [str(value) for value in row.get("flow_ids") or []]:
                best_row = row_index
                break
            if target_dt is not None:
                row_dt = parse(str(row.get("target_utc") or ""))
                if row_dt is not None:
                    delta = abs((row_dt - target_dt).total_seconds())
                    if best_delta is None or delta < best_delta:
                        best_delta = delta
                        best_row = row_index
        if best_row >= 0:
            self.unified_table.selectRow(best_row)
            self.unified_table.scrollToItem(self.unified_table.item(best_row, 0))
        self.tabs.setCurrentIndex(self.unified_tab_index)

        if direct_target:
            screen_index = model.get("screen_index")
            locator = (
                locate_screen_moment(screen_index, direct_target)
                if isinstance(screen_index, dict)
                else None
            )
            nearby = rows_near_target(model, direct_target, radius_seconds=2.0)
            lines = [format_screen_locator(locator), "", "Nearby evidence ±2s:"]
            for candidate in nearby[:30]:
                lines.append(
                    f"  {float(candidate.get('delta_seconds') or 0.0):+.3f}s"
                    f" • {candidate.get('kind') or 'event'}"
                    f" • {candidate.get('name') or '—'}"
                    f" • action {candidate.get('action_id') or '—'}"
                    f" • flows {','.join(str(value) for value in candidate.get('flow_ids') or []) or '—'}"
                )
            self.unified_details.setPlainText("\n".join(lines))

    def _update_v024_packet_buttons(self) -> None:
        packet = self._selected_packet()
        report = getattr(self, "_packet_report", None)
        self.packet_open_evidence.setEnabled(
            isinstance(report, dict) and bool(report.get("flow_id"))
        )
        self.packet_open_screen.setEnabled(
            isinstance(packet, dict) and bool(packet.get("target_utc"))
        )

    def _open_packet_flow_in_evidence(self) -> None:
        report = getattr(self, "_packet_report", None)
        if not isinstance(report, dict):
            return
        archive = str(report.get("archive") or "")
        flow_id = str(report.get("flow_id") or "")
        if archive and flow_id:
            self._load_evidence_for_archive(
                archive,
                pending_flow_id=flow_id,
            )

    def _open_packet_screen(self) -> None:
        packet = self._selected_packet()
        report = getattr(self, "_packet_report", None)
        if not isinstance(packet, dict) or not isinstance(report, dict):
            return
        target_utc = str(packet.get("target_utc") or "")
        archive = str(report.get("archive") or "")
        if archive and target_utc:
            self._load_unified_for_archive(
                archive,
                pending_target_utc=target_utc,
                pending_flow_id=str(report.get("flow_id") or ""),
                direct_screen_target_utc=target_utc,
            )

    def _update_timeline_screen_button(self) -> None:
        row_data = self._timeline_selected_row_data()
        event = row_data.get("event") if isinstance(row_data, dict) else None
        self.timeline_open_screen.setEnabled(
            isinstance(event, dict) and bool(event.get("target_utc"))
        )

    def _open_timeline_screen(self) -> None:
        row_data = self._timeline_selected_row_data()
        if not isinstance(row_data, dict):
            return
        event = row_data.get("event")
        if not isinstance(event, dict):
            return
        target_utc = str(event.get("target_utc") or "")
        archive = str(row_data.get("archive") or "")
        action = row_data.get("action")
        action_id = str(action.get("action_id") or "") if isinstance(action, dict) else ""
        if archive and target_utc:
            self._load_unified_for_archive(
                archive,
                pending_target_utc=target_utc,
                pending_action_id=action_id,
                direct_screen_target_utc=target_utc,
            )

    @staticmethod
    def _evidence_node_target_utc(node: dict[str, Any] | None) -> str:
        if not isinstance(node, dict):
            return ""
        action = node.get("action")
        if isinstance(action, dict):
            correlation = action.get("correlation")
            if isinstance(correlation, dict):
                value = str(correlation.get("target_started_utc_estimate") or "")
                if value:
                    return value
        flow = node.get("flow")
        if isinstance(flow, dict):
            value = str(flow.get("first_target_utc") or "")
            if value:
                return value
        locator = node.get("locator")
        if isinstance(locator, dict):
            return str(locator.get("first_target_utc") or "")
        return ""

    def _update_v024_evidence_buttons(self) -> None:
        node = self._selected_evidence_node()
        self.evidence_open_session.setEnabled(isinstance(node, dict))
        self.evidence_open_screen.setEnabled(
            bool(self._evidence_node_target_utc(node))
        )

    def _open_evidence_session(self) -> None:
        node = self._selected_evidence_node()
        if not isinstance(node, dict):
            return
        archive = str(getattr(self, "_evidence_archive", "") or "")
        if not archive:
            return
        self._load_unified_for_archive(
            archive,
            pending_action_id=self._node_action_id(node),
            pending_flow_id=self._node_flow_id(node),
            pending_target_utc=self._evidence_node_target_utc(node),
        )

    def _open_evidence_screen(self) -> None:
        node = self._selected_evidence_node()
        archive = str(getattr(self, "_evidence_archive", "") or "")
        target_utc = self._evidence_node_target_utc(node)
        if archive and target_utc:
            self._load_unified_for_archive(
                archive,
                pending_target_utc=target_utc,
                pending_action_id=self._node_action_id(node),
                pending_flow_id=self._node_flow_id(node),
                direct_screen_target_utc=target_utc,
            )

    def _load_evidence_archive(self, archive: Path) -> None:
        try:
            with zipfile.ZipFile(archive) as handle:
                network = json.loads(
                    handle.read("02_normalized/network-flows.json").decode("utf-8")
                )
                timeline = json.loads(
                    handle.read(TIMELINE_ARTIFACT).decode("utf-8")
                )
                try:
                    socket_attribution = json.loads(
                        handle.read("02_normalized/socket-attribution.json").decode("utf-8")
                    )
                except KeyError:
                    socket_attribution = {}
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
            model = build_evidence_model_v024(
                flows,
                actions,
                package=str(network.get("package") or ""),
            )
            self.evidenceReady.emit(
                {
                    "archive": str(archive),
                    "network_schema_version": str(network.get("schema_version") or ""),
                    "timeline_schema_version": str(timeline.get("schema_version") or ""),
                    "socket_summary": (
                        socket_attribution.get("summary")
                        if isinstance(socket_attribution, dict)
                        else {}
                    ) or socket_attribution,
                    "model": model,
                }
            )
        except KeyError as exc:
            self.controller.error.emit(
                f"В Research ZIP нет обязательного evidence artifact: {exc}"
            )
        except Exception as exc:
            self.controller.error.emit(str(exc) or exc.__class__.__name__)

    def _on_evidence_ready(self, data: dict) -> None:
        super()._on_evidence_ready(data)
        model = getattr(self, "_evidence_model", None)
        if not isinstance(model, dict):
            return
        processes = [
            node
            for node in model.get("processes") or []
            if isinstance(node, dict)
        ]
        if not processes:
            return
        root = self._tree_item(
            {"kind": "root", "label": "По процессам/сокетам"},
            "По процессам/сокетам",
            "Reverse index",
            "Process/Socket → all related Flow → Action / Raw",
        )
        self.evidence_tree.addTopLevelItem(root)
        for process in processes:
            processes_text = ", ".join(
                str(value) for value in process.get("processes") or []
            ) or "process/socket"
            label = processes_text
            if process.get("inode") is not None:
                label += f" • inode {process.get('inode')}"
            process_item = self._tree_item(
                process,
                label,
                "Process/Socket index",
                str(process.get("confidence") or "UNKNOWN"),
            )
            root.addChild(process_item)
            for flow_node in process.get("flow_nodes") or []:
                if isinstance(flow_node, dict):
                    self._append_flow_node(
                        process_item,
                        flow_node,
                        include_actions=True,
                    )
        root.setExpanded(True)
        self.evidence_tree.resizeColumnToContents(0)

    def _show_evidence_details(self) -> None:
        node = self._selected_evidence_node()
        if isinstance(node, dict) and str(node.get("kind") or "") == "process_index":
            self.evidence_details.setPlainText(
                format_process_index_details(node)
            )
            self.evidence_open_timeline.setEnabled(False)
            self.evidence_open_network.setEnabled(False)
            return
        super()._show_evidence_details()
