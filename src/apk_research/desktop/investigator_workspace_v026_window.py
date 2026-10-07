from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from apk_research.desktop.investigator_workspace_v026 import (
    active_evidence_refs,
    add_evidence_set,
    build_report_data,
    build_workspace_model,
    filter_workspace_rows,
    format_workspace_row_details,
    load_workspace_state,
    remove_evidence_set,
    report_markdown,
    save_workspace_state,
    set_evidence_membership,
    toggle_bookmark,
    workspace_state_path,
)
from apk_research.desktop.unified_evidence_v024 import (
    UnifiedEvidenceV024MainWindow,
)

_ROLE_WORKSPACE_ROW = int(Qt.ItemDataRole.UserRole)
_ROLE_WORKSPACE_REF = int(Qt.ItemDataRole.UserRole)


class InvestigatorWorkspaceV026MainWindow(UnifiedEvidenceV024MainWindow):
    """v0.26 investigation workflow over the verified v0.24/v0.25 evidence model."""

    def _build_ui(self) -> None:
        super()._build_ui()
        self.workspace_tab_index = self.tabs.addTab(
            self._build_workspace_tab(),
            "Investigator",
        )

    def _build_results_tab(self) -> QWidget:
        page = super()._build_results_tab()
        layout = page.layout()
        button_layout = layout.itemAt(0).layout()
        self.results_workspace = QPushButton("Investigator Workspace")
        button_layout.insertWidget(
            max(0, button_layout.count() - 1),
            self.results_workspace,
        )
        return page

    def _build_workspace_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)

        open_row = QHBoxLayout()
        self.workspace_load_selected = QPushButton(
            "Открыть выбранный Research ZIP"
        )
        self.workspace_search = QLineEdit()
        self.workspace_search.setPlaceholderText(
            "Глобальный поиск: EV-ссылка / время / действие / flow / процесс / endpoint / протокол"
        )
        self.workspace_clear_filters = QPushButton("Сбросить фильтры")
        open_row.addWidget(self.workspace_load_selected)
        open_row.addWidget(self.workspace_search, 1)
        open_row.addWidget(self.workspace_clear_filters)
        root.addLayout(open_row)

        filters = QHBoxLayout()
        self.workspace_kind = QComboBox()
        self.workspace_protocol = QComboBox()
        self.workspace_process = QComboBox()
        self.workspace_class = QComboBox()
        for combo, title in (
            (self.workspace_kind, "Все типы"),
            (self.workspace_protocol, "Все протоколы"),
            (self.workspace_process, "Все процессы"),
            (self.workspace_class, "Все классы связи"),
        ):
            combo.addItem(title, "")
            filters.addWidget(combo)
        self.workspace_endpoint = QLineEdit()
        self.workspace_endpoint.setPlaceholderText("endpoint / IP")
        self.workspace_action = QLineEdit()
        self.workspace_action.setPlaceholderText("action id")
        self.workspace_start = QLineEdit()
        self.workspace_start.setPlaceholderText("UTC from")
        self.workspace_end = QLineEdit()
        self.workspace_end.setPlaceholderText("UTC to")
        filters.addWidget(self.workspace_endpoint)
        filters.addWidget(self.workspace_action)
        filters.addWidget(self.workspace_start)
        filters.addWidget(self.workspace_end)
        root.addLayout(filters)

        self.workspace_summary = QLabel(
            "Investigator Workspace: выберите Research ZIP"
        )
        self.workspace_summary.setWordWrap(True)
        root.addWidget(self.workspace_summary)

        vertical = QSplitter(Qt.Orientation.Vertical)

        evidence_page = QWidget()
        evidence_layout = QVBoxLayout(evidence_page)
        evidence_layout.setContentsMargins(0, 0, 0, 0)
        self.workspace_table = QTableWidget(0, 9)
        self.workspace_table.setHorizontalHeaderLabels(
            [
                "UTC",
                "Reference",
                "Класс",
                "Тип",
                "Событие",
                "Action",
                "Протокол",
                "Endpoint / process",
                "Связь / сила",
            ]
        )
        self.workspace_table.setAlternatingRowColors(True)
        self.workspace_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.workspace_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.workspace_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.workspace_table.verticalHeader().setVisible(False)
        self.workspace_table.horizontalHeader().setStretchLastSection(True)
        evidence_layout.addWidget(self.workspace_table, 1)

        nav = QHBoxLayout()
        self.workspace_open_source = QPushButton("→ Session Evidence")
        self.workspace_open_timeline = QPushButton("→ Timeline")
        self.workspace_open_evidence = QPushButton("→ Evidence")
        self.workspace_open_packets = QPushButton("→ Packets")
        self.workspace_open_screen = QPushButton("→ Screen context")
        self.workspace_bookmark = QPushButton("★ Закладка")
        for button in (
            self.workspace_open_source,
            self.workspace_open_timeline,
            self.workspace_open_evidence,
            self.workspace_open_packets,
            self.workspace_open_screen,
            self.workspace_bookmark,
        ):
            button.setEnabled(False)
            nav.addWidget(button)
        nav.addStretch(1)
        evidence_layout.addLayout(nav)

        self.workspace_details = QPlainTextEdit()
        self.workspace_details.setReadOnly(True)
        self.workspace_details.setMaximumHeight(210)
        self.workspace_details.setPlaceholderText(
            "Выберите строку. EV-ссылка является устойчивым навигационным ключом, а не новым доказательством."
        )
        evidence_layout.addWidget(self.workspace_details)
        vertical.addWidget(evidence_page)

        saved_page = QWidget()
        saved_layout = QVBoxLayout(saved_page)
        saved_layout.setContentsMargins(0, 0, 0, 0)
        saved_group = QGroupBox("Наборы доказательств и отчёт")
        saved_group_layout = QVBoxLayout(saved_group)
        set_row = QHBoxLayout()
        self.workspace_set_combo = QComboBox()
        self.workspace_new_set = QPushButton("Новый набор…")
        self.workspace_delete_set = QPushButton("Удалить набор")
        self.workspace_add_to_set = QPushButton("Добавить выбранное")
        self.workspace_remove_from_set = QPushButton("Убрать из набора")
        set_row.addWidget(QLabel("Набор:"))
        set_row.addWidget(self.workspace_set_combo, 1)
        set_row.addWidget(self.workspace_new_set)
        set_row.addWidget(self.workspace_delete_set)
        set_row.addWidget(self.workspace_add_to_set)
        set_row.addWidget(self.workspace_remove_from_set)
        saved_group_layout.addLayout(set_row)

        self.workspace_set_table = QTableWidget(0, 5)
        self.workspace_set_table.setHorizontalHeaderLabels(
            ["Reference", "UTC", "Событие", "Протокол", "Связь"]
        )
        self.workspace_set_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.workspace_set_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.workspace_set_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.workspace_set_table.verticalHeader().setVisible(False)
        self.workspace_set_table.horizontalHeader().setStretchLastSection(True)
        saved_group_layout.addWidget(self.workspace_set_table)

        report_row = QHBoxLayout()
        self.workspace_set_open_source = QPushButton("Выбранное → источник")
        self.workspace_build_report = QPushButton("Сформировать отчёт")
        self.workspace_save_report_md = QPushButton("Сохранить Markdown…")
        self.workspace_save_report_json = QPushButton("Сохранить JSON…")
        self.workspace_save_report_md.setEnabled(False)
        self.workspace_save_report_json.setEnabled(False)
        report_row.addWidget(self.workspace_set_open_source)
        report_row.addWidget(self.workspace_build_report)
        report_row.addWidget(self.workspace_save_report_md)
        report_row.addWidget(self.workspace_save_report_json)
        report_row.addStretch(1)
        saved_group_layout.addLayout(report_row)

        self.workspace_report = QPlainTextEdit()
        self.workspace_report.setReadOnly(True)
        self.workspace_report.setPlaceholderText(
            "Отчёт строится только из выбранного набора. Каждая запись содержит EV-ссылку для возврата к исходному evidence item."
        )
        saved_group_layout.addWidget(self.workspace_report, 1)
        saved_layout.addWidget(saved_group, 1)
        vertical.addWidget(saved_page)
        vertical.setStretchFactor(0, 3)
        vertical.setStretchFactor(1, 2)
        root.addWidget(vertical, 1)

        note = QLabel(
            "v0.26 — рабочее место исследователя поверх существующих evidence artifacts. "
            "Закладки и наборы хранятся рядом с Research ZIP в отдельном .investigator.json и не изменяют архив. "
            "RAW остаётся авторитетным; temporal/navigation связи не доказывают причинность."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        return page

    def _connect_signals(self) -> None:
        super()._connect_signals()
        self.results_workspace.clicked.connect(self._inspect_selected_workspace)
        self.workspace_load_selected.clicked.connect(self._inspect_selected_workspace)
        self.unifiedReady.connect(self._on_workspace_unified_ready)

        for widget in (
            self.workspace_search,
            self.workspace_endpoint,
            self.workspace_action,
            self.workspace_start,
            self.workspace_end,
        ):
            widget.textChanged.connect(self._apply_workspace_filters)
        for combo in (
            self.workspace_kind,
            self.workspace_protocol,
            self.workspace_process,
            self.workspace_class,
        ):
            combo.currentIndexChanged.connect(self._apply_workspace_filters)
        self.workspace_clear_filters.clicked.connect(self._clear_workspace_filters)
        self.workspace_table.itemSelectionChanged.connect(
            self._on_workspace_selection_changed
        )
        self.workspace_table.itemDoubleClicked.connect(
            lambda _item, _column: self._workspace_open_source_view()
        )
        self.workspace_open_source.clicked.connect(self._workspace_open_source_view)
        self.workspace_open_timeline.clicked.connect(self._workspace_open_timeline_view)
        self.workspace_open_evidence.clicked.connect(self._workspace_open_evidence_view)
        self.workspace_open_packets.clicked.connect(self._workspace_open_packets_view)
        self.workspace_open_screen.clicked.connect(self._workspace_open_screen_view)
        self.workspace_bookmark.clicked.connect(self._toggle_workspace_bookmark)

        self.workspace_new_set.clicked.connect(self._new_workspace_set)
        self.workspace_delete_set.clicked.connect(self._delete_workspace_set)
        self.workspace_add_to_set.clicked.connect(self._add_workspace_selection_to_set)
        self.workspace_remove_from_set.clicked.connect(self._remove_workspace_set_selection)
        self.workspace_set_combo.currentIndexChanged.connect(self._on_workspace_set_changed)
        self.workspace_set_table.itemDoubleClicked.connect(
            lambda _item, _column: self._workspace_open_set_source()
        )
        self.workspace_set_open_source.clicked.connect(self._workspace_open_set_source)
        self.workspace_build_report.clicked.connect(self._build_workspace_report)
        self.workspace_save_report_md.clicked.connect(self._save_workspace_report_md)
        self.workspace_save_report_json.clicked.connect(self._save_workspace_report_json)

    def _inspect_selected_workspace(self) -> None:
        path = self._selected_table_path(self.results_table)
        if not path:
            return
        archive = str(path)
        self._workspace_requested_archive = archive
        self._load_unified_for_archive(archive)
        if (
            str(getattr(self, "_unified_archive", "") or "") == archive
            and isinstance(getattr(self, "_unified_model", None), dict)
        ):
            self._activate_workspace(archive, self._unified_model)

    def _on_workspace_unified_ready(self, data: dict) -> None:
        archive = str(data.get("archive") or "")
        model = data.get("model")
        if not archive or not isinstance(model, dict):
            return
        self._activate_workspace(archive, model)

    def _activate_workspace(self, archive: str, unified_model: dict[str, Any]) -> None:
        self._workspace_archive = archive
        self._workspace_model = build_workspace_model(unified_model)
        valid_refs = list((self._workspace_model.get("rows_by_ref") or {}).keys())
        self._workspace_state_path = workspace_state_path(archive)
        self._workspace_state = load_workspace_state(
            self._workspace_state_path,
            archive=archive,
            valid_refs=valid_refs,
        )
        self._populate_workspace_filters()
        self._populate_workspace_sets()
        self._apply_workspace_filters()
        self._refresh_workspace_set_table()
        self.workspace_report.clear()
        self._workspace_report_data = None
        self.workspace_save_report_md.setEnabled(False)
        self.workspace_save_report_json.setEnabled(False)
        self.tabs.setCurrentIndex(self.workspace_tab_index)

    def _populate_combo(self, combo: QComboBox, title: str, values: list[str]) -> None:
        current = str(combo.currentData() or "")
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(title, "")
        for value in values:
            combo.addItem(value, value)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _populate_workspace_filters(self) -> None:
        model = getattr(self, "_workspace_model", {})
        self._populate_combo(self.workspace_kind, "Все типы", list(model.get("kinds") or []))
        self._populate_combo(
            self.workspace_protocol,
            "Все протоколы",
            list(model.get("protocols") or []),
        )
        self._populate_combo(
            self.workspace_process,
            "Все процессы",
            list(model.get("processes") or []),
        )
        self._populate_combo(
            self.workspace_class,
            "Все классы связи",
            list(model.get("evidence_classes") or []),
        )

    def _populate_workspace_sets(self) -> None:
        state = getattr(self, "_workspace_state", {})
        active = str(state.get("active_set_id") or "")
        self.workspace_set_combo.blockSignals(True)
        self.workspace_set_combo.clear()
        for item in state.get("evidence_sets") or []:
            if not isinstance(item, dict):
                continue
            self.workspace_set_combo.addItem(
                str(item.get("name") or item.get("id") or "Набор"),
                str(item.get("id") or ""),
            )
        index = self.workspace_set_combo.findData(active)
        self.workspace_set_combo.setCurrentIndex(index if index >= 0 else 0)
        self.workspace_set_combo.blockSignals(False)

    def _apply_workspace_filters(self, *_args) -> None:
        model = getattr(self, "_workspace_model", None)
        if not isinstance(model, dict):
            return
        rows = filter_workspace_rows(
            model,
            query=self.workspace_search.text(),
            kind=str(self.workspace_kind.currentData() or ""),
            protocol=str(self.workspace_protocol.currentData() or ""),
            process=str(self.workspace_process.currentData() or ""),
            endpoint=self.workspace_endpoint.text(),
            action=self.workspace_action.text(),
            evidence_class=str(self.workspace_class.currentData() or ""),
            start_utc=self.workspace_start.text(),
            end_utc=self.workspace_end.text(),
        )
        self._workspace_visible_rows = rows
        self.workspace_table.setRowCount(len(rows))
        bookmarks = set((getattr(self, "_workspace_state", {}) or {}).get("bookmarks") or [])
        for row_index, row in enumerate(rows):
            process_endpoint = " / ".join(
                value
                for value in [
                    ", ".join(row.get("endpoints") or []),
                    ", ".join(row.get("processes") or []),
                ]
                if value
            )
            reference = str(row.get("ref") or "")
            if reference in bookmarks:
                reference = "★ " + reference
            values = [
                str(row.get("target_utc") or row.get("host_utc") or ""),
                reference,
                str(row.get("evidence_class") or ""),
                str(row.get("kind") or ""),
                str(row.get("name") or ""),
                str(row.get("action_id") or ""),
                ", ".join(row.get("protocols") or []),
                process_endpoint,
                f"{row.get('relation_type') or '—'} / {row.get('relation_strength') or '—'}",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(_ROLE_WORKSPACE_ROW, row)
                self.workspace_table.setItem(row_index, column, item)
        self.workspace_table.resizeColumnsToContents()
        self.workspace_summary.setText(
            f"{model.get('package') or '—'} • {len(rows)}/{int(model.get('row_count') or 0)} evidence rows"
            f" • {int(model.get('action_count') or 0)} actions"
            f" • {int(model.get('flow_count') or 0)} flows"
            f" • {len(model.get('protocols') or [])} protocols"
            f" • {len(model.get('endpoints') or [])} endpoints"
            f" • state: {getattr(self, '_workspace_state_path', '—')}"
        )
        self._on_workspace_selection_changed()

    def _clear_workspace_filters(self) -> None:
        self.workspace_search.clear()
        self.workspace_endpoint.clear()
        self.workspace_action.clear()
        self.workspace_start.clear()
        self.workspace_end.clear()
        for combo in (
            self.workspace_kind,
            self.workspace_protocol,
            self.workspace_process,
            self.workspace_class,
        ):
            combo.setCurrentIndex(0)
        self._apply_workspace_filters()

    def _selected_workspace_rows(self) -> list[dict[str, Any]]:
        rows = []
        selection = self.workspace_table.selectionModel()
        if selection is None:
            return rows
        for index in selection.selectedRows():
            item = self.workspace_table.item(index.row(), 0)
            value = item.data(_ROLE_WORKSPACE_ROW) if item is not None else None
            if isinstance(value, dict):
                rows.append(value)
        return rows

    def _selected_workspace_row(self) -> dict[str, Any] | None:
        rows = self._selected_workspace_rows()
        return rows[0] if rows else None

    def _on_workspace_selection_changed(self) -> None:
        row = self._selected_workspace_row()
        available = isinstance(row, dict)
        for button in (
            self.workspace_open_source,
            self.workspace_bookmark,
        ):
            button.setEnabled(available)
        self.workspace_add_to_set.setEnabled(bool(self._selected_workspace_rows()))
        if not available:
            self.workspace_details.clear()
            self.workspace_open_timeline.setEnabled(False)
            self.workspace_open_evidence.setEnabled(False)
            self.workspace_open_packets.setEnabled(False)
            self.workspace_open_screen.setEnabled(False)
            return
        self.workspace_details.setPlainText(format_workspace_row_details(row))
        self.workspace_open_timeline.setEnabled(bool(row.get("action_id")))
        self.workspace_open_evidence.setEnabled(bool(row.get("action_id") or row.get("flow_ids")))
        self.workspace_open_packets.setEnabled(bool(row.get("flow_ids")))
        self.workspace_open_screen.setEnabled(bool(row.get("screen_available")))
        bookmarks = set((getattr(self, "_workspace_state", {}) or {}).get("bookmarks") or [])
        self.workspace_bookmark.setText(
            "★ Убрать закладку" if row.get("ref") in bookmarks else "☆ Добавить закладку"
        )

    def _select_source_row(self, row: dict[str, Any]) -> bool:
        source = row.get("source_row")
        if not isinstance(source, dict):
            return False
        self.unified_search.clear()
        self._pending_unified_target_utc = str(source.get("target_utc") or "")
        self._pending_unified_action_id = str(source.get("action_id") or "")
        flow_ids = [str(value) for value in source.get("flow_ids") or [] if value]
        self._pending_unified_flow_id = flow_ids[0] if flow_ids else ""
        self.tabs.setCurrentIndex(self.unified_tab_index)
        self._select_pending_unified()
        return self._selected_unified_row() is not None

    def _workspace_open_source_view(self) -> None:
        row = self._selected_workspace_row()
        if isinstance(row, dict):
            self._select_source_row(row)

    def _workspace_open_timeline_view(self) -> None:
        row = self._selected_workspace_row()
        if isinstance(row, dict) and self._select_source_row(row):
            self._open_unified_timeline()

    def _workspace_open_evidence_view(self) -> None:
        row = self._selected_workspace_row()
        if isinstance(row, dict) and self._select_source_row(row):
            self._open_unified_evidence()

    def _workspace_open_packets_view(self) -> None:
        row = self._selected_workspace_row()
        if isinstance(row, dict) and self._select_source_row(row):
            self._open_unified_packets()

    def _workspace_open_screen_view(self) -> None:
        row = self._selected_workspace_row()
        if isinstance(row, dict) and self._select_source_row(row):
            self._show_screen_vicinity()

    def _save_workspace_state(self) -> None:
        state = getattr(self, "_workspace_state", None)
        path = getattr(self, "_workspace_state_path", None)
        if not isinstance(state, dict) or path is None:
            return
        try:
            save_workspace_state(path, state)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Investigator Workspace",
                f"Не удалось сохранить состояние рабочего места:\n{exc}",
            )

    def _toggle_workspace_bookmark(self) -> None:
        row = self._selected_workspace_row()
        state = getattr(self, "_workspace_state", None)
        if not isinstance(row, dict) or not isinstance(state, dict):
            return
        toggle_bookmark(state, str(row.get("ref") or ""))
        self._save_workspace_state()
        self._apply_workspace_filters()

    def _new_workspace_set(self) -> None:
        state = getattr(self, "_workspace_state", None)
        if not isinstance(state, dict):
            return
        name, accepted = QInputDialog.getText(
            self,
            "Новый набор доказательств",
            "Название:",
        )
        if not accepted or not name.strip():
            return
        add_evidence_set(state, name)
        self._save_workspace_state()
        self._populate_workspace_sets()
        self._refresh_workspace_set_table()

    def _delete_workspace_set(self) -> None:
        state = getattr(self, "_workspace_state", None)
        if not isinstance(state, dict):
            return
        set_id = str(self.workspace_set_combo.currentData() or "")
        if not remove_evidence_set(state, set_id):
            QMessageBox.information(
                self,
                "Наборы доказательств",
                "Последний набор удалить нельзя.",
            )
            return
        self._save_workspace_state()
        self._populate_workspace_sets()
        self._refresh_workspace_set_table()

    def _add_workspace_selection_to_set(self) -> None:
        state = getattr(self, "_workspace_state", None)
        if not isinstance(state, dict):
            return
        rows = self._selected_workspace_rows()
        refs = [str(row.get("ref") or "") for row in rows if row.get("ref")]
        if not refs:
            return
        set_id = str(self.workspace_set_combo.currentData() or state.get("active_set_id") or "")
        state["active_set_id"] = set_id
        set_evidence_membership(state, set_id, refs, include=True)
        bookmarks = set(state.get("bookmarks") or [])
        bookmarks.update(refs)
        state["bookmarks"] = sorted(bookmarks, key=str.lower)
        self._save_workspace_state()
        self._refresh_workspace_set_table()
        self._apply_workspace_filters()

    def _selected_set_ref(self) -> str:
        row = self.workspace_set_table.currentRow()
        if row < 0:
            return ""
        item = self.workspace_set_table.item(row, 0)
        if item is None:
            return ""
        return str(item.data(_ROLE_WORKSPACE_REF) or item.text() or "")

    def _remove_workspace_set_selection(self) -> None:
        state = getattr(self, "_workspace_state", None)
        if not isinstance(state, dict):
            return
        reference = self._selected_set_ref()
        if not reference:
            return
        set_id = str(self.workspace_set_combo.currentData() or "")
        set_evidence_membership(state, set_id, [reference], include=False)
        self._save_workspace_state()
        self._refresh_workspace_set_table()

    def _on_workspace_set_changed(self, _index: int) -> None:
        state = getattr(self, "_workspace_state", None)
        if not isinstance(state, dict):
            return
        state["active_set_id"] = str(self.workspace_set_combo.currentData() or "")
        self._save_workspace_state()
        self._refresh_workspace_set_table()

    def _refresh_workspace_set_table(self) -> None:
        model = getattr(self, "_workspace_model", {})
        rows_by_ref = model.get("rows_by_ref") if isinstance(model.get("rows_by_ref"), dict) else {}
        state = getattr(self, "_workspace_state", {})
        refs = active_evidence_refs(state) if isinstance(state, dict) else []
        self.workspace_set_table.setRowCount(len(refs))
        for row_index, reference in enumerate(refs):
            row = rows_by_ref.get(reference, {})
            values = [
                reference,
                str(row.get("target_utc") or row.get("host_utc") or ""),
                str(row.get("name") or row.get("kind") or ""),
                ", ".join(row.get("protocols") or []),
                f"{row.get('relation_type') or '—'} / {row.get('relation_strength') or '—'}",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(_ROLE_WORKSPACE_REF, reference)
                self.workspace_set_table.setItem(row_index, column, item)
        self.workspace_set_table.resizeColumnsToContents()
        self.workspace_remove_from_set.setEnabled(bool(refs))
        self.workspace_set_open_source.setEnabled(bool(refs))
        self.workspace_build_report.setEnabled(bool(refs))

    def _workspace_row_by_ref(self, reference: str) -> dict[str, Any] | None:
        model = getattr(self, "_workspace_model", {})
        rows_by_ref = model.get("rows_by_ref") if isinstance(model.get("rows_by_ref"), dict) else {}
        value = rows_by_ref.get(reference)
        return value if isinstance(value, dict) else None

    def _select_workspace_ref(self, reference: str) -> dict[str, Any] | None:
        row = self._workspace_row_by_ref(reference)
        if not isinstance(row, dict):
            return None
        self.workspace_search.setText(reference)
        self.tabs.setCurrentIndex(self.workspace_tab_index)
        for index in range(self.workspace_table.rowCount()):
            item = self.workspace_table.item(index, 0)
            candidate = item.data(_ROLE_WORKSPACE_ROW) if item is not None else None
            if isinstance(candidate, dict) and candidate.get("ref") == reference:
                self.workspace_table.selectRow(index)
                self.workspace_table.scrollToItem(item)
                break
        return row

    def _workspace_open_set_source(self) -> None:
        reference = self._selected_set_ref()
        row = self._select_workspace_ref(reference) if reference else None
        if isinstance(row, dict):
            self._select_source_row(row)

    def _build_workspace_report(self) -> None:
        model = getattr(self, "_workspace_model", None)
        state = getattr(self, "_workspace_state", None)
        if not isinstance(model, dict) or not isinstance(state, dict):
            return
        refs = active_evidence_refs(state)
        if not refs:
            return
        set_name = self.workspace_set_combo.currentText().strip() or "Evidence set"
        report = build_report_data(
            model,
            refs,
            archive=str(getattr(self, "_workspace_archive", "") or ""),
            title=f"apk-research — {set_name}",
        )
        self._workspace_report_data = report
        self.workspace_report.setPlainText(report_markdown(report))
        self.workspace_save_report_md.setEnabled(True)
        self.workspace_save_report_json.setEnabled(True)

    def _save_workspace_report_md(self) -> None:
        report = getattr(self, "_workspace_report_data", None)
        if not isinstance(report, dict):
            return
        default = Path(str(getattr(self, "_workspace_archive", "report.research.zip"))).with_suffix(".report.md")
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Сохранить отчёт",
            str(default),
            "Markdown (*.md);;All files (*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(report_markdown(report), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Отчёт", f"Не удалось сохранить отчёт:\n{exc}")

    def _save_workspace_report_json(self) -> None:
        report = getattr(self, "_workspace_report_data", None)
        if not isinstance(report, dict):
            return
        default = Path(str(getattr(self, "_workspace_archive", "report.research.zip"))).with_suffix(".report.json")
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Сохранить отчёт JSON",
            str(default),
            "JSON (*.json);;All files (*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            QMessageBox.warning(self, "Отчёт", f"Не удалось сохранить отчёт:\n{exc}")
