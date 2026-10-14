"""Explicit one-shot HTTPS request replay. Never modifies original capture/ZIP."""
from __future__ import annotations

import http.client
import re
import ssl
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_HEADERS_BYTES = 64 * 1024
MAX_HEADER_COUNT = 120
HOP_HEADERS = frozenset({
    "connection", "proxy-connection", "proxy-authorization",
    "proxy-authenticate", "keep-alive", "te", "trailer",
    "transfer-encoding", "upgrade", "expect", "host",
    "content-length", "content-encoding",
})
TOKEN = re.compile(r"^[!#$%&'*+.^_a-zA-Z0-9|~-]+$")


class ReplayError(ValueError):
    """Invalid/unsafe request or unavailable captured bytes."""


@dataclass(frozen=True)
class ReplayResult:
    status: int
    reason: str
    headers: list[tuple[str, str]]
    body: bytes
    limited: bool
    duration_ms: int


def _host(name: str) -> str:
    name = name.strip()
    if not name or any(x in name for x in ("\r", "\n", "@", "/", "\\")):
        return ""
    try:
        return (urlsplit("//" + name).hostname or "").rstrip(".").lower()
    except ValueError:
        return ""


def validate_target(original_url: str, target_url: str,
                    original_headers: list[tuple[str, str]]) -> tuple[str, int, str]:
    original = urlsplit(original_url)
    target = urlsplit(target_url)
    if original.scheme.lower() != "https" or target.scheme.lower() != "https":
        raise ReplayError("Повторная отправка доступна только для HTTPS.")
    if not original.hostname or not target.hostname or target.username or target.password:
        raise ReplayError("Невозможно определить безопасный адрес назначения.")
    try:
        src_port, port = original.port or 443, target.port or 443
    except ValueError as exc:
        raise ReplayError("Недопустимый номер порта.") from exc
    allowed = {original.hostname.rstrip(".").lower()}
    for key, value in original_headers:
        if key.casefold() == "host" and _host(value):
            allowed.add(_host(value))
    host = target.hostname.rstrip(".").lower()
    if host not in allowed or port != src_port:
        raise ReplayError(
            "Можно отправлять только на исходный сервер или сохранённый "
            "для него Host, без изменения порта."
        )
    if target.fragment or any(ord(ch) < 32 for ch in target_url):
        raise ReplayError("Недопустимый фрагмент или символы в адресе.")
    path = target.path or "/"
    if target.query:
        path += "?" + target.query
    return host, port, path


def parse_headers(text: str) -> list[tuple[str, str]]:
    if len(text.encode("utf-8")) > MAX_HEADERS_BYTES:
        raise ReplayError("Размер заголовков превышает 64 КиБ.")
    result: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line[0] in " \t" or ":" not in line:
            raise ReplayError("Заголовки: каждая строка должна иметь вид Имя: значение.")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if not TOKEN.fullmatch(key) or any(ord(x) < 32 and x != "\t" for x in value):
            raise ReplayError("Некорректные заголовки.")
        if key.lower() in HOP_HEADERS:
            continue  # calculated by the HTTP client; never carry stale compression
        if len(result) >= MAX_HEADER_COUNT:
            raise ReplayError("Слишком много HTTP-заголовков.")
        result.append((key, value))
    return result


def read_captured_body(
    record: dict, archive_path: Path | None, session_root: Path | None,
) -> bytes:
    body = (record.get("request") or {}).get("body") or {}
    if not body.get("present"):
        return b""
    name = body.get("path")
    if not isinstance(name, str) or not name or Path(name).name != name:
        raise ReplayError("Недопустимое имя файла исходного тела запроса.")
    if archive_path is not None:
        try:
            with zipfile.ZipFile(archive_path) as archive:
                with archive.open("02_normalized/http-bodies/" + name) as stream:
                    value = stream.read(MAX_REQUEST_BYTES + 1)
        except (OSError, KeyError, zipfile.BadZipFile, RuntimeError) as exc:
            raise ReplayError("Исходное тело запроса отсутствует в ZIP.") from exc
    elif session_root is not None:
        try:
            with (Path(session_root) / "02_normalized/http-bodies" / name).open("rb") as f:
                value = f.read(MAX_REQUEST_BYTES + 1)
        except OSError as exc:
            raise ReplayError("Не удалось прочитать тело текущего запроса.") from exc
    else:
        raise ReplayError("Источник исходного запроса недоступен.")
    if len(value) > MAX_REQUEST_BYTES:
        raise ReplayError("Тело запроса больше 8 МиБ; повторная отправка запрещена.")
    return value


def perform_replay(
    original_url: str, url: str, method: str, header_text: str, body: bytes,
    original_headers: list[tuple[str, str]],
) -> ReplayResult:
    """Single user-triggered request, no redirects, retries, or disabled TLS."""
    headers = parse_headers(header_text)
    host, port, path = validate_target(original_url, url, original_headers)
    method = method.strip().upper()
    if not TOKEN.fullmatch(method) or len(method) > 32:
        raise ReplayError("Недопустимый метод HTTP.")
    if not isinstance(body, bytes) or len(body) > MAX_REQUEST_BYTES:
        raise ReplayError("Тело запроса должно быть байтовым и не превышать 8 МиБ.")
    started = time.monotonic()
    conn = http.client.HTTPSConnection(
        host, port, timeout=15, context=ssl.create_default_context()
    )
    try:
        conn.putrequest(method, path, skip_accept_encoding=True)
        if not any(k.lower() == "accept-encoding" for k, _ in headers):
            conn.putheader("Accept-Encoding", "identity")
        for key, value in headers:
            conn.putheader(key, value)
        if body or method in ("POST", "PUT", "PATCH"):
            conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body if body else None)
        response = conn.getresponse()
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        return ReplayResult(
            status=int(response.status), reason=str(response.reason),
            headers=[(str(k), str(v)) for k, v in response.getheaders()],
            body=payload[:MAX_RESPONSE_BYTES], limited=len(payload) > MAX_RESPONSE_BYTES,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        # Do not leak URL, authorization/cookies, or body into UI diagnostics.
        raise ReplayError(
            "Не удалось выполнить HTTPS-запрос или проверить TLS: "
            + type(exc).__name__
        ) from exc
    finally:
        conn.close()
