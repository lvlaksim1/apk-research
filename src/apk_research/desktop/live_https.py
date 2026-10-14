"""Minimal live HTTPS view for one current research session.

Live mode reads only completed JSONL records from the existing local session
folder. Archive mode reads the exact Research ZIP; no network calls or data
collection takes place in the UI thread.
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import Qt, QTimer, Signal, QPoint
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QComboBox, QSpinBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
    QMenu, QWidgetAction,
    QVBoxLayout, QWidget,
)

from apk_research.desktop.live_https_reader import IncrementalHttpReader
from apk_research.desktop.http_window import (
    _decode_body, _header_text, TRANSACTIONS_ARTIFACT, BODIES_PREFIX,
)

MAX_PREVIEW_BYTES = 128 * 1024
class LiveHttpsView(QWidget):
    """Read-only live display of requests and responses for current session."""

    countChanged = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.session_root: Path | None = None
        self.archive_path: Path | None = None
        self._reader: IncrementalHttpReader | None = None
        self.transactions: list[dict] = []
        self._selected_preview_id = None
        self.filtered_indices: list[int] = []
        self._sort_column = 0
        self._sort_ascending = False
        self._method_filter: set[str] | None = None
        self._domain_filter: set[str] | None = None

        outer = QVBoxLayout(self)
        header = QHBoxLayout()
        self.title = QLabel("HTTPS-запросы исследуемого приложения")
        self.title.setStyleSheet("font-weight: 600;")
        header.addWidget(self.title)
        header.addStretch(1)
        self.count = QLabel("0 запросов")
        header.addWidget(self.count)
        outer.addLayout(header)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по адресу, методу, коду ответа…")
        self.search.textChanged.connect(self._apply_filter)
        search_row.addWidget(self.search, 1)
        self.open_archive_button = QPushButton("Открыть сохранённый ZIP…")
        self.open_archive_button.clicked.connect(self._choose_archive)
        search_row.addWidget(self.open_archive_button)
        outer.addLayout(search_row)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Время", "Метод ▾", "Сервер", "Адрес запроса ▾", "Ответ"]
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(
            3, self.table.horizontalHeader().ResizeMode.Stretch
        )
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(0, Qt.SortOrder.DescendingOrder)
        header.sectionClicked.connect(self._sort_by_column)
        self.table.currentCellChanged.connect(self._show_selected)
        splitter.addWidget(self.table)

        details_container = QWidget()
        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(4)
        mode_line = QHBoxLayout()
        mode_line.addWidget(QLabel("Отображение тел:"))
        self.body_mode = QComboBox()
        self.body_mode.addItem("Текст (авто)", "text")
        self.body_mode.addItem("HEX", "hex")
        self.body_mode.setToolTip(
            "HEX показывает сохранённые байты без распаковки."
        )
        self.body_mode.currentIndexChanged.connect(
            self._body_mode_changed
        )
        mode_line.addWidget(self.body_mode)
        mode_line.addWidget(QLabel("Фрагмент:"))
        self.body_page = QSpinBox()
        self.body_page.setRange(1, 64)
        self.body_page.setToolTip(
            "Страницы распакованного текста по 128 КиБ, до 8 МиБ."
        )
        self.body_page.valueChanged.connect(self._body_mode_changed)
        mode_line.addWidget(self.body_page)
        mode_line.addStretch(1)
        details_layout.addLayout(mode_line)

        self.details_tabs = QTabWidget()
        self.info = QPlainTextEdit()
        self.request_headers = QPlainTextEdit()
        self.request_body = QPlainTextEdit()
        self.response_headers = QPlainTextEdit()
        self.response_body = QPlainTextEdit()
        for widget in (
            self.info, self.request_headers, self.request_body,
            self.response_headers, self.response_body,
        ):
            widget.setReadOnly(True)
            widget.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        for label, widget in (
            ("Сведения", self.info),
            ("Заголовки запроса", self.request_headers),
            ("Тело запроса", self.request_body),
            ("Заголовки ответа", self.response_headers),
            ("Тело ответа", self.response_body),
        ):
            self.details_tabs.addTab(widget, label)
        details_layout.addWidget(self.details_tabs, 1)
        splitter.addWidget(details_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)

        self.note = QLabel(
            "Начните анализ HTTPS — запросы появятся автоматически. "
            "Запись ZIP включается отдельной кнопкой."
        )
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.refresh)

    def _clear(self) -> None:
        self.transactions.clear()
        self.filtered_indices.clear()
        self._selected_preview_id = None
        self.body_page.blockSignals(True)
        self.body_page.setValue(1)
        self.body_page.blockSignals(False)
        self._method_filter = None
        self._domain_filter = None
        self._update_filter_titles()
        self.table.setRowCount(0)
        for field in (
            self.info, self.request_headers, self.request_body,
            self.response_headers, self.response_body,
        ):
            field.clear()
        self.count.setText("0 запросов")
        self.countChanged.emit(0)

    def begin_session(self, root: str | Path, package: str) -> None:
        self.timer.stop()
        self._clear()
        self.session_root = Path(root).resolve()
        self.archive_path = None
        self._reader = IncrementalHttpReader(
            self.session_root / TRANSACTIONS_ARTIFACT
        )
        self.title.setText(f"HTTPS • {package}")
        self.note.setText("● Анализ HTTPS включён. Запись ZIP управляется отдельно.")
        self.timer.start()
        self.refresh()

    def refresh(self) -> None:
        if self._reader is None:
            return
        records = self._reader.poll()
        if records:
            self.transactions.extend(records)
            self._apply_filter()
            self.countChanged.emit(len(self.transactions))
        invalid = self._reader.invalid_records
        self.count.setText(
            f"{len(self.transactions)} запросов"
            + (f" · ошибок чтения: {invalid}" if invalid else "")
        )

    def finish_session(self, archive: str | Path | None) -> None:
        self.refresh()
        self.timer.stop()
        if archive and Path(archive).is_file():
            self.load_archive(archive)
            self.note.setText(
                "Исследование завершено. Показаны данные сохранённого Research ZIP."
            )
        else:
            self.note.setText(
                "Запись завершена; архив пока недоступен. "
                "Сохранённые в сеансе запросы оставлены на экране."
            )

    def load_archive(self, archive: str | Path) -> None:
        path = Path(archive).resolve()
        with zipfile.ZipFile(path) as content:
            raw = content.read(TRANSACTIONS_ARTIFACT)
        records = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if isinstance(item, dict):
                records.append(item)
        self.timer.stop()
        self._reader = None
        self.session_root = None
        self.archive_path = path
        self._clear()
        self.transactions = records
        self.title.setText("HTTPS • " + path.name)
        self._apply_filter()
        self.count.setText(f"{len(self.transactions)} запросов")
        self.countChanged.emit(len(self.transactions))

    def _choose_archive(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите Research ZIP", "",
            "Исследования (*.research.zip *.zip)"
        )
        if not path:
            return
        try:
            self.load_archive(path)
            self.note.setText("Просмотр сохранённого Research ZIP.")
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            self.note.setText("Не удалось открыть архив: " + str(exc))

    @staticmethod
    def _domain(item: dict) -> str:
        url = urlsplit(str(item.get("url") or ""))
        return str(url.hostname or item.get("host") or "").casefold()

    def _filter_options(self, column: int) -> list[str]:
        if column == 1:
            return sorted({
                str(item.get("method") or "—").upper()
                for item in self.transactions
            })
        return sorted({self._domain(item) for item in self.transactions if self._domain(item)})

    def _update_filter_titles(self) -> None:
        method = "Метод ▾" + (" •" if self._method_filter is not None else "")
        domain = "Адрес запроса ▾" + (" •" if self._domain_filter is not None else "")
        self.table.setHorizontalHeaderLabels(
            ["Время", method, "Сервер", domain, "Ответ"]
        )

    def _set_column_filter(self, column: int, selected: set[str] | None) -> None:
        if column == 1:
            self._method_filter = None if selected is None else set(selected)
        elif column == 3:
            self._domain_filter = None if selected is None else set(selected)
        else:
            raise ValueError("Filtering is supported for Method and Address")
        self._update_filter_titles()
        self._apply_filter()

    def _show_filter_menu(self, column: int) -> None:
        options = self._filter_options(column)
        current = self._method_filter if column == 1 else self._domain_filter
        menu = QMenu(self)
        search = QLineEdit(menu)
        search.setPlaceholderText(
            "Найти метод…" if column == 1 else "Найти домен…"
        )
        search_action = QWidgetAction(menu)
        search_action.setDefaultWidget(search)
        menu.addAction(search_action)
        all_action = menu.addAction("Выбрать все")
        all_action.triggered.connect(
            lambda: self._set_column_filter(column, None)
        )
        none_action = menu.addAction("Снять все")
        none_action.triggered.connect(
            lambda: self._set_column_filter(column, set())
        )
        menu.addSeparator()
        options_actions = []
        for value in options:
            action = menu.addAction(value)
            action.setCheckable(True)
            action.setChecked(current is None or value in current)
            def selected(checked=False, key=value):
                current_filter = (
                    self._method_filter if column == 1
                    else self._domain_filter
                )
                next_values = (
                    set(options) if current_filter is None
                    else set(current_filter)
                )
                if checked:
                    next_values.add(key)
                else:
                    next_values.discard(key)
                self._set_column_filter(column, next_values)
            action.toggled.connect(selected)
            options_actions.append(action)
        search.textChanged.connect(
            lambda query: [
                action.setVisible(query.casefold() in action.text().casefold())
                for action in options_actions
            ]
        )
        header = self.table.horizontalHeader()
        pos = QPoint(header.sectionViewportPosition(column), header.height())
        menu.exec(header.mapToGlobal(pos))

    def _sort_by_column(self, column: int) -> None:
        if column in (1, 3):
            self._show_filter_menu(column)
            return
        if column == self._sort_column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True
        self.table.horizontalHeader().setSortIndicator(
            column,
            (Qt.SortOrder.AscendingOrder if self._sort_ascending
             else Qt.SortOrder.DescendingOrder),
        )
        self._apply_filter()

    @staticmethod
    def _sort_value(item: dict, column: int):
        if column == 0:
            try:
                return float(item.get("timestamp_start") or 0)
            except (TypeError, ValueError):
                return 0.0
        if column == 4:
            try:
                return int((item.get("response") or {}).get("status_code") or 0)
            except (TypeError, ValueError):
                return 0
        if column == 1:
            return str(item.get("method") or "").casefold()
        url = urlsplit(str(item.get("url") or ""))
        if column == 2:
            return str(item.get("host") or url.hostname or "").casefold()
        return (url.path + (("?" + url.query) if url.query else "")).casefold()

    def _apply_filter(self, *_args) -> None:
        query = self.search.text().strip().casefold()
        indices = [
            i for i, item in enumerate(self.transactions)
            if (
                (self._method_filter is None
                 or str(item.get("method") or "—").upper() in self._method_filter)
                and (self._domain_filter is None
                     or self._domain(item) in self._domain_filter)
                and (
                    not query or query in (
                        str(item.get("url", "")) + " "
                        + str(item.get("method", "")) + " "
                        + str((item.get("response") or {}).get("status_code", ""))
                    ).casefold()
                )
            )
        ]
        indices.sort(
            key=lambda i: (self._sort_value(self.transactions[i], self._sort_column), i),
            reverse=not self._sort_ascending,
        )
        self.filtered_indices = indices
        selected = self.table.currentRow()
        selected_id = (
            self.table.item(selected, 0).data(Qt.ItemDataRole.UserRole)
            if selected >= 0 and self.table.item(selected, 0) else None
        )
        self.table.setUpdatesEnabled(False)
        previous_signals = self.table.blockSignals(True)
        restore = -1
        try:
            self.table.setRowCount(len(indices))
            for row, index in enumerate(indices):
                record = self.transactions[index]
                try:
                    time_text = datetime.fromtimestamp(
                        float(record.get("timestamp_start", 0))
                    ).strftime("%H:%M:%S")
                except (TypeError, ValueError, OverflowError, OSError):
                    time_text = "—"
                url = str(record.get("url") or "")
                parsed = urlsplit(url)
                values = [
                    time_text,
                    str(record.get("method") or "—"),
                    str(record.get("host") or parsed.hostname or "—"),
                    parsed.path + (("?" + parsed.query) if parsed.query else ""),
                    str((record.get("response") or {}).get("status_code") or "Ошибка"),
                ]
                for col, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    cell.setToolTip(url)
                    if col == 0:
                        cell.setData(Qt.ItemDataRole.UserRole, index)
                    self.table.setItem(row, col, cell)
                if index == selected_id:
                    restore = row
            if restore < 0 and indices:
                restore = 0
            if restore >= 0:
                self.table.selectRow(restore)
        finally:
            self.table.blockSignals(previous_signals)
            self.table.setUpdatesEnabled(True)
        if restore >= 0:
            self._show_selected(restore)
        else:
            for field in (
                self.info, self.request_headers, self.request_body,
                self.response_headers, self.response_body,
            ):
                field.clear()

    def _show_selected(self, row: int, *_args) -> None:
        if row < 0:
            return
        first = self.table.item(row, 0)
        if first is None:
            return
        index = first.data(Qt.ItemDataRole.UserRole)
        if not isinstance(index, int) or not (0 <= index < len(self.transactions)):
            return
        record = self.transactions[index]
        key = record.get("transaction_id") or id(record)
        if key != self._selected_preview_id:
            self._selected_preview_id = key
            self.body_page.blockSignals(True)
            self.body_page.setValue(1)
            self.body_page.blockSignals(False)
        request = record.get("request") or {}
        response = record.get("response") or {}
        self.info.setPlainText(
            str(record.get("method") or "") + " " + str(record.get("url") or "")
            + "\nHTTP: " + str(response.get("status_code") or "Ошибка")
            + "\nДлительность: " + str(record.get("duration_ms") or 0) + " мс"
            + ("\nОшибка: " + str(record.get("error")) if record.get("error") else "")
        )
        self.request_headers.setPlainText(_header_text(request.get("headers")))
        self.response_headers.setPlainText(_header_text(response.get("headers")))
        self.request_body.setPlainText(self._body_preview(request.get("body")))
        self.response_body.setPlainText(self._body_preview(response.get("body")))

    def _body_mode_changed(self, *_args) -> None:
        self.body_page.setEnabled(self.body_mode.currentData() == "text")
        row = self.table.currentRow()
        if row >= 0:
            self._show_selected(row)

    def _body_preview(self, details) -> str:
        if not isinstance(details, dict) or not details.get("present"):
            return "Тело отсутствует"
        name = details.get("path")
        if not isinstance(name, str) or not name or Path(name).name != name:
            return "Путь к телу ответа не подтверждён"
        try:
            if self.archive_path is not None:
                with zipfile.ZipFile(self.archive_path) as archive:
                    with archive.open(BODIES_PREFIX + name) as stream:
                        value = stream.read(MAX_PREVIEW_BYTES + 1)
            elif self.session_root is not None:
                path = self.session_root / "02_normalized/http-bodies" / name
                with path.open("rb") as stream:
                    value = stream.read(MAX_PREVIEW_BYTES + 1)
            else:
                return "Данные недоступны"
        except (OSError, KeyError, zipfile.BadZipFile):
            return "Тело пока недоступно"
        content_type = str(details.get("content_type") or "")
        content_encoding = str(details.get("content_encoding") or "")
        truncated = len(value) > MAX_PREVIEW_BYTES
        return _decode_body(
            value[:MAX_PREVIEW_BYTES],
            content_type,
            content_encoding,
            mode=str(self.body_mode.currentData() or "text"),
            truncated=truncated,
            page=self.body_page.value() - 1,
        )
