"""GUI acceptance for the streamlined two-purpose main window.

These tests run in the Windows desktop build where PySide6 is installed.
Core-only CI intentionally skips them.
"""
from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from apk_research.desktop.main_window import MainWindow
from apk_research.desktop.live_https import LiveHttpsView


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    yield instance


def _transaction() -> dict:
    return {
        "transaction_id": "http-00000001",
        "timestamp_start": 1760067900.0,
        "method": "GET",
        "url": "https://evrasia.spb.ru/api/v3/menu/",
        "host": "evrasia.spb.ru",
        "duration_ms": 43,
        "request": {"headers": [["accept", "application/json"]], "body": {
            "present": False, "size": 0, "path": None}},
        "response": {
            "status_code": 200,
            "headers": [["content-type", "application/json"]],
            "body": {"present": True, "size": 11,
                     "path": "http-00000001.response.body",
                     "content_type": "application/json"},
        },
    }


def test_main_window_exposes_only_research_and_https(app):
    window = MainWindow()
    try:
        assert window.tabs.count() == 2
        assert [window.tabs.tabText(i) for i in range(2)] == [
            "Исследование", "HTTPS • онлайн"
        ]
        assert window.https_view is not None
        assert window.stop_button.text() == "ЗАВЕРШИТЬ И СОХРАНИТЬ"
        assert window.zip_folder_button.isVisible() is False or (
            window.zip_folder_button.text() == "Открыть папку с ZIP"
        )
        assert not any(page in (
            window.tabs.widget(i) for i in range(window.tabs.count())
        ) for page in window._hidden_pages)
    finally:
        window.https_view.timer.stop()
        window.controller.close()
        window.close()


def test_live_https_updates_before_archive_and_reads_body(app, tmp_path: Path):
    view = LiveHttpsView()
    session = tmp_path / "session"
    journal = session / "02_normalized/http-transactions.jsonl"
    journal.parent.mkdir(parents=True)
    body = session / "02_normalized/http-bodies/http-00000001.response.body"
    body.parent.mkdir(parents=True)
    body.write_text('{"ok":true}', encoding="utf-8")
    view.begin_session(session, "com.evrasia")
    try:
        data = json.dumps(_transaction()).encode("utf-8")
        journal.write_bytes(data[:40])
        view.refresh()
        assert view.table.rowCount() == 0
        with journal.open("ab") as stream:
            stream.write(data[40:] + b"\n")
        view.refresh()
        assert view.table.rowCount() == 1
        assert view.table.item(0, 1).text() == "GET"
        assert view.table.item(0, 2).text() == "evrasia.spb.ru"
        view.table.selectRow(0)
        view._show_selected(0)
        assert '"ok": true' in view.response_body.toPlainText()

        archive = tmp_path / "last.research.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("02_normalized/http-transactions.jsonl", data + b"\n")
            zipped.write(body, "02_normalized/http-bodies/" + body.name)
        view.finish_session(archive)
        assert not view.timer.isActive()
        assert view.table.rowCount() == 1
        assert view.archive_path == archive
        assert '"ok": true' in view.response_body.toPlainText()
    finally:
        view.timer.stop()
        view.close()
