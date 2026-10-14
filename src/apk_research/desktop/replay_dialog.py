"""Editable HTTPS request replay dialog; intentionally detached from evidence."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from apk_research.desktop.body_display import format_http_body
from apk_research.desktop.request_replay import (
    ReplayError, ReplayResult, perform_replay, read_captured_body,
)


def _headers_list(value) -> list[tuple[str, str]]:
    if not isinstance(value, list):
        return []
    return [(str(k), str(v)) for entry in value
            if isinstance(entry, (list, tuple)) and len(entry) == 2
            for k, v in [entry]]


def _body_for_editor(data: bytes) -> tuple[str, str]:
    """Pretty JSON; unknown binary never silently converted or corrupted."""
    try:
        decoded = data.decode("utf-8-sig", "strict")
        if any(not x.isprintable() and x not in "\r\n\t" for x in decoded):
            raise UnicodeError("binary")
    except UnicodeError:
        return "hex", data.hex(" ")
    try:
        parsed = json.loads(decoded)
    except (json.JSONDecodeError, ValueError):
        return "text", decoded
    return "text", json.dumps(parsed, ensure_ascii=False, indent=2)


def _edited_bytes(text: str, mode: str) -> bytes:
    if mode == "hex":
        try:
            return bytes.fromhex(text)
        except ValueError as exc:
            raise ReplayError("Некорректное шестнадцатеричное тело запроса.") from exc
    return text.encode("utf-8")


class _ReplayWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, arguments: tuple, parent=None) -> None:
        super().__init__(parent)
        self.arguments = arguments

    def run(self) -> None:
        try:
            result = perform_replay(*self.arguments)
        except (ReplayError, ValueError) as exc:
            self.failed.emit(str(exc))
        except Exception:
            # Never expose secrets from connection diagnostics or tracebacks.
            self.failed.emit("Непредвиденная ошибка выполнения HTTPS-запроса.")
        else:
            self.succeeded.emit(result)


class ReplayDialog(QDialog):
    """One manually submitted request. No edits to session or ZIP."""

    def __init__(self, record: dict, archive_path: Path | None = None,
                 session_root: Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Изменить и повторить HTTPS-запрос")
        self.resize(900, 710)
        self._record = record
        self._original_url = str(record.get("url") or "")
        self._original_headers = _headers_list(
            (record.get("request") or {}).get("headers")
        )
        self._worker: _ReplayWorker | None = None
        self._result: ReplayResult | None = None
        try:
            initial = read_captured_body(record, archive_path, session_root)
            self._load_error = ""
        except ReplayError as exc:
            initial = b""
            self._load_error = str(exc)
        text_mode, initial_text = _body_for_editor(initial)
        layout = QVBoxLayout(self)

        description = QLabel(
            "Запрос отправляется с этого компьютера напрямую на сервер по HTTPS. "
            "Исходный запрос и ZIP не меняются. Действие может изменить "
            "данные на сервере; автоматических повторов и переходов по ссылкам нет."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        self.method = QComboBox()
        self.method.setEditable(True)
        self.method.addItems(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
        self.method.setCurrentText(str(record.get("method") or "GET").upper())
        form.addRow("Метод:", self.method)
        self.url = QLineEdit(self._original_url)
        self.url.setToolTip(
            "Разрешён исходный сервер или сохранённый Host; другой порт запрещён."
        )
        form.addRow("Адрес:", self.url)
        layout.addLayout(form)

        self.tabs = QTabWidget()
        self.headers = QPlainTextEdit()
        self.headers.setPlaceholderText("Каждый заголовок с новой строки: Имя: значение")
        self.headers.setPlainText(
            "\n".join(f"{k}: {v}" for k, v in self._original_headers)
        )
        self.tabs.addTab(self.headers, "Заголовки запроса")

        request_page = QWidget()
        request_layout = QVBoxLayout(request_page)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Редактирование:"))
        self.request_mode = QComboBox()
        self.request_mode.addItem("Текст / JSON", "text")
        self.request_mode.addItem("HEX", "hex")
        self.request_mode.setCurrentIndex(1 if text_mode == "hex" else 0)
        self.request_mode.currentIndexChanged.connect(self._convert_request_mode)
        mode_row.addWidget(self.request_mode)
        mode_row.addStretch()
        request_layout.addLayout(mode_row)
        self.request_body = QPlainTextEdit(initial_text)
        self.request_body.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        request_layout.addWidget(self.request_body)
        self.tabs.addTab(request_page, "Тело запроса")

        self.response_headers = QPlainTextEdit()
        self.response_headers.setReadOnly(True)
        self.tabs.addTab(self.response_headers, "Заголовки нового ответа")

        response_page = QWidget()
        response_layout = QVBoxLayout(response_page)
        response_row = QHBoxLayout()
        self.response_mode = QComboBox()
        self.response_mode.addItem("Текст (авто)", "text")
        self.response_mode.addItem("HEX", "hex")
        self.response_mode.currentIndexChanged.connect(self._render_response)
        response_row.addWidget(self.response_mode)
        response_row.addWidget(QLabel("Фрагмент:"))
        self.response_page = QSpinBox()
        self.response_page.setRange(1, 64)
        self.response_page.valueChanged.connect(self._render_response)
        response_row.addWidget(self.response_page)
        response_row.addStretch()
        response_layout.addLayout(response_row)
        self.response_body = QPlainTextEdit()
        self.response_body.setReadOnly(True)
        self.response_body.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        response_layout.addWidget(self.response_body)
        self.tabs.addTab(response_page, "Тело нового ответа")
        layout.addWidget(self.tabs, 1)

        self.status = QLabel(
            "Проверьте URL, заголовки, тело и действие перед отправкой. "
            "Content-Length и Content-Encoding пересчитываются/убираются автоматически."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        actions.addStretch()
        self.send = QPushButton("Отправить запрос")
        self.send.clicked.connect(self._send_request)
        actions.addWidget(self.send)
        self.close_button = QPushButton("Закрыть")
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)
        if self._load_error:
            self.status.setText("Нельзя повторить запрос: " + self._load_error)
            self.send.setEnabled(False)

    def _convert_request_mode(self, *_args) -> None:
        current = self.request_body.toPlainText()
        destination = self.request_mode.currentData()
        previous = "hex" if destination == "text" else "text"
        try:
            data = _edited_bytes(current, previous)
            result = data.hex(" ") if destination == "hex" else data.decode("utf-8")
        except (ReplayError, UnicodeError):
            self.request_mode.blockSignals(True)
            self.request_mode.setCurrentIndex(0 if previous == "text" else 1)
            self.request_mode.blockSignals(False)
            self.status.setText("Невозможно преобразовать бинарное тело в текст; используйте HEX.")
            return
        self.request_body.setPlainText(result)

    def _send_request(self) -> None:
        try:
            body = _edited_bytes(
                self.request_body.toPlainText(),
                str(self.request_mode.currentData()),
            )
            # Validate before starting a worker; worker repeats validation.
            from apk_research.desktop.request_replay import (
                parse_headers, validate_target, MAX_REQUEST_BYTES,
            )
            parse_headers(self.headers.toPlainText())
            validate_target(self._original_url, self.url.text(), self._original_headers)
            if len(body) > MAX_REQUEST_BYTES:
                raise ReplayError("Тело запроса превышает 8 МиБ.")
        except ReplayError as exc:
            QMessageBox.warning(self, "Повторная отправка", str(exc))
            return
        answer = QMessageBox.question(
            self, "Подтвердить отправку",
            "Отправить новый " + self.method.currentText().upper()
            + "-запрос на " + self.url.text()
            + "?\nДействие может изменить данные на сервере.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.send.setEnabled(False)
        self.status.setText("Запрос выполняется… (TLS-проверка включена)")
        self._worker = _ReplayWorker((
            self._original_url, self.url.text(), self.method.currentText(),
            self.headers.toPlainText(), body, self._original_headers,
        ), self)
        self._worker.succeeded.connect(self._show_result)
        self._worker.failed.connect(self._show_error)
        self._worker.finished.connect(self._finished)
        self._worker.start()

    def _show_result(self, result: ReplayResult) -> None:
        self._result = result
        self.response_headers.setPlainText(
            "\n".join(f"{k}: {v}" for k, v in result.headers)
        )
        self.response_page.setValue(1)
        self._render_response()
        self.tabs.setCurrentIndex(3)
        self.status.setText(
            f"Ответ: HTTP {result.status} {result.reason}; "
            f"{len(result.body)} байт; {result.duration_ms} мс. "
            + ("Данные ограничены 8 МиБ." if result.limited else "")
            + " Ответ не добавлялся в исходный ZIP."
        )

    def _render_response(self, *_args) -> None:
        if self._result is None:
            return
        headers = {k.lower(): v for k, v in self._result.headers}
        self.response_body.setPlainText(format_http_body(
            self._result.body,
            headers.get("content-type", ""),
            headers.get("content-encoding", ""),
            mode=str(self.response_mode.currentData()),
            page=self.response_page.value() - 1,
            truncated=self._result.limited,
        ))

    def _show_error(self, message: str) -> None:
        self.status.setText("Не удалось отправить запрос: " + message)

    def _finished(self) -> None:
        self.send.setEnabled(not self._load_error)

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self, "Запрос выполняется",
                "Дождитесь завершения отправки (тайм-аут соединения 15 секунд).",
            )
            return
        super().reject()

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            event.ignore()
            return
        super().closeEvent(event)
