"""Bounded, read-only presentation of saved HTTP bodies.

No transformation in this module modifies Research ZIP artifacts or the
bytes retained by the HTTPS recorder. All decoding is display-only.
"""
from __future__ import annotations

import json
import re
import zlib
from email import policy
from email.parser import BytesParser
from email.message import Message
from urllib.parse import parse_qsl

MAX_TEXT_BYTES = 128 * 1024
# Separate memory-safety ceiling from the amount shown on a single page.
MAX_INFLATE_BYTES = 8 * 1024 * 1024
MAX_HEX_BYTES = 4096
MAX_PARTS = 64


def _raw_hex(data: bytes) -> str:
    payload = data[:MAX_HEX_BYTES].hex(" ")
    suffix = (
        "\n… HEX ограничен первыми 4096 байтами"
        if len(data) > MAX_HEX_BYTES else ""
    )
    return f"<исходные байты: {len(data)}>\n{payload}{suffix}"


def _content_params(content_type: str) -> Message:
    header = Message()
    # Never allow a header value to inject extra email parser headers.
    safe = content_type.replace("\r", "").replace("\n", "")
    # A few observed applications use a comma instead of a semicolon.
    safe = re.sub(
        r",\s*(boundary\s*=)", r"; \1", safe, flags=re.IGNORECASE
    )
    header["Content-Type"] = safe
    return header


def _is_zlib(data: bytes) -> bool:
    return (
        len(data) >= 2
        and data[0] & 15 == 8
        and (data[0] >> 4) <= 7
        and ((data[0] << 8) | data[1]) % 31 == 0
    )


def _inflate(data: bytes, wbits: int) -> tuple[bytes, bool]:
    """Decompress at most 8 MiB. Return a safe prefix if larger.

    A valid large response is not a decoding failure. Returning a bounded
    prefix permits viewing pages without unlimited decompression or memory.
    Stream integrity is only declared for a complete, verified stream.
    """
    decoder = zlib.decompressobj(wbits)
    output = decoder.decompress(data, MAX_INFLATE_BYTES + 1)
    if len(output) > MAX_INFLATE_BYTES or decoder.unconsumed_tail:
        return output[:MAX_INFLATE_BYTES], True
    output += decoder.flush(MAX_INFLATE_BYTES + 1 - len(output))
    if len(output) > MAX_INFLATE_BYTES:
        return output[:MAX_INFLATE_BYTES], True
    if not decoder.eof:
        raise ValueError("Сжатые данные обрываются до завершения потока")
    if decoder.unused_data:
        raise ValueError("После сжатого потока обнаружены дополнительные байты")
    return output, False


def _is_text(content_type: str) -> bool:
    value = content_type.casefold()
    return (
        value.startswith("text/")
        or any(kind in value for kind in (
            "json", "xml", "javascript", "x-www-form-urlencoded", "graphql",
        ))
    )


def _text(
    data: bytes, content_type: str, *, incomplete: bool = False
) -> str | None:
    if data == b"":
        return ""
    header = _content_params(content_type)
    charset = header.get_param("charset", header="content-type")
    encodings = [charset] if charset else []
    encodings.extend(["utf-8-sig", "utf-16"] if data.startswith((
        b"\xff\xfe", b"\xfe\xff"
    )) else ["utf-8-sig"])
    for encoding in encodings:
        if not encoding:
            continue
        try:
            decoded = data.decode(str(encoding), errors="strict")
        except UnicodeDecodeError as exc:
            # Only trim an *incomplete trailing* code point at a page
            # boundary; do not silently discard arbitrary invalid bytes.
            if (
                not incomplete or exc.reason != "unexpected end of data"
                or exc.start < len(data) - 4
            ):
                continue
            try:
                decoded = data[:exc.start].decode(str(encoding), errors="strict")
            except (UnicodeError, LookupError, ValueError):
                continue
        except (LookupError, ValueError):
            continue
        if not decoded:
            return ""
        invalid = sum(
            1 for char in decoded
            if not char.isprintable() and char not in "\r\n\t"
        )
        if invalid > max(1, len(decoded) // 100):
            continue
        return decoded
    return None


def _text_display(
    data: bytes, content_type: str, *, incomplete: bool = False
) -> str | None:
    text = _text(data, content_type, incomplete=incomplete)
    if text is None:
        return None
    if not incomplete and "x-www-form-urlencoded" in content_type.lower():
        items = parse_qsl(text, keep_blank_values=True)
        return "\n".join(f"{key}: {val}" for key, val in items)
    if not incomplete and (
        "json" in content_type.lower()
        or text.lstrip().startswith(("{", "["))
    ):
        try:
            return json.dumps(
                json.loads(text), indent=2, ensure_ascii=False
            )
        except (ValueError, TypeError):
            pass
    return text


def _multipart(data: bytes, content_type: str) -> str | None:
    params = _content_params(content_type)
    boundary = params.get_param("boundary", header="content-type")
    if not boundary or len(str(boundary)) > 200:
        return None
    # Multipart body is parsed as a single MIME entity, with bounded input.
    safe_type = content_type.replace("\r", "").replace("\n", "")
    # Some applications send non-standard ", boundary=" rather than "; boundary=".
    safe_type = re.sub(
        r",\s*(boundary\s*=)", r"; \1", safe_type, flags=re.IGNORECASE,
    )
    message = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + safe_type.encode("ascii", "replace")
        + b"\r\nMIME-Version: 1.0\r\n\r\n" + data
    )
    if not message.is_multipart():
        return None
    children = list(message.iter_parts())
    if len(children) > MAX_PARTS:
        return "Слишком много полей multipart (более 64). Используйте HEX."
    chunks = []
    for part in children:
        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        kind = part.get_content_type()
        raw = part.get_payload(decode=True)
        if not isinstance(raw, bytes):
            raw = b""
        raw = raw[:MAX_TEXT_BYTES + 1]
        chunks.append(f"Поле: {name or '(без имени)'}"
                      + (f"  |  файл: {filename}" if filename else "")
                      + f"\nТип: {kind}, размер: {len(raw)} байт")
        if len(raw) > MAX_TEXT_BYTES:
            chunks.append("Слишком большое поле. Используйте HEX.")
        else:
            display = _text_display(raw, kind)
            chunks.append(display if display is not None else _raw_hex(raw))
    return "\n\n".join(chunks) if chunks else ""


def format_http_body(
    data: bytes,
    content_type: str = "",
    content_encoding: str = "",
    *,
    mode: str = "text",
    truncated: bool = False,
    page: int = 0,
) -> str:
    """Render text or original-byte HEX, with conservative compression checks.

    The HTTPS recorder may have already removed the HTTP Content-Encoding,
    while preserving the original header. Only decompress if bytes actually
    carry the matching signature. application/zlib may add another layer.
    """
    if mode == "hex":
        result = _raw_hex(data)
        if truncated:
            result += "\n… Исходное тело длиннее 128 КиБ; показан фрагмент."
        return result
    if mode != "text":
        raise ValueError("Unknown body display mode")
    if not isinstance(page, int) or not 0 <= page < (
        MAX_INFLATE_BYTES // MAX_TEXT_BYTES
    ):
        raise ValueError("Invalid decoded body preview page")
    if not data:
        return ""
    if truncated:
        return (
            "Тело длиннее 128 КиБ. Для безопасного отображения оно "
            "не распаковывается и не разбирается целиком.\n"
            + _raw_hex(data)
        )
    raw = data
    details: list[str] = []
    inflation_limited = False
    encodings = [v.strip().lower() for v in content_encoding.split(",") if v.strip()]
    if len(encodings) > 3:
        return "Слишком много уровней HTTP-сжатия.\n" + _raw_hex(raw)
    for encoding in reversed(encodings):
        if inflation_limited:
            break
        if encoding in ("gzip", "x-gzip"):
            if data.startswith(b"\x1f\x8b"):
                try:
                    data, hit_limit = _inflate(data, zlib.MAX_WBITS | 16)
                    inflation_limited |= hit_limit
                except (ValueError, zlib.error) as exc:
                    return f"Ошибка распаковки gzip: {exc}\n" + _raw_hex(raw)
                details.append("gzip")
            else:
                details.append("gzip уже снят при записи или отсутствует в сохранённых байтах")
        elif encoding in ("deflate", "zlib"):
            if _is_zlib(data):
                try:
                    data, hit_limit = _inflate(data, zlib.MAX_WBITS)
                    inflation_limited |= hit_limit
                except (ValueError, zlib.error) as exc:
                    return f"Ошибка распаковки zlib: {exc}\n" + _raw_hex(raw)
                details.append("zlib")
            elif encoding == "deflate":
                # Raw deflate has no reliable magic bytes. Do not guess.
                details.append("deflate не распознан; исходные байты сохранены")
        elif encoding not in ("identity",):
            details.append(f"Неподдерживаемое Content-Encoding: {encoding}")
    if not inflation_limited and "zlib" in content_type.lower() and _is_zlib(data):
        try:
            data, hit_limit = _inflate(data, zlib.MAX_WBITS)
            inflation_limited |= hit_limit
        except (ValueError, zlib.error) as exc:
            return f"Ошибка распаковки вложенного zlib: {exc}\n" + _raw_hex(raw)
        details.append("zlib (из Content-Type)")
    if (
        not inflation_limited
        and data.startswith(b"\x1f\x8b")
        and not any(x == "gzip" for x in details)
    ):
        try:
            data, hit_limit = _inflate(data, zlib.MAX_WBITS | 16)
            inflation_limited |= hit_limit
        except (ValueError, zlib.error) as exc:
            return f"Ошибка распаковки gzip: {exc}\n" + _raw_hex(raw)
        details.append("gzip (по сигнатуре)")
    # zlib data can also be inside application/octet-stream or be nested.
    if not inflation_limited and _is_zlib(data) and (
        "zlib" in content_type.lower()
        or details and any("gzip" in x or "zlib" in x for x in details)
    ):
        try:
            data, hit_limit = _inflate(data, zlib.MAX_WBITS)
            inflation_limited |= hit_limit
        except (ValueError, zlib.error) as exc:
            return f"Ошибка распаковки zlib: {exc}\n" + _raw_hex(raw)
        details.append("вложенный zlib")
    total_pages = max(1, (len(data) + MAX_TEXT_BYTES - 1) // MAX_TEXT_BYTES)
    start = page * MAX_TEXT_BYTES
    if start >= len(data):
        return (
            f"Фрагмента {page + 1} нет. "
            f"Доступно фрагментов: {total_pages}. "
            "Выберите меньший номер."
        )
    end = min(len(data), start + MAX_TEXT_BYTES)
    fragment = data[start:end]
    incomplete = inflation_limited or total_pages > 1
    if content_type.casefold().startswith("multipart/form-data") and not incomplete:
        body = _multipart(fragment, content_type)
        if body is None:
            return "Не удалось разобрать multipart/form-data.\n" + _raw_hex(raw)
    else:
        body = _text_display(
            fragment, content_type, incomplete=incomplete
        )
        if body is None:
            return (
                "Текстовый формат не подтверждён даже после распаковки; "
                "показаны исходные байты.\n" + _raw_hex(raw)
            )
    if incomplete:
        note = (
            f"Фрагмент {page + 1} из {total_pages} "
            f"(байты {start + 1}–{end} после распаковки). "
            "Переключайте фрагменты рядом с режимом просмотра."
        )
        if inflation_limited:
            note += (
                " Превышен безопасный предел распаковки 8 МиБ; "
                "показано только начало, полнота потока не подтверждена."
            )
        body = note + "\n\n" + body
    # Do not say “decompressed” if the proxy had already decoded the body.
    if details:
        return "Обработка: " + "; ".join(details) + "\n\n" + body
    return body
