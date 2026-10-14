"""Display-only HTTP body decode regressions (no Qt/Android dependency)."""
from __future__ import annotations

import gzip
import json
import zlib

from apk_research.desktop.body_display import format_http_body


def test_zlib_application_body_pretty_printed_and_raw_hex_remains_original():
    plain = '{"username":"проверка","count":2}'.encode("utf-8")
    compressed = zlib.compress(plain, level=9)
    assert compressed[:2] == b"\x78\xda"
    readable = format_http_body(
        compressed, "application/zlib", "gzip", mode="text",
    )
    assert '"username": "проверка"' in readable
    assert '"count": 2' in readable
    assert "zlib" in readable
    assert format_http_body(compressed, "application/zlib", "gzip", mode="hex").splitlines()[-1].startswith(
        compressed[:8].hex(" ")
    )


def test_gzip_body_decompression_with_declared_http_header():
    data = gzip.compress(b'{"items":[1,2],"ok":true}')
    rendered = format_http_body(data, "application/json", "gzip")
    assert '"ok": true' in rendered
    assert '"items": [' in rendered
    assert "gzip" in rendered
    assert "1f 8b" in format_http_body(data, "application/json", "gzip", mode="hex")


def test_gzip_already_removed_by_collector_does_not_get_redecompressed():
    body = b'{"ok":true}'
    rendered = format_http_body(body, "application/json", "gzip")
    assert '"ok": true' in rendered
    assert "gzip уже снят" in rendered
    assert "Ошибка" not in rendered


def test_deflate_zlib_stream_and_nested_layers():
    payload = json.dumps({"status": "ok"}).encode()
    packed = zlib.compress(payload)
    assert '"status": "ok"' in format_http_body(packed, "application/json", "deflate")
    double = gzip.compress(packed)
    rendered = format_http_body(double, "application/zlib", "gzip")
    assert '"status": "ok"' in rendered
    assert "zlib" in rendered


def test_multipart_with_fields_file_and_nonstandard_comma_boundary():
    boundary = "--dio-boundary-3334630000"
    payload = (
        ("--" + boundary + "\r\n"
         'Content-Disposition: form-data; name="action"\r\n\r\n'
         "getData\r\n"
         "--" + boundary + "\r\n"
         'Content-Disposition: form-data; name="session"\r\n'
         "Content-Type: application/json\r\n\r\n"
         '{"id":123,"ok":true}\r\n'
         "--" + boundary + "\r\n"
         'Content-Disposition: form-data; name="attachment"; filename="x.bin"\r\n'
         "Content-Type: application/octet-stream\r\n\r\n").encode()
        + b"\x00\x01\xff"
        + ("\r\n--" + boundary + "--\r\n").encode()
    )
    shown = format_http_body(
        payload, "multipart/form-data, boundary=" + boundary
    )
    assert "Поле: action" in shown
    assert "getData" in shown
    assert "Поле: session" in shown
    assert '"id": 123' in shown
    assert "файл: x.bin" in shown
    assert "00 01 ff" in shown
    assert "Ошибка" not in shown
    hexed = format_http_body(payload, "multipart/form-data", mode="hex")
    assert payload[:12].hex(" ") in hexed


def test_bounded_decompression_preserves_original_bytes_on_excess():
    bomb = zlib.compress(b"X" * (128 * 1024 + 1))
    result = format_http_body(bomb, "application/zlib")
    assert "128 КиБ" in result
    assert bomb[:2].hex(" ") in result


def test_invalid_truncated_and_genuine_binary_are_not_fabricated_as_text():
    damaged = b"\x78\xda" + b"\x00" * 5
    shown = format_http_body(damaged, "application/zlib")
    assert "Ошибка распаковки" in shown
    assert damaged.hex(" ") in shown
    raw = b"\x00\xff\x01\xd4\x8a"
    result = format_http_body(raw, "application/octet-stream")
    assert "Текстовый формат не подтверждён" in result
    assert raw.hex(" ") in result
    assert "128 КиБ" in format_http_body(
        gzip.compress(b"data"), "application/json", "gzip", truncated=True
    )


def test_utf8_utf16_and_form_fields():
    assert "привет" in format_http_body("привет".encode(), "text/plain")
    assert "hello" in format_http_body(
        "hello".encode("utf-16"), "text/plain; charset=utf-16"
    )
    assert "key: русский" in format_http_body(
        "key=%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9".encode(),
        "application/x-www-form-urlencoded",
    )
