from __future__ import annotations

import hashlib
import hmac
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

QUIC_V1 = 0x00000001
QUIC_V2 = 0x6B3343CF

_VERSION_CONFIG = {
    QUIC_V1: {
        "name": "v1",
        "initial_type": 0,
        "salt": bytes.fromhex("38762cf7f55934b34d179ae6a4c80cadccbb7f0a"),
        "key_label": "quic key",
        "iv_label": "quic iv",
        "hp_label": "quic hp",
    },
    QUIC_V2: {
        "name": "v2",
        "initial_type": 1,
        "salt": bytes.fromhex("0dede3def700a6db819381be6e269dcbf9bd2ed9"),
        "key_label": "quicv2 key",
        "iv_label": "quicv2 iv",
        "hp_label": "quicv2 hp",
    },
}


def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    output = bytearray()
    previous = b""
    counter = 1
    while len(output) < length:
        previous = hmac.new(
            prk,
            previous + info + bytes([counter]),
            hashlib.sha256,
        ).digest()
        output.extend(previous)
        counter += 1
    return bytes(output[:length])


def _hkdf_expand_label(secret: bytes, label: str, length: int) -> bytes:
    full_label = b"tls13 " + label.encode("ascii")
    info = (
        length.to_bytes(2, "big")
        + bytes([len(full_label)])
        + full_label
        + b"\x00"
    )
    return _hkdf_expand(secret, info, length)


def derive_initial_keys(
    version: int,
    destination_connection_id: bytes,
    *,
    role: str = "client",
) -> dict[str, bytes] | None:
    config = _VERSION_CONFIG.get(version)
    if config is None or role not in {"client", "server"}:
        return None
    initial_secret = _hkdf_extract(
        config["salt"],
        destination_connection_id,
    )
    secret = _hkdf_expand_label(
        initial_secret,
        f"{role} in",
        32,
    )
    return {
        "secret": secret,
        "key": _hkdf_expand_label(secret, config["key_label"], 16),
        "iv": _hkdf_expand_label(secret, config["iv_label"], 12),
        "hp": _hkdf_expand_label(secret, config["hp_label"], 16),
    }


def _decode_varint(data: bytes, offset: int) -> tuple[int, int] | None:
    if offset >= len(data):
        return None
    first = data[offset]
    length = 1 << (first >> 6)
    if offset + length > len(data):
        return None
    value = first & 0x3F
    for byte in data[offset + 1 : offset + length]:
        value = (value << 8) | byte
    return value, offset + length


def _decode_packet_number(
    truncated: int,
    bits: int,
    largest: int | None,
) -> int:
    if largest is None:
        return truncated
    expected = largest + 1
    window = 1 << bits
    half_window = window // 2
    mask = window - 1
    candidate = (expected & ~mask) | truncated
    if (
        candidate <= expected - half_window
        and candidate < (1 << 62) - window
    ):
        return candidate + window
    if candidate > expected + half_window and candidate >= window:
        return candidate - window
    return candidate


def _header_mask(hp_key: bytes, sample: bytes) -> bytes:
    encryptor = Cipher(
        algorithms.AES(hp_key),
        modes.ECB(),
    ).encryptor()
    return encryptor.update(sample) + encryptor.finalize()


def _nonce(iv: bytes, packet_number: int) -> bytes:
    number = packet_number.to_bytes(len(iv), "big")
    return bytes(left ^ right for left, right in zip(iv, number))


def _parse_long_header(
    packet: bytes,
    offset: int,
) -> dict[str, Any] | None:
    if offset + 7 > len(packet):
        return None
    first = packet[offset]
    if not (first & 0x80) or not (first & 0x40):
        return None
    version = int.from_bytes(packet[offset + 1 : offset + 5], "big")
    cursor = offset + 5
    dcid_length = packet[cursor]
    cursor += 1
    if cursor + dcid_length + 1 > len(packet):
        return None
    dcid = packet[cursor : cursor + dcid_length]
    cursor += dcid_length
    scid_length = packet[cursor]
    cursor += 1
    if cursor + scid_length > len(packet):
        return None
    scid = packet[cursor : cursor + scid_length]
    cursor += scid_length
    return {
        "start": offset,
        "first": first,
        "version": version,
        "dcid": dcid,
        "scid": scid,
        "cursor": cursor,
    }


def _parse_initial_bounds(
    packet: bytes,
    header: dict[str, Any],
) -> dict[str, Any] | None:
    version = int(header["version"])
    config = _VERSION_CONFIG.get(version)
    if config is None:
        return None
    packet_type = (int(header["first"]) >> 4) & 0x03
    if packet_type != int(config["initial_type"]):
        return None
    cursor = int(header["cursor"])
    token = _decode_varint(packet, cursor)
    if token is None:
        return None
    token_length, cursor = token
    cursor += token_length
    if cursor > len(packet):
        return None
    length_value = _decode_varint(packet, cursor)
    if length_value is None:
        return None
    packet_length, pn_offset = length_value
    end = pn_offset + packet_length
    if end > len(packet) or packet_length < 17:
        return None
    return {
        **header,
        "packet_type": "initial",
        "pn_offset": pn_offset,
        "end": end,
    }


def _decrypt_client_initial(
    packet: bytes,
    bounds: dict[str, Any],
    *,
    largest_packet_number: int | None,
) -> tuple[bytes, int] | None:
    keys = derive_initial_keys(
        int(bounds["version"]),
        bytes(bounds["dcid"]),
        role="client",
    )
    if keys is None:
        return None
    start = int(bounds["start"])
    pn_offset = int(bounds["pn_offset"])
    end = int(bounds["end"])
    sample_offset = pn_offset + 4
    if sample_offset + 16 > end:
        return None
    mask = _header_mask(
        keys["hp"],
        packet[sample_offset : sample_offset + 16],
    )
    first = packet[start] ^ (mask[0] & 0x0F)
    pn_length = (first & 0x03) + 1
    if pn_offset + pn_length > end:
        return None
    protected_pn = packet[pn_offset : pn_offset + pn_length]
    unprotected_pn = bytes(
        value ^ mask[index + 1]
        for index, value in enumerate(protected_pn)
    )
    truncated = int.from_bytes(unprotected_pn, "big")
    packet_number = _decode_packet_number(
        truncated,
        pn_length * 8,
        largest_packet_number,
    )
    header = bytearray(packet[start : pn_offset + pn_length])
    header[0] = first
    relative_pn_offset = pn_offset - start
    header[
        relative_pn_offset : relative_pn_offset + pn_length
    ] = unprotected_pn
    ciphertext = packet[pn_offset + pn_length : end]
    try:
        plaintext = AESGCM(keys["key"]).decrypt(
            _nonce(keys["iv"], packet_number),
            ciphertext,
            bytes(header),
        )
    except InvalidTag:
        return None
    return plaintext, packet_number


def _skip_ack(
    data: bytes,
    cursor: int,
    *,
    ecn: bool,
) -> int | None:
    values: list[int] = []
    for _ in range(4):
        decoded = _decode_varint(data, cursor)
        if decoded is None:
            return None
        value, cursor = decoded
        values.append(value)
    range_count = values[2]
    for _ in range(range_count):
        for _ in range(2):
            decoded = _decode_varint(data, cursor)
            if decoded is None:
                return None
            _, cursor = decoded
    if ecn:
        for _ in range(3):
            decoded = _decode_varint(data, cursor)
            if decoded is None:
                return None
            _, cursor = decoded
    return cursor


def _crypto_stream(plaintext: bytes) -> bytes:
    cursor = 0
    fragments: list[tuple[int, bytes]] = []
    while cursor < len(plaintext):
        frame_value = _decode_varint(plaintext, cursor)
        if frame_value is None:
            break
        frame_type, cursor = frame_value
        if frame_type in {0x00, 0x01}:
            continue
        if frame_type in {0x02, 0x03}:
            next_cursor = _skip_ack(
                plaintext,
                cursor,
                ecn=frame_type == 0x03,
            )
            if next_cursor is None:
                break
            cursor = next_cursor
            continue
        if frame_type == 0x06:
            offset_value = _decode_varint(plaintext, cursor)
            if offset_value is None:
                break
            crypto_offset, cursor = offset_value
            length_value = _decode_varint(plaintext, cursor)
            if length_value is None:
                break
            crypto_length, cursor = length_value
            end = cursor + crypto_length
            if end > len(plaintext):
                break
            fragments.append(
                (crypto_offset, plaintext[cursor:end])
            )
            cursor = end
            continue
        if frame_type in {0x1C, 0x1D}:
            error_value = _decode_varint(plaintext, cursor)
            if error_value is None:
                break
            _, cursor = error_value
            if frame_type == 0x1C:
                frame_value = _decode_varint(plaintext, cursor)
                if frame_value is None:
                    break
                _, cursor = frame_value
            reason_value = _decode_varint(plaintext, cursor)
            if reason_value is None:
                break
            reason_length, cursor = reason_value
            cursor += reason_length
            if cursor > len(plaintext):
                break
            continue
        break

    if not fragments:
        return b""
    fragments.sort(key=lambda item: item[0])
    stream = bytearray()
    expected = 0
    for offset, fragment in fragments:
        if offset > expected:
            break
        overlap = max(0, expected - offset)
        if overlap < len(fragment):
            stream.extend(fragment[overlap:])
            expected += len(fragment) - overlap
    return bytes(stream)


def parse_tls_client_hello(
    data: bytes,
) -> dict[str, Any] | None:
    if len(data) < 4 or data[0] != 0x01:
        return None
    body_length = int.from_bytes(data[1:4], "big")
    body = data[4 : 4 + body_length]
    if len(body) < body_length or len(body) < 35:
        return None
    cursor = 34
    session_length = body[cursor]
    cursor += 1 + session_length
    if cursor + 2 > len(body):
        return None
    cipher_length = int.from_bytes(
        body[cursor : cursor + 2],
        "big",
    )
    cursor += 2 + cipher_length
    if cursor >= len(body):
        return None
    compression_length = body[cursor]
    cursor += 1 + compression_length
    if cursor + 2 > len(body):
        return None
    extensions_length = int.from_bytes(
        body[cursor : cursor + 2],
        "big",
    )
    cursor += 2
    end = min(len(body), cursor + extensions_length)
    sni: str | None = None
    alpn: list[str] = []
    while cursor + 4 <= end:
        extension_type = int.from_bytes(
            body[cursor : cursor + 2],
            "big",
        )
        extension_length = int.from_bytes(
            body[cursor + 2 : cursor + 4],
            "big",
        )
        cursor += 4
        extension = body[cursor : cursor + extension_length]
        cursor += extension_length
        if len(extension) != extension_length:
            break
        if extension_type == 0 and len(extension) >= 5:
            names_length = int.from_bytes(
                extension[:2],
                "big",
            )
            name_cursor = 2
            name_end = min(
                len(extension),
                2 + names_length,
            )
            while name_cursor + 3 <= name_end:
                name_type = extension[name_cursor]
                name_length = int.from_bytes(
                    extension[
                        name_cursor + 1 : name_cursor + 3
                    ],
                    "big",
                )
                name_cursor += 3
                name = extension[
                    name_cursor : name_cursor + name_length
                ]
                name_cursor += name_length
                if (
                    name_type == 0
                    and len(name) == name_length
                ):
                    value = name.decode(
                        "ascii",
                        errors="ignore",
                    ).strip()
                    if value:
                        sni = value
                        break
        elif extension_type == 16 and len(extension) >= 2:
            protocols_length = int.from_bytes(
                extension[:2],
                "big",
            )
            alpn_cursor = 2
            alpn_end = min(
                len(extension),
                2 + protocols_length,
            )
            while alpn_cursor < alpn_end:
                item_length = extension[alpn_cursor]
                alpn_cursor += 1
                item = extension[
                    alpn_cursor : alpn_cursor + item_length
                ]
                alpn_cursor += item_length
                if len(item) != item_length:
                    break
                value = item.decode(
                    "ascii",
                    errors="ignore",
                ).strip()
                if value and value not in alpn:
                    alpn.append(value)
    return {"sni": sni, "alpn": alpn}


def inspect_quic_datagram(
    payload: bytes,
    *,
    largest_packet_number: int | None = None,
) -> dict[str, Any] | None:
    """Inspect a recognizable QUIC long-header packet.

    QUIC v1/v2 client Initial keys are public derivations from the packet
    Destination Connection ID. This permits forensic extraction of Initial
    ClientHello metadata without MITM. 1-RTT application data is never
    decrypted here.
    """

    header = _parse_long_header(payload, 0)
    if header is None:
        return None
    version = int(header["version"])
    result: dict[str, Any] = {
        "detected": True,
        "version": (
            _VERSION_CONFIG[version]["name"]
            if version in _VERSION_CONFIG
            else f"0x{version:08x}"
        ),
        "version_number": version,
        "packet_type": "long-header",
        "destination_connection_id": (
            bytes(header["dcid"]).hex()
        ),
        "source_connection_id": (
            bytes(header["scid"]).hex()
        ),
        "initial_decrypted": False,
        "packet_number": None,
        "sni": None,
        "alpn": [],
        "application_protocol": "QUIC",
    }
    bounds = _parse_initial_bounds(payload, header)
    if bounds is None:
        if version in _VERSION_CONFIG:
            packet_type = (
                (int(header["first"]) >> 4) & 0x03
            )
            if version == QUIC_V1:
                names = {
                    0: "initial",
                    1: "0-rtt",
                    2: "handshake",
                    3: "retry",
                }
            else:
                names = {
                    0: "retry",
                    1: "initial",
                    2: "0-rtt",
                    3: "handshake",
                }
            result["packet_type"] = names.get(
                packet_type,
                "long-header",
            )
        return result

    result["packet_type"] = "initial"
    decrypted = _decrypt_client_initial(
        payload,
        bounds,
        largest_packet_number=largest_packet_number,
    )
    if decrypted is None:
        return result

    plaintext, packet_number = decrypted
    result["initial_decrypted"] = True
    result["packet_number"] = packet_number
    hello = parse_tls_client_hello(
        _crypto_stream(plaintext)
    )
    if hello is None:
        return result
    result["sni"] = hello.get("sni")
    result["alpn"] = list(
        hello.get("alpn") or []
    )
    if any(
        value == "h3" or value.startswith("h3-")
        for value in result["alpn"]
    ):
        result["application_protocol"] = "HTTP/3"
    return result
