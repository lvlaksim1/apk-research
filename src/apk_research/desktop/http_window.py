from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import Qt
from apk_research.desktop.body_display import format_http_body, MAX_TEXT_BYTES

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QSpinBox,
    QMainWindow,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

TRANSACTIONS_ARTIFACT = "02_normalized/http-transactions.jsonl"
BODIES_PREFIX = "02_normalized/http-bodies/"


def load_http_transactions(
    archive_path: str | Path,
) -> list[dict]:
    path = Path(archive_path)
    with zipfile.ZipFile(path) as archive:
        try:
            raw = archive.read(
                TRANSACTIONS_ARTIFACT
            ).decode(
                "utf-8",
                errors="replace",
            )
        except KeyError:
            return []
    values: list[dict] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            values.append(value)
    return values


def _format_time(value) -> str:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return "—"
    dt = datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc,
    )
    return dt.strftime("%H:%M:%S.%f")[:-3]


def _header_text(headers) -> str:
    if not isinstance(headers, list):
        return ""
    lines: list[str] = []
    for item in headers:
        if (
            isinstance(item, list)
            and len(item) == 2
        ):
            lines.append(
                f"{item[0]}: {item[1]}"
            )
    return "\n".join(lines)


def _is_textual(content_type: str) -> bool:
    value = content_type.lower()
    return (
        value.startswith("text/")
        or "json" in value
        or "xml" in value
        or "javascript" in value
        or "x-www-form-urlencoded" in value
        or "graphql" in value
    )


def _decode_body(
    data: bytes,
    content_type: str,
    content_encoding: str = "",
    mode: str = "text",
    truncated: bool = False,
    page: int = 0,
) -> str:
    return format_http_body(
        data, content_type, content_encoding,
        mode=mode, truncated=truncated, page=page,
    )


class HttpTransactionsWindow(QMainWindow):
    def __init__(
        self,
        archive_path: str | Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.archive_path = Path(archive_path)
        self.transactions = load_http_transactions(
            self.archive_path
        )
        self.filtered: list[dict] = list(
            self.transactions
        )
        self._replay_dialogs: list = []
        self.setWindowTitle(
            "HTTP/HTTPS — " + self.archive_path.name
        )
        self.resize(1250, 780)
        self.setMinimumSize(900, 560)
        self._selected_preview_id = None
        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        top = QHBoxLayout()
        top.addWidget(QLabel("Поиск"))
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "URL, host, метод, код, заголовок…"
        )
        self.search.textChanged.connect(
            self._apply_filter
        )
        top.addWidget(self.search, 1)
        self.count_label = QLabel()
        top.addWidget(self.count_label)
        self.replay_button = QPushButton("Изменить и отправить…")
        self.replay_button.setToolTip(
            "Повторная отправка вручную; оригинальная запись и ZIP не меняются."
        )
        self.replay_button.setEnabled(False)
        self.replay_button.clicked.connect(self._open_replay_dialog)
        top.addWidget(self.replay_button)
        layout.addLayout(top)

        splitter = QSplitter(
            Qt.Orientation.Vertical
        )
        self.table = QTableWidget(
            0,
            8,
        )
        self.table.setHorizontalHeaderLabels(
            [
                "Время UTC",
                "HTTPS",
                "Метод",
                "Host",
                "Путь",
                "Код",
                "Тип",
                "Длительность",
            ]
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.currentCellChanged.connect(
            self._selection_changed
        )
        self.table.horizontalHeader().setStretchLastSection(
            True
        )
        splitter.addWidget(self.table)

        details = QWidget()
        details_layout = QVBoxLayout(details)
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMaximumHeight(120)
        details_layout.addWidget(self.summary)

        mode_line = QHBoxLayout()
        mode_line.addWidget(QLabel("Отображение тел:"))
        self.body_mode = QComboBox()
        self.body_mode.addItem("Текст (авто)", "text")
        self.body_mode.addItem("HEX", "hex")
        self.body_mode.setToolTip(
            "HEX показывает исходные байты без преобразований."
        )
        self.body_mode.currentIndexChanged.connect(
            self._body_mode_changed
        )
        mode_line.addWidget(self.body_mode)
        mode_line.addWidget(QLabel("Фрагмент:"))
        self.body_page = QSpinBox()
        self.body_page.setRange(1, 64)
        self.body_page.setValue(1)
        self.body_page.setToolTip(
            "Страницы распакованного текста по 128 КиБ; максимум 8 МиБ."
        )
        self.body_page.valueChanged.connect(self._body_mode_changed)
        mode_line.addWidget(self.body_page)
        mode_line.addStretch(1)
        details_layout.addLayout(mode_line)

        self.detail_tabs = QTabWidget()
        self.request_headers = QPlainTextEdit()
        self.request_body = QPlainTextEdit()
        self.response_headers = QPlainTextEdit()
        self.response_body = QPlainTextEdit()
        for widget in (
            self.request_headers,
            self.request_body,
            self.response_headers,
            self.response_body,
        ):
            widget.setReadOnly(True)
            widget.setLineWrapMode(
                QPlainTextEdit.LineWrapMode.NoWrap
            )
        self.detail_tabs.addTab(
            self.request_headers,
            "Заголовки запроса",
        )
        self.detail_tabs.addTab(
            self.request_body,
            "Тело запроса",
        )
        self.detail_tabs.addTab(
            self.response_headers,
            "Заголовки ответа",
        )
        self.detail_tabs.addTab(
            self.response_body,
            "Тело ответа",
        )
        details_layout.addWidget(
            self.detail_tabs,
            1,
        )
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

    def _populate(self, select_id: str | None = None) -> None:
        if select_id is None:
            select_id = self._selected_preview_id
        self.table.setRowCount(
            len(self.filtered)
        )
        for row, transaction in enumerate(
            self.filtered
        ):
            request = (
                transaction.get("request")
                or {}
            )
            response = (
                transaction.get("response")
                or {}
            )
            url = str(
                transaction.get("url")
                or ""
            )
            parsed = urlsplit(url)
            content_type = ""
            headers = response.get("headers")
            if isinstance(headers, list):
                for item in headers:
                    if (
                        isinstance(item, list)
                        and len(item) == 2
                        and str(item[0]).lower()
                        == "content-type"
                    ):
                        content_type = str(item[1])
                        break
            values = [
                _format_time(
                    transaction.get(
                        "timestamp_start"
                    )
                ),
                (
                    "да"
                    if (
                        transaction.get(
                            "interception"
                        )
                        or {}
                    ).get("tls_decrypted")
                    else "нет"
                ),
                ("↻ " if transaction.get("capture_mode") == "manual_replay" else "")
                + str(transaction.get("method") or ""),
                str(
                    transaction.get("host")
                    or parsed.hostname
                    or ""
                ),
                ("↻ " if transaction.get("capture_mode") == "manual_replay" else "")
                + parsed.path
                + (
                    ("?" + parsed.query)
                    if parsed.query
                    else ""
                ),
                str(
                    response.get("status_code")
                    if response
                    else transaction.get("state") or ""
                ),
                content_type,
                (
                    f"{transaction.get('duration_ms', 0)} ms"
                ),
            ]
            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    value
                )
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    row,
                )
                self.table.setItem(
                    row,
                    column,
                    item,
                )
        self.table.resizeColumnsToContents()
        self.count_label.setText(
            f"{len(self.filtered)} / {len(self.transactions)}"
        )
        if self.filtered:
            selected_row = next(
                (row for row, item in enumerate(self.filtered)
                 if item.get("transaction_id") == select_id),
                0,
            )
            self.table.selectRow(selected_row)
            self._show_transaction(self.filtered[selected_row])
        else:
            self._clear_details()

    def _apply_filter(
        self,
        text: str,
    ) -> None:
        needle = text.strip().lower()
        if not needle:
            self.filtered = list(
                self.transactions
            )
        else:
            values: list[dict] = []
            for transaction in self.transactions:
                haystack = json.dumps(
                    transaction, ensure_ascii=False,
                    default=lambda value: "" if isinstance(value, bytes) else str(value),
                ).lower()
                if transaction.get("capture_mode") == "manual_replay":
                    haystack += " повтор ↻ вручную"
                if needle in haystack:
                    values.append(transaction)
            self.filtered = values
        self._populate()

    def _selection_changed(
        self,
        current_row: int,
        _current_column: int,
        _previous_row: int,
        _previous_column: int,
    ) -> None:
        if (
            current_row < 0
            or current_row >= len(self.filtered)
        ):
            self._clear_details()
            return
        self._show_transaction(
            self.filtered[current_row]
        )

    def _show_transaction(
        self,
        transaction: dict,
    ) -> None:
        key = transaction.get("transaction_id") or id(transaction)
        if key != self._selected_preview_id:
            self._selected_preview_id = key
            self.body_page.blockSignals(True)
            self.body_page.setValue(1)
            self.body_page.blockSignals(False)
        request = (
            transaction.get("request")
            or {}
        )
        self.replay_button.setEnabled(
            str(transaction.get("url") or "").startswith("https://")
        )
        response = (
            transaction.get("response")
            or {}
        )
        summary = [
            f"ID: {transaction.get('transaction_id', '—')}",
            *(
                ["↻ Повторная отправка с компьютера (не в ZIP)"]
                if transaction.get("capture_mode") == "manual_replay" else []
            ),
            f"{transaction.get('method', '')} {transaction.get('url', '')}",
            (
                "Статус: "
                + (
                    str(
                        response.get(
                            "status_code"
                        )
                    )
                    if response
                    else str(
                        transaction.get(
                            "error"
                        )
                        or transaction.get(
                            "state"
                        )
                        or "—"
                    )
                )
            ),
            (
                "Протокол: "
                + str(
                    (
                        response.get(
                            "http_version"
                        )
                        if response
                        else None
                    )
                    or transaction.get(
                        "http_version"
                    )
                    or "—"
                )
            ),
            (
                "Активный HTTPS-перехват: "
                + (
                    "да"
                    if (
                        transaction.get(
                            "interception"
                        )
                        or {}
                    ).get("tls_decrypted")
                    else "нет"
                )
            ),
        ]
        self.summary.setPlainText(
            "\n".join(summary)
        )
        self.request_headers.setPlainText(
            _header_text(
                request.get("headers")
            )
        )
        self.response_headers.setPlainText(
            _header_text(
                response.get("headers")
                if response
                else []
            )
        )
        self.request_body.setPlainText(
            self._body_text(
                request.get("body")
                or {}
            )
        )
        self.response_body.setPlainText(
            self._body_text(
                (
                    response.get("body")
                    if response
                    else {}
                )
                or {}
            )
        )

    def _open_replay_dialog(self) -> None:
        row = self.table.currentRow()
        if not (0 <= row < len(self.filtered)):
            return
        from apk_research.desktop.replay_dialog import ReplayDialog
        dialog = ReplayDialog(
            self.filtered[row], archive_path=self.archive_path, parent=self
        )
        dialog.replayChanged.connect(self._upsert_replay_record)
        self._replay_dialogs.append(dialog)
        dialog.finished.connect(
            lambda _result, item=dialog: (
                self._replay_dialogs.remove(item)
                if item in self._replay_dialogs else None
            )
        )
        dialog.show()

    def _upsert_replay_record(self, record: dict) -> None:
        key = record.get("transaction_id")
        if record.get("capture_mode") != "manual_replay" or not key:
            return
        newly_added = True
        for index, existing in enumerate(self.transactions):
            if (existing.get("transaction_id") == key
                    and existing.get("capture_mode") == "manual_replay"):
                self.transactions[index] = record
                newly_added = False
                break
        if newly_added:
            self.transactions.append(record)
        self._apply_filter(self.search.text())
        if newly_added:
            for index, row in enumerate(self.filtered):
                if row.get("transaction_id") == key:
                    self.table.selectRow(index)
                    self._show_transaction(row)
                    break

    def _body_mode_changed(self, *_args) -> None:
        self.body_page.setEnabled(self.body_mode.currentData() == "text")
        row = self.table.currentRow()
        if 0 <= row < len(self.filtered):
            self._show_transaction(self.filtered[row])

    def _body_text(
        self,
        body: dict,
    ) -> str:
        data = body.get("_inline_bytes")
        if isinstance(data, bytes):
            return _decode_body(
                data,
                str(body.get("content_type") or ""),
                str(body.get("content_encoding") or ""),
                mode=str(self.body_mode.currentData() or "text"),
                truncated=bool(body.get("_limited")),
                page=self.body_page.value() - 1,
            )
        path = body.get("path")
        if not path:
            return ""
        member = BODIES_PREFIX + str(path)
        try:
            with zipfile.ZipFile(
                self.archive_path
            ) as archive:
                with archive.open(member) as reader:
                    data = reader.read(MAX_TEXT_BYTES + 1)
        except Exception as exc:
            return (
                "Не удалось прочитать тело: "
                + (str(exc) or exc.__class__.__name__)
            )
        return _decode_body(
            data[:MAX_TEXT_BYTES],
            str(body.get("content_type") or ""),
            str(body.get("content_encoding") or ""),
            mode=str(self.body_mode.currentData() or "text"),
            truncated=len(data) > MAX_TEXT_BYTES,
            page=self.body_page.value() - 1,
        )

    def _clear_details(self) -> None:
        self.replay_button.setEnabled(False)
        for widget in (
            self.summary,
            self.request_headers,
            self.request_body,
            self.response_headers,
            self.response_body,
        ):
            widget.clear()
