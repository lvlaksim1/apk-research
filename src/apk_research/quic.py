from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import hmac
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

QUIC_VERSION_1 = 0x00000001
QUIC_VERSION_2 = 0x6B3343CF

_VERSION_CONFIG: dict[int, dict[str, Any]] = {
    QUIC_VERSION_1: {
        "name": "v1",
        "salt": bytes.fromhex(
            "38762cf7f55934b34d179ae6a4c80cadccbb7f0a"
        ),
        "key_label": b"quic key",
        "iv_label": b"quic iv",
        "hp_label": b"quic hp",
        "types": {
            0: "initial",
            1: "0-rtt",
            2: "handshake",
            3: "retry",
        },
    },
    QUIC_VERSION_2: {
        "name": "v2",
        "salt": bytes.fromhex(
            "0dede3def700a6db819381be6e269dcbf9bd2ed9"
        ),
        "key_label": b"quicv2 key",
        "iv_label": b"quicv2 iv",
        "hp_label": b"quicv2 hp",
        "types": {
            1: "initial",
            2: "0-rtt",
            3: "handshake",
            0: "retry",
        },
    },
}


def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt, ikm, sha256).digest()


def _hkdf_expand(
    prk: bytes,
    info: bytes,
    length: int,
) -> bytes:
    output = b""
    previous = b""
    counter = 1
    while len(output) < length:
        previous = hmac.new(
            prk,
            previous + info + bytes([counter]),
            sha256,
        ).digest()
        output += previous
        counter += 1
    return output[:length]


def _hkdf_expand_label(
    secret: bytes,
    label: bytes,
    length: int,
) -> bytes:
    full_label = b"tls13 " + label
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
    sender: str,
) -> dict[str, bytes]:
    """Derive public QUIC Initial protection material.

    Initial secrets are intentionally derivable by passive observers from the
    version salt and the client's initial Destination Connection ID. This does
    not provide keys for Handshake or 1-RTT application data.
    """

    if sender not in {"client", "server"}:
        raise ValueError("sender must be 'client' or 'server'")
    config = _VERSION_CONFIG[version]
    initial_secret = _hkdf_extract(
        config["salt"],
        destination_connection_id,
    )
    role_label = (
        b"client in"
        if sender == "client"
        else b"server in"
    )
    secret = _hkdf_expand_label(
        initial_secret,
        role_label,
        32,
    )
    return {
        "secret": secret,
        "key": _hkdf_expand_label(
            secret,
            config["key_label"],
            16,
        ),
        "iv": _hkdf_expand_label(
            secret,
            config["iv_label"],
            12,
        ),
        "hp": _hkdf_expand_label(
            secret,
            config["hp_label"],
            16,
        ),
    }


def decode_varint(
    data: bytes,
    offset: int,
) -> tuple[int, int]:
    if offset >= len(data):
        raise ValueError("truncated QUIC varint")
    first = data[offset]
    length = 1 << (first >> 6)
    if offset + length > len(data):
        raise ValueError("truncated QUIC varint")
    value = first & 0x3F
    for byte in data[offset + 1 : offset + length]:
        value = (value << 8) | byte
    return value, offset + length


def _parse_long_header(
    data: bytes,
) -> dict[str, Any] | None:
    if len(data) < 7 or not (data[0] & 0x80):
        return None

    version = int.from_bytes(data[1:5], "big")
    config = _VERSION_CONFIG.get(version)
    cursor = 5
    dcid_length = data[cursor]
    cursor += 1
    if (
        config is not None
        and dcid_length > 20
    ):
        return None
    if cursor + dcid_length + 1 > len(data):
        return None
    dcid = data[cursor : cursor + dcid_length]
    cursor += dcid_length
    scid_length = data[cursor]
    cursor += 1
    if (
        config is not None
        and scid_length > 20
    ):
        return None
    if cursor + scid_length > len(data):
        return None
    scid = data[cursor : cursor + scid_length]
    cursor += scid_length

    if version == 0:
        return {
            "version": 0,
            "version_name": "negotiation",
            "packet_type": "version-negotiation",
            "dcid": dcid,
            "scid": scid,
            "pn_offset": None,
            "packet_end": len(data),
        }

    type_bits = (data[0] >> 4) & 0x03
    packet_type = (
        config["types"].get(type_bits)
        if config is not None
        else "unknown-long"
    )
    value: dict[str, Any] = {
        "version": version,
        "version_name": (
            config["name"]
            if config is not None
            else f"0x{version:08x}"
        ),
        "packet_type": packet_type,
        "dcid": dcid,
        "scid": scid,
        "pn_offset": None,
        "packet_end": len(data),
    }
    if packet_type != "initial":
        return value

    try:
        token_length, cursor = decode_varint(
            data,
            cursor,
        )
        cursor += token_length
        if cursor > len(data):
            return None
        protected_length, cursor = decode_varint(
            data,
            cursor,
        )
    except ValueError:
        return None

    packet_end = cursor + protected_length
    if packet_end > len(data):
        return None
    value.update(
        {
            "pn_offset": cursor,
            "packet_end": packet_end,
            "length": protected_length,
        }
    )
    return value


def _packet_nonce(
    iv: bytes,
    packet_number: int,
) -> bytes:
    encoded = packet_number.to_bytes(
        len(iv),
        "big",
    )
    return bytes(
        left ^ right
        for left, right in zip(iv, encoded)
    )


def decrypt_initial(
    data: bytes,
    *,
    initial_dcid: bytes,
    sender: str,
) -> dict[str, Any] | None:
    header = _parse_long_header(data)
    if (
        not header
        or header["packet_type"] != "initial"
        or header["version"] not in _VERSION_CONFIG
    ):
        return None

    packet_number_offset = header["pn_offset"]
    packet_end = int(header["packet_end"])
    if (
        packet_number_offset is None
        or packet_number_offset + 4 + 16 > packet_end
    ):
        return None

    keys = derive_initial_keys(
        int(header["version"]),
        initial_dcid,
        sender,
    )
    sample = data[
        packet_number_offset + 4 :
        packet_number_offset + 20
    ]
    encryptor = Cipher(
        algorithms.AES(keys["hp"]),
        modes.ECB(),
    ).encryptor()
    mask = (
        encryptor.update(sample)
        + encryptor.finalize()
    )[:5]

    first = data[0] ^ (mask[0] & 0x0F)
    packet_number_length = (first & 0x03) + 1
    if (
        packet_number_offset + packet_number_length
        > packet_end
    ):
        return None

    packet_number_bytes = bytes(
        data[packet_number_offset + index]
        ^ mask[index + 1]
        for index in range(packet_number_length)
    )
    packet_number = int.from_bytes(
        packet_number_bytes,
        "big",
    )
    associated_data = (
        bytes([first])
        + data[1:packet_number_offset]
        + packet_number_bytes
    )
    ciphertext = data[
        packet_number_offset + packet_number_length :
        packet_end
    ]
    try:
        plaintext = AESGCM(keys["key"]).decrypt(
            _packet_nonce(
                keys["iv"],
                packet_number,
            ),
            ciphertext,
            associated_data,
        )
    except InvalidTag:
        return None

    return {
        "plaintext": plaintext,
        "packet_number": packet_number,
        "sender": sender,
        "header": header,
    }


def _crypto_fragments(
    plaintext: bytes,
) -> list[tuple[int, bytes]]:
    fragments: list[tuple[int, bytes]] = []
    cursor = 0
    while cursor < len(plaintext):
        frame_type = plaintext[cursor]
        cursor += 1
        if frame_type in {0x00, 0x01}:
            continue
        if frame_type in {0x02, 0x03}:
            try:
                for _ in range(4):
                    _, cursor = decode_varint(
                        plaintext,
                        cursor,
                    )
                if frame_type == 0x03:
                    for _ in range(3):
                        _, cursor = decode_varint(
                            plaintext,
                            cursor,
                        )
            except ValueError:
                break
            continue
        if frame_type != 0x06:
            break
        try:
            offset, cursor = decode_varint(
                plaintext,
                cursor,
            )
            length, cursor = decode_varint(
                plaintext,
                cursor,
            )
        except ValueError:
            break
        if cursor + length > len(plaintext):
            break
        fragments.append(
            (
                offset,
                plaintext[cursor : cursor + length],
            )
        )
        cursor += length
    return fragments


def _contiguous_crypto(
    fragments: dict[int, bytes],
) -> bytes:
    if 0 not in fragments:
        return b""
    value = bytearray()
    cursor = 0
    while cursor in fragments:
        chunk = fragments[cursor]
        value.extend(chunk)
        cursor += len(chunk)
    return bytes(value)


def _parse_client_hello(
    data: bytes,
) -> dict[str, Any] | None:
    if len(data) < 4 or data[0] != 0x01:
        return None
    message_length = int.from_bytes(
        data[1:4],
        "big",
    )
    if len(data) < 4 + message_length:
        return None
    body = data[4 : 4 + message_length]
    if len(body) < 34:
        return None

    cursor = 34
    if cursor >= len(body):
        return None
    session_id_length = body[cursor]
    cursor += 1 + session_id_length
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
    extensions_end = min(
        len(body),
        cursor + extensions_length,
    )

    server_name: str | None = None
    alpn: list[str] = []
    while cursor + 4 <= extensions_end:
        extension_type = int.from_bytes(
            body[cursor : cursor + 2],
            "big",
        )
        extension_length = int.from_bytes(
            body[cursor + 2 : cursor + 4],
            "big",
        )
        cursor += 4
        extension = body[
            cursor : cursor + extension_length
        ]
        cursor += extension_length

        if extension_type == 0 and len(extension) >= 5:
            list_length = int.from_bytes(
                extension[:2],
                "big",
            )
            name_cursor = 2
            name_end = min(
                len(extension),
                2 + list_length,
            )
            while name_cursor + 3 <= name_end:
                name_type = extension[name_cursor]
                name_length = int.from_bytes(
                    extension[
                        name_cursor + 1 :
                        name_cursor + 3
                    ],
                    "big",
                )
                name_cursor += 3
                name = extension[
                    name_cursor :
                    name_cursor + name_length
                ]
                name_cursor += name_length
                if name_type == 0 and server_name is None:
                    text = name.decode(
                        "ascii",
                        errors="ignore",
                    ).strip()
                    server_name = text or None

        elif extension_type == 16 and len(extension) >= 2:
            list_length = int.from_bytes(
                extension[:2],
                "big",
            )
            alpn_cursor = 2
            alpn_end = min(
                len(extension),
                2 + list_length,
            )
            while alpn_cursor < alpn_end:
                length = extension[alpn_cursor]
                alpn_cursor += 1
                if alpn_cursor + length > alpn_end:
                    break
                text = extension[
                    alpn_cursor :
                    alpn_cursor + length
                ].decode(
                    "ascii",
                    errors="ignore",
                ).strip()
                alpn_cursor += length
                if text:
                    alpn.append(text)

    return {
        "sni": server_name,
        "alpn": alpn,
    }


@dataclass
class QuicFlowInspector:
    """Stateful passive QUIC metadata inspector for one UDP 5-tuple."""

    client_initial_dcid: bytes | None = None
    version: int | None = None
    crypto_fragments: dict[int, bytes] = field(
        default_factory=dict
    )
    sni: str | None = None
    alpn: list[str] = field(default_factory=list)
    confirmed: bool = False

    def inspect(
        self,
        payload: bytes,
        *,
        direction: str | None,
    ) -> dict[str, Any] | None:
        header = _parse_long_header(payload)
        if header is None:
            if (
                self.confirmed
                and self.version is not None
                and payload
                and not (payload[0] & 0x80)
            ):
                return {
                    "version": _VERSION_CONFIG[
                        self.version
                    ]["name"],
                    "version_number": self.version,
                    "packet_type": "1-rtt",
                    "initial_decrypted": False,
                    "sni": self.sni,
                    "alpn": list(self.alpn),
                }
            return None

        if (
            not (payload[0] & 0x40)
            and header["version"] != 0
        ):
            return None

        version = int(header["version"])

        # v0.16.1 evidence boundary:
        # an arbitrary long-header-shaped UDP payload is not proof of QUIC.
        # We only establish a flow from versions whose packet protection we
        # actually implement and can authenticate (v1/v2 Initial).
        if version not in _VERSION_CONFIG and version != 0:
            return None

        if version == 0:
            if not self.confirmed:
                return None
            return {
                "version": "negotiation",
                "version_number": 0,
                "packet_type": "version-negotiation",
                "initial_decrypted": False,
                "sni": self.sni,
                "alpn": list(self.alpn),
            }

        result: dict[str, Any] = {
            "version": header["version_name"],
            "version_number": version,
            "packet_type": header["packet_type"],
            "destination_connection_id": (
                header["dcid"].hex()
            ),
            "source_connection_id": (
                header["scid"].hex()
            ),
            "initial_decrypted": False,
            "sni": self.sni,
            "alpn": list(self.alpn),
        }
        if header["packet_type"] != "initial":
            if (
                self.confirmed
                and self.version == version
            ):
                return result
            return None

        # RFC 9000 requires every client UDP datagram carrying an Initial
        # packet to be padded/coalesced to at least 1200 bytes. A smaller
        # outbound datagram therefore cannot establish a confirmed flow.
        if (
            direction == "outbound"
            and len(payload) < 1200
        ):
            return None

        candidate_initial_dcid = (
            self.client_initial_dcid
            or header["dcid"]
        )
        initial_dcid = candidate_initial_dcid
        senders = (
            ["client"]
            if direction == "outbound"
            else ["server"]
            if direction == "inbound"
            else ["client", "server"]
        )

        for sender in senders:
            decrypted = decrypt_initial(
                payload,
                initial_dcid=initial_dcid,
                sender=sender,
            )
            if decrypted is None:
                continue
            result["initial_decrypted"] = True
            result["initial_sender"] = sender
            result["packet_number"] = decrypted[
                "packet_number"
            ]
            self.confirmed = True
            self.version = version
            if (
                sender == "client"
                and self.client_initial_dcid is None
            ):
                self.client_initial_dcid = (
                    candidate_initial_dcid
                )

            if sender == "client":
                for offset, data in _crypto_fragments(
                    decrypted["plaintext"]
                ):
                    previous = self.crypto_fragments.get(
                        offset
                    )
                    if (
                        previous is None
                        or len(data) > len(previous)
                    ):
                        self.crypto_fragments[offset] = data
                hello = _parse_client_hello(
                    _contiguous_crypto(
                        self.crypto_fragments
                    )
                )
                if hello is not None:
                    self.sni = hello["sni"] or self.sni
                    self.alpn = list(
                        dict.fromkeys(
                            self.alpn
                            + list(hello["alpn"])
                        )
                    )
                    result["sni"] = self.sni
                    result["alpn"] = list(self.alpn)
            break

        if not result["initial_decrypted"]:
            if (
                self.confirmed
                and self.version == version
            ):
                return result
            return None
        return result
