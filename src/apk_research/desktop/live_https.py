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

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
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
        self.filtered_indices: list[int] = []
        self._sort_column = 0
        self._sort_ascending = False

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
            ["Время", "Метод", "Сервер", "Адрес запроса", "Ответ"]
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
        splitter.addWidget(self.details_tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)

        self.note = QLabel(
            "Начните исследование — запросы появятся автоматически. "
            "Все данные сохраняются в Research ZIP."
        )
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.refresh)

    def _clear(self) -> None:
        self.transactions.clear()
        self.filtered_indices.clear()
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
        self.note.setText("● Исследование идёт — новые ответы появляются автоматически.")
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

    def _sort_by_column(self, column: int) -> None:
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
            if not query or query in (
                str(item.get("url", "")) + " "
                + str(item.get("method", "")) + " "
                + str((item.get("response") or {}).get("status_code", ""))
            ).casefold()
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
            if restore >= 0:
                self.table.selectRow(restore)
            elif indices and selected_id is None:
                self.table.selectRow(0)
        finally:
            self.table.blockSignals(previous_signals)
            self.table.setUpdatesEnabled(True)
        if restore >= 0:
            self._show_selected(restore)
        elif not indices:
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
        truncated = len(value) > MAX_PREVIEW_BYTES
        preview = _decode_body(value[:MAX_PREVIEW_BYTES], content_type)
        if truncated:
            preview += "\n\n… Предпросмотр ограничен 128 КБ; полное тело сохранено в ZIP."
        return preview
