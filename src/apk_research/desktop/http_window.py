from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
) -> str:
    if not data:
        return ""
    if not _is_textual(content_type):
        preview = data[:4096].hex(" ")
        suffix = (
            ""
            if len(data) <= 4096
            else "\n… hex preview limited to 4096 bytes"
        )
        return (
            f"<binary body: {len(data)} bytes>\n"
            f"{preview}{suffix}"
        )
    text = data.decode(
        "utf-8",
        errors="replace",
    )
    if "json" in content_type.lower():
        try:
            value = json.loads(text)
        except Exception:
            return text
        return json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        )
    return text


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
        self.setWindowTitle(
            "HTTP/HTTPS — " + self.archive_path.name
        )
        self.resize(1250, 780)
        self.setMinimumSize(900, 560)
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

    def _populate(self) -> None:
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
                str(
                    transaction.get("method")
                    or ""
                ),
                str(
                    transaction.get("host")
                    or parsed.hostname
                    or ""
                ),
                parsed.path
                + (
                    ("?" + parsed.query)
                    if parsed.query
                    else ""
                ),
                str(
                    response.get("status_code")
                    if response
                    else transaction.get(
                        "state"
                    )
                    or ""
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
            self.table.selectRow(0)
            self._show_transaction(
                self.filtered[0]
            )
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
                    transaction,
                    ensure_ascii=False,
                ).lower()
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
        request = (
            transaction.get("request")
            or {}
        )
        response = (
            transaction.get("response")
            or {}
        )
        summary = [
            f"ID: {transaction.get('transaction_id', '—')}",
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

    def _body_text(
        self,
        body: dict,
    ) -> str:
        path = body.get("path")
        if not path:
            return ""
        member = BODIES_PREFIX + str(path)
        try:
            with zipfile.ZipFile(
                self.archive_path
            ) as archive:
                data = archive.read(member)
        except Exception as exc:
            return (
                "Не удалось прочитать тело: "
                + (str(exc) or exc.__class__.__name__)
            )
        return _decode_body(
            data,
            str(
                body.get("content_type")
                or ""
            ),
        )

    def _clear_details(self) -> None:
        for widget in (
            self.summary,
            self.request_headers,
            self.request_body,
            self.response_headers,
            self.response_body,
        ):
            widget.clear()
