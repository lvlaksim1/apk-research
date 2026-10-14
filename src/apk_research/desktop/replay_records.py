"""In-memory representation of manually repeated HTTPS requests.

These records are ephemeral presentation data, not Research ZIP evidence.
Raw request and response bytes are retained only in this running UI.
"""
from __future__ import annotations

import time
import uuid
from urllib.parse import urlsplit

from apk_research.desktop.request_replay import ReplayResult, parse_headers


def _original_headers(record: dict) -> list[list[str]]:
    saved = record.get("_replay_original_headers")
    if saved is None:
        saved = (record.get("request") or {}).get("headers") or []
    return [
        [str(item[0]), str(item[1])]
        for item in saved
        if isinstance(item, (list, tuple)) and len(item) == 2
    ]


def _mime(headers: list[list[str]], name: str) -> str:
    return next(
        (value for key, value in headers if key.casefold() == name),
        "",
    )


def _body(data: bytes, headers: list[list[str]], *, limited: bool = False) -> dict:
    return {
        "present": bool(data),
        "path": None,
        "size": len(data),
        "content_type": _mime(headers, "content-type"),
        "content_encoding": _mime(headers, "content-encoding"),
        "_inline_bytes": data,
        "_limited": limited,
    }


def create_replay_record(
    source: dict, url: str, method: str, header_text: str, body: bytes
) -> dict:
    """Create a pending row; no disk writes, no raw body in the search index."""
    request_headers = [
        [name, value] for name, value in parse_headers(header_text)
    ]
    parsed = urlsplit(url)
    request_headers.insert(0, ["Host", parsed.netloc])
    if body or method.upper() in ("POST", "PUT", "PATCH"):
        request_headers.append(["Content-Length", str(len(body))])
    return {
        "transaction_id": "manual-" + uuid.uuid4().hex,
        "timestamp_start": time.time(),
        "method": method.strip().upper(),
        "url": url,
        "host": parsed.hostname or "",
        "capture_mode": "manual_replay",
        "_replay_original_url": (
            source.get("_replay_original_url") or source.get("url") or ""
        ),
        "_replay_original_headers": _original_headers(source),
        "request": {
            "headers": request_headers,
            "body": _body(body, request_headers),
        },
        "response": {},
        "state": "Выполняется",
        "duration_ms": 0,
    }


def complete_replay_record(
    started: dict, result: ReplayResult | None, error: str = ""
) -> dict:
    """Return an updated row retaining the same id and submitted request."""
    row = dict(started)
    if result is None:
        row["state"] = "Ошибка"
        row["error"] = error or "Не удалось получить ответ"
        row["response"] = {}
    else:
        headers = [[str(a), str(b)] for a, b in result.headers]
        row["state"] = "Завершён"
        row["error"] = ""
        row["duration_ms"] = result.duration_ms
        row["response"] = {
            "status_code": result.status,
            "headers": headers,
            "body": _body(result.body, headers, limited=result.limited),
        }
    return row
