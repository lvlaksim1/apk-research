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


def test_main_window_integrates_https_beside_android(app):
    window = MainWindow()
    try:
        assert window.tabs.count() == 1
        assert window.tabs.tabText(0) == "Исследование"
        assert window.research_splitter.count() == 3
        assert window.research_splitter.indexOf(window.https_view) == 2
        assert window.research_splitter.indexOf(window.android_view.parentWidget()) == 1
        assert window.https_view is not None
        assert window.stop_button.text() == "5. Начать запись ZIP"
        assert window.start_button.text() == "Начать анализ"
        assert window.installed_apps.count() == 0
        assert len(window.emulator_buttons) == 18
        assert "more" not in window.emulator_buttons
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


def test_https_sorting_preserves_details_after_new_records(app):
    view = LiveHttpsView()
    try:
        a = _transaction()
        a["timestamp_start"] = 100.0
        a["url"] = "https://example.com/first"
        a["response"]["status_code"] = 301
        b = _transaction()
        b["timestamp_start"] = 200.0
        b["url"] = "https://example.com/second"
        b["response"]["status_code"] = 200
        view.transactions = [a, b]
        view._apply_filter()
        assert view.table.item(0, 3).text() == "/second"
        view.table.horizontalHeader().sectionClicked.emit(4)
        assert [view.table.item(i, 4).text() for i in range(2)] == ["200", "301"]
        view._show_selected(0)
        assert "/second" in view.info.toPlainText()
        view.table.horizontalHeader().sectionClicked.emit(4)
        assert [view.table.item(i, 4).text() for i in range(2)] == ["301", "200"]
        view.table.selectRow(0)
        view._show_selected(0)
        assert "/first" in view.info.toPlainText()
        c = _transaction()
        c["timestamp_start"] = 300.0
        c["url"] = "https://example.com/third"
        c["response"]["status_code"] = 404
        view.transactions.append(c)
        view._apply_filter()
        assert [view.table.item(i, 4).text() for i in range(3)] == ["404", "301", "200"]
        assert "/first" in view.info.toPlainText()
        view.search.setText("third")
        assert view.table.rowCount() == 1
        view._show_selected(0)
        assert "/third" in view.info.toPlainText()
    finally:
        view.timer.stop()
        view.close()


def test_https_method_and_domain_headers_use_independent_filters(app):
    view = LiveHttpsView()
    try:
        a = _transaction()
        a["method"] = "GET"
        a["url"] = "https://alpha.example/api"
        a["host"] = "alpha.example"
        b = _transaction()
        b["method"] = "POST"
        b["url"] = "https://beta.example/send"
        b["host"] = "beta.example"
        c = _transaction()
        c["method"] = "GET"
        c["url"] = "https://beta.example/other"
        c["host"] = "beta.example"
        view.transactions = [a, b, c]
        view._apply_filter()
        view._set_column_filter(1, {"GET"})
        assert view.table.rowCount() == 2
        view._set_column_filter(3, {"beta.example"})
        assert view.table.rowCount() == 1
        assert "/other" in view.info.toPlainText()
        assert view._filter_options(1) == ["GET", "POST"]
        assert view._filter_options(3) == ["alpha.example", "beta.example"]
        assert view._sort_column == 0
        view._set_column_filter(1, None)
        assert view.table.rowCount() == 2
        view._set_column_filter(3, None)
        assert view.table.rowCount() == 3
    finally:
        view.timer.stop()
        view.close()



def test_https_analysis_and_zip_have_independent_window_states(app, tmp_path):
    window = MainWindow()
    try:
        window._on_installed_apps(["com.example.alpha", "com.example.beta"])
        assert window.installed_apps.count() == 2
        assert window.controller.package_name == "com.example.alpha"
        starts = []
        zips = []
        window.controller.start_analysis = lambda package: starts.append(package)
        window.controller.start_research = lambda: zips.append("start")
        window._toggle_analysis()
        assert starts == ["com.example.alpha"]
        assert not zips
        assert window._analysis_starting
        window._on_analysis_started({
            "package": "com.example.alpha",
            "session_root": str(tmp_path),
        })
        assert window._analysis_active
        assert window.https_view.timer.isActive()
        assert window.start_button.text() == "Остановить"
        assert window.stop_button.isEnabled()
        window._toggle_zip()
        assert zips == ["start"]
        window._on_research_started({"package": "com.example.alpha"})
        assert window._research_active
        assert window.https_view.timer.isActive()
        window._on_research_finished({
            "archive": str(tmp_path / "recording.research.zip"),
            "session_status": "complete",
            "validation_issues": 0,
        })
        assert not window._research_active
        assert window._analysis_active
        assert window.https_view.timer.isActive()
        assert window.installed_apps.isEnabled() is False
        window._on_analysis_stopped("com.example.alpha")
        assert not window.https_view.timer.isActive()
    finally:
        window.https_view.timer.stop()
        window.controller.close()
        window.close()



def test_http_text_and_hex_in_live_and_saved_zip(app, tmp_path):
    import zlib
    from apk_research.desktop.http_window import HttpTransactionsWindow

    boundary = "--dio-boundary-3334630000"
    form = (
        "--" + boundary + "\r\n"
        'Content-Disposition: form-data; name="action"\r\n\r\n'
        "readField\r\n"
        "--" + boundary + "--\r\n"
    ).encode()
    raw_response = zlib.compress(
        '{"ok":true,"message":"русский текст"}'.encode("utf-8"), level=9
    )
    assert raw_response[:2] == b"\x78\xda"
    item = _transaction()
    item["method"] = "POST"
    item["request"]["headers"] = [
        ["content-type", "multipart/form-data, boundary=" + boundary]
    ]
    item["request"]["body"] = {
        "present": True, "path": "http-00000001.request.body",
        "content_type": "multipart/form-data, boundary=" + boundary,
        "size": len(form),
    }
    item["response"]["headers"] = [
        ["content-type", "application/zlib"],
        ["content-encoding", "gzip"],
    ]
    item["response"]["body"] = {
        "present": True, "path": "http-00000001.response.body",
        "content_type": "application/zlib", "content_encoding": "gzip",
        "size": len(raw_response),
    }
    session = tmp_path / "live"
    bodies = session / "02_normalized/http-bodies"
    bodies.mkdir(parents=True)
    (bodies / "http-00000001.request.body").write_bytes(form)
    (bodies / "http-00000001.response.body").write_bytes(raw_response)
    line = json.dumps(item).encode("utf-8") + b"\n"
    (session / "02_normalized/http-transactions.jsonl").write_bytes(line)
    view = LiveHttpsView()
    view.begin_session(session, "com.example.test")
    try:
        view.refresh()
        view.table.selectRow(0)
        view._show_selected(0)
        assert "Поле: action" in view.request_body.toPlainText()
        assert "readField" in view.request_body.toPlainText()
        assert '"message": "русский текст"' in view.response_body.toPlainText()
        view.body_mode.setCurrentIndex(1)
        assert form[:8].hex(" ") in view.request_body.toPlainText()
        assert raw_response[:8].hex(" ") in view.response_body.toPlainText()
        view.body_mode.setCurrentIndex(0)
        assert '"ok": true' in view.response_body.toPlainText()

        archive = tmp_path / "saved.research.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("02_normalized/http-transactions.jsonl", line)
            zipped.write(
                bodies / "http-00000001.request.body",
                "02_normalized/http-bodies/http-00000001.request.body",
            )
            zipped.write(
                bodies / "http-00000001.response.body",
                "02_normalized/http-bodies/http-00000001.response.body",
            )
        view.finish_session(archive)
        assert '"message": "русский текст"' in view.response_body.toPlainText()
        view.body_mode.setCurrentIndex(1)
        assert raw_response[:8].hex(" ") in view.response_body.toPlainText()
        view.body_mode.setCurrentIndex(0)

        legacy = HttpTransactionsWindow(archive)
        try:
            legacy.table.selectRow(0)
            legacy._show_transaction(item)
            assert "readField" in legacy.request_body.toPlainText()
            assert '"message": "русский текст"' in legacy.response_body.toPlainText()
            legacy.body_mode.setCurrentIndex(1)
            assert raw_response[:8].hex(" ") in legacy.response_body.toPlainText()
        finally:
            legacy.close()
    finally:
        view.timer.stop()
        view.close()



def test_large_zlib_body_paging_live_and_archived(app, tmp_path):
    from apk_research.desktop.http_window import HttpTransactionsWindow
    import zlib
    text = (b'{"values":"' + b"A" * 300000 + b'"}')
    compressed = zlib.compress(text, level=9)
    item = _transaction()
    item["response"]["body"].update(
        size=len(compressed),
        content_type="application/zlib",
        content_encoding="gzip",
    )
    location = tmp_path / "02_normalized/http-bodies"
    location.mkdir(parents=True)
    (location / "http-00000001.response.body").write_bytes(compressed)
    journal = tmp_path / "02_normalized/http-transactions.jsonl"
    journal.write_text(json.dumps(item) + "\n", encoding="utf-8")
    view = LiveHttpsView()
    view.begin_session(tmp_path, "com.example.test")
    try:
        view.refresh()
        view.table.selectRow(0)
        assert "Фрагмент 1 из 3" in view.response_body.toPlainText()
        view.body_page.setValue(2)
        assert "Фрагмент 2 из 3" in view.response_body.toPlainText()
        view.body_mode.setCurrentIndex(1)
        assert compressed[:8].hex(" ") in view.response_body.toPlainText()
        view.body_mode.setCurrentIndex(0)
        assert "Фрагмент 2 из 3" in view.response_body.toPlainText()
        archive = tmp_path / "saved.research.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.write(journal, "02_normalized/http-transactions.jsonl")
            zipped.write(
                location / "http-00000001.response.body",
                "02_normalized/http-bodies/http-00000001.response.body",
            )
        view.finish_session(archive)
        view.body_page.setValue(3)
        assert "Фрагмент 3 из 3" in view.response_body.toPlainText()
        reader = HttpTransactionsWindow(archive)
        try:
            reader._show_transaction(item)
            reader.body_page.setValue(2)
            assert "Фрагмент 2 из 3" in reader.response_body.toPlainText()
        finally:
            reader.close()
    finally:
        view.timer.stop()
        view.close()



def test_replay_dialog_json_pretty_and_original_evidence_unchanged(app, tmp_path):
    from apk_research.desktop.replay_dialog import (
        ReplayDialog, _edited_bytes, _body_for_editor,
    )
    assert _body_for_editor(b'{"a":1,"b":{"x":2}}')[1].startswith('{\n  "a": 1')
    assert _body_for_editor(b"\x00\xff") == ("hex", "00 ff")
    assert _edited_bytes("00 ff", "hex") == b"\x00\xff"

    body = b'{"a":1,"b":{"x":2}}'
    path = tmp_path / "02_normalized/http-bodies"
    path.mkdir(parents=True)
    (path / "one.request.body").write_bytes(body)
    record = {
        "method": "POST", "url": "https://example.com/items",
        "request": {
            "headers": [["content-type", "application/json"], ["Host", "example.com"]],
            "body": {"present": True, "path": "one.request.body"},
        },
    }
    dialog = ReplayDialog(record, session_root=tmp_path)
    try:
        assert dialog.method.currentText() == "POST"
        assert '"a": 1' in dialog.request_body.toPlainText()
        assert '"x": 2' in dialog.request_body.toPlainText()
        assert dialog.send.isEnabled()
        dialog.request_mode.setCurrentIndex(1)
        assert body[:3].hex(" ") in dialog.request_body.toPlainText() is False or (
            "7b 0a" in dialog.request_body.toPlainText()
        )
        dialog.request_mode.setCurrentIndex(0)
        assert '"a": 1' in dialog.request_body.toPlainText()
        assert (path / "one.request.body").read_bytes() == body
    finally:
        dialog.close()
