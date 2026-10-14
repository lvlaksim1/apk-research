"""Replay boundaries: explicit target restrictions and byte-exact requests."""
from __future__ import annotations

import json
import zipfile

import pytest

from apk_research.desktop.request_replay import (
    MAX_REQUEST_BYTES, ReplayError, parse_headers, perform_replay,
    read_captured_body, validate_target,
)


def test_editable_target_restricted_to_saved_host_and_port():
    original = "https://88.198.62.106:443/flut23/ping.php"
    saved = [("Host", "srv1.resources-game.ch")]
    assert validate_target(original, "https://srv1.resources-game.ch/flut23/ping.php?a=2", saved) == (
        "srv1.resources-game.ch", 443, "/flut23/ping.php?a=2"
    )
    for url in (
        "http://88.198.62.106/ping",
        "https://evil.example/ping",
        "https://srv1.resources-game.ch:444/ping",
        "https://user:pass@88.198.62.106/ping",
        "https://88.198.62.106/ping#fragment",
    ):
        with pytest.raises(ReplayError):
            validate_target(original, url, saved)
    # Edited Host cannot create an allowed target; only recorded headers authorize it.
    with pytest.raises(ReplayError):
        validate_target(original, "https://evil.example/ping", [])


def test_header_validation_rebuilds_length_and_never_forwards_old_gzip():
    text = (
        "authorization: Bearer sample\n"
        "cookie: sid=test\n"
        "Content-Type: application/json\n"
        "Content-Length: 123\n"
        "Content-Encoding: gzip\n"
        "Host: wrong.example\n"
        "Transfer-Encoding: chunked\n"
        "X-Action: 1\n"
        "X-Action: 2\n"
    )
    assert parse_headers(text) == [
        ("authorization", "Bearer sample"), ("cookie", "sid=test"),
        ("Content-Type", "application/json"),
        ("X-Action", "1"), ("X-Action", "2"),
    ]
    with pytest.raises(ReplayError):
        parse_headers("Not A Header")
    with pytest.raises(ReplayError):
        parse_headers(" bad: header")
    with pytest.raises(ReplayError):
        parse_headers("X-Bad: \x01")
    with pytest.raises(ReplayError):
        parse_headers("X-OK: " + "a" * (64 * 1024 + 1))


def test_captured_request_body_from_live_and_zip_does_not_mutate_files(tmp_path):
    source = tmp_path / "02_normalized/http-bodies"
    source.mkdir(parents=True)
    body = b'{"b":2,"a":1}'
    (source / "one.request.body").write_bytes(body)
    record = {"request": {"body": {"present": True, "path": "one.request.body"}}}
    assert read_captured_body(record, None, tmp_path) == body
    archive = tmp_path / "sample.research.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.write(
            source / "one.request.body",
            "02_normalized/http-bodies/one.request.body",
        )
    assert read_captured_body(record, archive, None) == body
    assert (source / "one.request.body").read_bytes() == body
    with zipfile.ZipFile(archive) as stream:
        assert stream.read("02_normalized/http-bodies/one.request.body") == body
    record["request"]["body"]["path"] = "../../secret"
    with pytest.raises(ReplayError):
        read_captured_body(record, None, tmp_path)


class _Response:
    status = 302
    reason = "Found"

    def read(self, limit):
        return b'{"ok":true}'

    def getheaders(self):
        return [("Content-Type", "application/json"), ("Location", "/redirect")]


class _Connection:
    history = []

    def __init__(self, host, port, timeout, context):
        self.history.append(["open", host, port, timeout, context.verify_mode])

    def putrequest(self, method, path, skip_accept_encoding):
        self.history.append(["request", method, path, skip_accept_encoding])

    def putheader(self, key, value):
        self.history.append(["header", key, value])

    def endheaders(self, body):
        self.history.append(["body", body])

    def getresponse(self):
        return _Response()

    def close(self):
        self.history.append(["close"])


def test_replay_is_one_shot_tls_and_preserves_explicit_body(monkeypatch):
    from apk_research.desktop import request_replay as module
    _Connection.history.clear()
    monkeypatch.setattr(module.http.client, "HTTPSConnection", _Connection)
    raw = b'{"x":1, "changed":true}'
    result = perform_replay(
        "https://example.com/a", "https://example.com/b?q=1", "post",
        "Host: example.com\nContent-Length: 777\n"
        "Content-Encoding: gzip\nContent-Type: application/json\n",
        raw, [("Host", "example.com")],
    )
    assert result.status == 302
    assert result.body == b'{"ok":true}'
    assert ["request", "POST", "/b?q=1", True] in _Connection.history
    assert ["body", raw] in _Connection.history
    assert ["header", "Content-Length", str(len(raw))] in _Connection.history
    assert not any(x[:2] in (
        ["header", "Content-Encoding"], ["header", "Host"],
    ) for x in _Connection.history)
    assert len([x for x in _Connection.history if x[0] == "request"]) == 1
    assert ["close"] in _Connection.history


def test_no_large_send_or_cross_host_secret_forward(monkeypatch):
    from apk_research.desktop import request_replay as module
    monkeypatch.setattr(module.http.client, "HTTPSConnection", _Connection)
    _Connection.history.clear()
    with pytest.raises(ReplayError):
        perform_replay(
            "https://example.com", "https://attacker.example", "POST",
            "Authorization: Bearer abc\nHost: attacker.example",
            b"secret", [("Host", "example.com")],
        )
    with pytest.raises(ReplayError):
        perform_replay(
            "https://example.com", "https://example.com", "POST",
            "", b"X" * (MAX_REQUEST_BYTES + 1), [],
        )
    assert _Connection.history == []
