"""Manual sends become in-memory, traceable HTTPS rows, never ZIP evidence."""
from __future__ import annotations

from apk_research.desktop.replay_records import (
    create_replay_record, complete_replay_record,
)
from apk_research.desktop.request_replay import ReplayResult, read_captured_body


def source():
    return {
        "url": "https://example.org/start",
        "method": "POST",
        "request": {
            "headers": [["host", "api.example.org"], ["content-type", "application/json"]],
            "body": {"present": False},
        },
    }


def test_manual_record_preserves_edited_method_bytes_and_origin(tmp_path):
    body = b'{"item": 3}'
    row = create_replay_record(
        source(), "https://api.example.org/path?q=1", "patch",
        "Content-Type: application/json\nContent-Length: 1234\n",
        body,
    )
    assert row["capture_mode"] == "manual_replay"
    assert row["method"] == "PATCH"
    assert row["state"] == "Выполняется"
    assert row["host"] == "api.example.org"
    assert row["_replay_original_url"] == "https://example.org/start"
    assert ["host", "api.example.org"] in row["_replay_original_headers"]
    assert row["request"]["body"]["_inline_bytes"] == body
    assert read_captured_body(row, None, None) == body
    assert ["Content-Length", str(len(body))] in row["request"]["headers"]


def test_completion_same_identifier_with_original_bytes_and_separate_response():
    row = create_replay_record(
        source(), "https://example.org/data", "post",
        "content-type: application/json", b'{"x":1}',
    )
    result = ReplayResult(
        status=201, reason="Created",
        headers=[("Content-Type", "application/json")],
        body=b'{"ok":true}', limited=False, duration_ms=87,
    )
    complete = complete_replay_record(row, result)
    assert complete["transaction_id"] == row["transaction_id"]
    assert complete["response"]["status_code"] == 201
    assert complete["response"]["body"]["_inline_bytes"] == b'{"ok":true}'
    assert complete["request"]["body"]["_inline_bytes"] == b'{"x":1}'
    assert "response" in complete and not row["response"]
    assert not complete["error"]


def test_failed_manual_request_stays_visible_without_fake_response():
    row = create_replay_record(
        source(), "https://example.org/missing", "GET", "", b"",
    )
    fail = complete_replay_record(row, None, "TLS проверка отклонена")
    assert fail["transaction_id"] == row["transaction_id"]
    assert fail["state"] == "Ошибка"
    assert "TLS" in fail["error"]
    assert fail["response"] == {}
