from __future__ import annotations

import base64
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from apk_research.collectors import (
    HTTPS_INTERCEPTION_ARTIFACT,
    HTTPS_TRANSACTIONS_ARTIFACT,
)


_ROLE_TRANSACTION = int(Qt.ItemDataRole.UserRole)


def load_https_capture(
    archive_path: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    archive = Path(archive_path)
    with zipfile.ZipFile(archive) as handle:
        try:
            state = json.loads(
                handle.read(
                    HTTPS_INTERCEPTION_ARTIFACT
                ).decode("utf-8")
            )
        except KeyError:
            state = {}

        try:
            raw = handle.read(
                HTTPS_TRANSACTIONS_ARTIFACT
            ).decode(
                "utf-8",
                errors="replace",
            )
        except KeyError:
            raw = ""

    transactions: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            transactions.append(value)

    return (
        state if isinstance(state, dict) else {},
        transactions,
    )


def _header_value(
    headers: Any,
    name: str,
) -> str:
    target = name.lower()
    if not isinstance(headers, list):
        return ""
    for item in headers:
        if (
            isinstance(item, list)
            and len(item) >= 2
            and str(item[0]).lower() == target
        ):
            return str(item[1])
    return ""


def _header_text(headers: Any) -> str:
    if not isinstance(headers, list):
        return ""
    rows: list[str] = []
    for item in headers:
        if (
            isinstance(item, list)
            and len(item) >= 2
        ):
            rows.append(
                f"{item[0]}: {item[1]}"
            )
    return "\n".join(rows)


def _decode_body(
    body: Any,
    headers: Any,
) -> tuple[str, bytes]:
    if not isinstance(body, dict):
        return "", b""
    encoded = str(body.get("base64") or "")
    try:
        raw = base64.b64decode(
            encoded,
            validate=True,
        )
    except Exception:
        raw = b""

    if not raw:
        return "(пустое тело)", raw

    content_type = _header_value(
        headers,
        "content-type",
    )
    lowered = content_type.lower()
    charset = "utf-8"
    match = re.search(
        r"charset\s*=\s*['\"]?([^;\s'\"]+)",
        content_type,
        flags=re.IGNORECASE,
    )
    if match:
        charset = match.group(1)

    textual = (
        lowered.startswith("text/")
        or "json" in lowered
        or "xml" in lowered
        or "javascript" in lowered
        or "x-www-form-urlencoded" in lowered
        or "graphql" in lowered
    )
    if not textual:
        stripped = raw.lstrip()
        if stripped.startswith((b"{", b"[")):
            textual = True

    if textual:
        try:
            text = raw.decode(
                charset,
                errors="replace",
            )
        except LookupError:
            text = raw.decode(
                "utf-8",
                errors="replace",
            )

        if "json" in lowered or raw.lstrip().startswith(
            (b"{", b"[")
        ):
            try:
                parsed = json.loads(text)
                text = json.dumps(
                    parsed,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            except Exception:
                pass
        return text, raw

    return (
        "Двоичное тело: "
        f"{len(raw)} байт\n\n"
        "Base64:\n"
        + base64.b64encode(raw).decode("ascii"),
        raw,
    )


def transaction_search_text(
    transaction: dict[str, Any],
) -> str:
    response = (
        transaction.get("response")
        if isinstance(
            transaction.get("response"),
            dict,
        )
        else {}
    )
    request_text, _ = _decode_body(
        transaction.get("request_body"),
        transaction.get("request_headers"),
    )
    response_text, _ = _decode_body(
        response.get("body"),
        response.get("headers"),
    )
    parts = [
        str(transaction.get("transaction_id") or ""),
        str(transaction.get("request_started_utc") or ""),
        str(transaction.get("method") or ""),
        str(transaction.get("url") or ""),
        str(transaction.get("host") or ""),
        str(transaction.get("path") or ""),
        str(response.get("status_code") or ""),
        _header_text(
            transaction.get("request_headers")
        ),
        _header_text(response.get("headers")),
        request_text,
        response_text,
        str(transaction.get("error") or ""),
    ]
    return "\n".join(parts).lower()


def format_transaction(
    transaction: dict[str, Any],
) -> tuple[str, str, str]:
    response = (
        transaction.get("response")
        if isinstance(
            transaction.get("response"),
            dict,
        )
        else {}
    )
    request_headers = transaction.get(
        "request_headers"
    )
    response_headers = response.get("headers")
    request_body_text, request_body = _decode_body(
        transaction.get("request_body"),
        request_headers,
    )
    response_body_text, response_body = _decode_body(
        response.get("body"),
        response_headers,
    )

    request_line = (
        f"{transaction.get('method') or ''} "
        f"{transaction.get('url') or ''} "
        f"{transaction.get('http_version') or ''}"
    ).strip()
    request = (
        request_line
        + "\n"
        + _header_text(request_headers)
        + "\n\n"
        + request_body_text
    )

    if response:
        response_line = (
            f"{response.get('http_version') or ''} "
            f"{response.get('status_code') or ''} "
            f"{response.get('reason') or ''}"
        ).strip()
        response_text = (
            response_line
            + "\n"
            + _header_text(response_headers)
            + "\n\n"
            + response_body_text
        )
    else:
        response_text = (
            "Ответ не получен.\n"
            + str(
                transaction.get("error")
                or "Причина не зафиксирована."
            )
        )

    summary = {
        "transaction_id": transaction.get(
            "transaction_id"
        ),
        "capture_mode": transaction.get(
            "capture_mode"
        ),
        "intervention": transaction.get(
            "intervention"
        ),
        "request_started_utc": transaction.get(
            "request_started_utc"
        ),
        "request_ended_utc": transaction.get(
            "request_ended_utc"
        ),
        "request_body_bytes": len(request_body),
        "response_started_utc": response.get(
            "started_utc"
        ),
        "response_ended_utc": response.get(
            "ended_utc"
        ),
        "response_body_bytes": len(response_body),
        "tls": transaction.get("tls"),
        "error": transaction.get("error"),
    }
    return (
        request,
        response_text,
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
    )


class HttpsTrafficWindow(QMainWindow):
    def __init__(
        self,
        archive_path: str | Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.archive_path = str(
            Path(archive_path)
        )
        self.state, self.transactions = (
            load_https_capture(
                self.archive_path
            )
        )
        self.filtered: list[
            dict[str, Any]
        ] = list(self.transactions)

        self.setWindowTitle(
            "HTTPS Traffic — apk-research"
        )
        self.resize(1320, 820)
        self.setMinimumSize(980, 620)
        self._build_ui()
        self._apply_filter()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        scope = self.state.get(
            "evidence_semantics"
        )
        state_status = str(
            self.state.get("status")
            or "нет данных"
        )
        self.summary = QLabel(
            "HTTPS interception: "
            f"{state_status}. "
            "Это активное доказательство: прокси и исследовательский CA "
            "изменяют сетевую среду. "
            "Принадлежность каждой HTTP-транзакции пакету сама по себе "
            "не доказывается."
        )
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Поиск: URL / метод / статус / заголовок / тело"
        )
        self.count_label = QLabel()
        search_row.addWidget(
            self.search,
            1,
        )
        search_row.addWidget(
            self.count_label
        )
        root.addLayout(search_row)

        splitter = QSplitter(
            Qt.Orientation.Vertical
        )
        self.table = QTableWidget(
            0,
            9,
        )
        self.table.setHorizontalHeaderLabels(
            [
                "UTC",
                "Method",
                "Host",
                "Path",
                "Status",
                "Type",
                "Request",
                "Response",
                "HTTP",
            ]
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(
            False
        )
        self.table.horizontalHeader().setStretchLastSection(
            True
        )
        splitter.addWidget(self.table)

        self.details_tabs = QTabWidget()
        self.request_text = QPlainTextEdit()
        self.response_text = QPlainTextEdit()
        self.meta_text = QPlainTextEdit()
        for editor in (
            self.request_text,
            self.response_text,
            self.meta_text,
        ):
            editor.setReadOnly(True)
        self.details_tabs.addTab(
            self.request_text,
            "Request",
        )
        self.details_tabs.addTab(
            self.response_text,
            "Response",
        )
        self.details_tabs.addTab(
            self.meta_text,
            "Metadata",
        )
        splitter.addWidget(
            self.details_tabs
        )
        splitter.setSizes(
            [420, 320]
        )
        root.addWidget(
            splitter,
            1,
        )

        self.search.textChanged.connect(
            self._apply_filter
        )
        self.table.itemSelectionChanged.connect(
            self._show_selected
        )
        self.setCentralWidget(central)

    def _apply_filter(self) -> None:
        needle = (
            self.search.text()
            .strip()
            .lower()
        )
        if needle:
            self.filtered = [
                transaction
                for transaction in self.transactions
                if needle
                in transaction_search_text(
                    transaction
                )
            ]
        else:
            self.filtered = list(
                self.transactions
            )

        self.table.setRowCount(
            len(self.filtered)
        )
        for row, transaction in enumerate(
            self.filtered
        ):
            response = (
                transaction.get("response")
                if isinstance(
                    transaction.get("response"),
                    dict,
                )
                else {}
            )
            response_headers = response.get(
                "headers"
            )
            content_type = _header_value(
                response_headers,
                "content-type",
            )
            req_body = transaction.get(
                "request_body"
            )
            resp_body = response.get(
                "body"
            )
            values = [
                str(
                    transaction.get(
                        "request_started_utc"
                    )
                    or ""
                ),
                str(
                    transaction.get("method")
                    or ""
                ),
                str(
                    transaction.get("host")
                    or ""
                ),
                str(
                    transaction.get("path")
                    or ""
                ),
                str(
                    response.get("status_code")
                    or ""
                ),
                content_type,
                str(
                    (
                        req_body.get("size")
                        if isinstance(
                            req_body,
                            dict,
                        )
                        else 0
                    )
                    or 0
                ),
                str(
                    (
                        resp_body.get("size")
                        if isinstance(
                            resp_body,
                            dict,
                        )
                        else 0
                    )
                    or 0
                ),
                str(
                    response.get("http_version")
                    or transaction.get(
                        "http_version"
                    )
                    or ""
                ),
            ]
            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    value
                )
                if column == 0:
                    item.setData(
                        _ROLE_TRANSACTION,
                        transaction,
                    )
                self.table.setItem(
                    row,
                    column,
                    item,
                )

        self.count_label.setText(
            f"{len(self.filtered)} / "
            f"{len(self.transactions)}"
        )
        self.table.resizeColumnsToContents()
        if self.filtered:
            self.table.selectRow(0)
        else:
            self.request_text.clear()
            self.response_text.clear()
            self.meta_text.clear()

    def _show_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(
            row,
            0,
        )
        if item is None:
            return
        transaction = item.data(
            _ROLE_TRANSACTION
        )
        if not isinstance(
            transaction,
            dict,
        ):
            return
        request, response, metadata = (
            format_transaction(
                transaction
            )
        )
        self.request_text.setPlainText(
            request
        )
        self.response_text.setPlainText(
            response
        )
        self.meta_text.setPlainText(
            metadata
        )
