from __future__ import annotations

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from apk_research.network_attribution import build_flow_inventory
from apk_research.quic import (
    QUIC_V1,
    QUIC_V2,
    QuicInitialTracker,
    derive_initial_keys,
    inspect_quic_datagram,
    parse_tls_client_hello,
)


def test_rfc9001_initial_keys() -> None:
    keys = derive_initial_keys(
        QUIC_V1,
        bytes.fromhex("8394c8f03e515708"),
    )
    assert keys is not None
    assert keys["secret"].hex() == (
        "c00cf151ca5be075ed0ebfb5c80323c4"
        "2d6b7db67881289af4008f1f6c357aea"
    )
    assert keys["key"].hex() == (
        "1f369613dd76d5467730efcbe3b1a22d"
    )
    assert keys["iv"].hex() == (
        "fa044b2f42a3fd3b46fb255c"
    )
    assert keys["hp"].hex() == (
        "9f50449e04a0e810283a1e9933adedd2"
    )


def test_rfc9369_initial_keys() -> None:
    keys = derive_initial_keys(
        QUIC_V2,
        bytes.fromhex("8394c8f03e515708"),
    )
    assert keys is not None
    assert keys["secret"].hex() == (
        "14ec9d6eb9fd7af83bf5a668bc17a7e2"
        "83766aade7ecd0891f70f9ff7f4bf47b"
    )
    assert keys["key"].hex() == (
        "8b1a0bc121284290a29e0971b5cd045d"
    )
    assert keys["iv"].hex() == (
        "91f73e2351d8fa91660e909f"
    )
    assert keys["hp"].hex() == (
        "45b95e15235d6f45a6b19cbcb0294ba9"
    )


def _client_hello() -> bytes:
    sni = b"api.example.com"
    sni_entry = (
        b"\x00"
        + len(sni).to_bytes(2, "big")
        + sni
    )
    sni_ext_data = (
        len(sni_entry).to_bytes(2, "big")
        + sni_entry
    )
    sni_ext = (
        b"\x00\x00"
        + len(sni_ext_data).to_bytes(2, "big")
        + sni_ext_data
    )
    protocols = b"\x02h3\x05h3-29"
    alpn_data = (
        len(protocols).to_bytes(2, "big")
        + protocols
    )
    alpn_ext = (
        b"\x00\x10"
        + len(alpn_data).to_bytes(2, "big")
        + alpn_data
    )
    extensions = sni_ext + alpn_ext
    body = (
        b"\x03\x03"
        + b"\x11" * 32
        + b"\x00"
        + b"\x00\x02\x13\x01"
        + b"\x01\x00"
        + len(extensions).to_bytes(2, "big")
        + extensions
    )
    return (
        b"\x01"
        + len(body).to_bytes(3, "big")
        + body
    )


def test_client_hello_sni_and_alpn() -> None:
    parsed = parse_tls_client_hello(
        _client_hello()
    )
    assert parsed == {
        "sni": "api.example.com",
        "alpn": ["h3", "h3-29"],
    }


def _varint(value: int) -> bytes:
    if value < 64:
        return bytes([value])
    if value < 16384:
        return (0x4000 | value).to_bytes(
            2,
            "big",
        )
    raise ValueError(value)


def _protected_client_initial() -> bytes:
    dcid = bytes.fromhex(
        "8394c8f03e515708"
    )
    keys = derive_initial_keys(
        QUIC_V1,
        dcid,
    )
    assert keys is not None
    hello = _client_hello()
    plaintext = (
        b"\x06"
        + _varint(0)
        + _varint(len(hello))
        + hello
        + b"\x00" * 32
    )
    packet_number = 7
    packet_number_bytes = (
        packet_number.to_bytes(2, "big")
    )
    first = 0xC1
    prefix = (
        bytes([first])
        + QUIC_V1.to_bytes(4, "big")
        + bytes([len(dcid)])
        + dcid
        + b"\x00"
        + _varint(0)
    )
    length = (
        len(packet_number_bytes)
        + len(plaintext)
        + 16
    )
    header = (
        prefix
        + _varint(length)
        + packet_number_bytes
    )
    nonce = bytes(
        left ^ right
        for left, right in zip(
            keys["iv"],
            packet_number.to_bytes(
                12,
                "big",
            ),
        )
    )
    ciphertext = AESGCM(
        keys["key"]
    ).encrypt(
        nonce,
        plaintext,
        header,
    )
    pn_offset = (
        len(header)
        - len(packet_number_bytes)
    )
    protected = bytearray(
        header + ciphertext
    )
    sample = bytes(
        protected[
            pn_offset + 4 : pn_offset + 20
        ]
    )
    encryptor = Cipher(
        algorithms.AES(keys["hp"]),
        modes.ECB(),
    ).encryptor()
    mask = (
        encryptor.update(sample)
        + encryptor.finalize()
    )
    protected[0] ^= mask[0] & 0x0F
    for index in range(
        len(packet_number_bytes)
    ):
        protected[
            pn_offset + index
        ] ^= mask[index + 1]
    return bytes(protected)


def test_inspect_synthetic_v1_client_initial() -> None:
    result = inspect_quic_datagram(
        _protected_client_initial()
    )
    assert result is not None
    assert result["version"] == "v1"
    assert result["packet_type"] == "initial"
    assert result["initial_decrypted"] is True
    assert result["packet_number"] == 7
    assert result["sni"] == (
        "api.example.com"
    )
    assert result["alpn"] == [
        "h3",
        "h3-29",
    ]
    assert (
        result["application_protocol"]
        == "HTTP/3"
    )


class _UnknownIndex:
    package = "com.example"
    package_uid = 10123
    uid_packages = ["com.example"]

    def attribute_packet(
        self,
        packet: dict[str, object],
    ) -> dict[str, object]:
        return {
            "package": self.package,
            "uid": self.package_uid,
            "confidence": "UNKNOWN",
            "evidence": (
                "test-unattributed"
            ),
        }


def test_flow_inventory_preserves_quic_intelligence() -> None:
    packet = {
        "epoch": 1000.0,
        "captured_length": 1200,
        "protocol": "udp",
        "direction": "outbound",
        "src": "10.0.2.15",
        "src_port": 50000,
        "dst": "203.0.113.10",
        "dst_port": 443,
        "dns_query": None,
        "tls_sni": "api.example.com",
        "quic_version": "v1",
        "quic_packet_type": "initial",
        "quic_initial_decrypted": True,
        "quic_sni": "api.example.com",
        "quic_alpn": ["h3"],
        "application_protocol": "HTTP/3",
    }

    inventory = build_flow_inventory(
        [packet],
        _UnknownIndex(),
    )

    assert (
        inventory["schema_version"]
        == "0.3"
    )
    assert inventory["summary"][
        "quic_flow_count"
    ] == 1
    assert inventory["summary"][
        "http3_flow_count"
    ] == 1
    flow = inventory["flows"][0]
    assert flow["quic_versions"] == [
        "v1"
    ]
    assert flow["quic_packet_types"] == [
        "initial"
    ]
    assert flow["quic_alpn"] == ["h3"]
    assert flow["application_protocols"] == [
        "HTTP/3"
    ]
    assert flow[
        "quic_initial_decrypted_packet_count"
    ] == 1



def _protected_crypto_fragment(
    fragment: bytes,
    *,
    crypto_offset: int,
    packet_number: int,
) -> bytes:
    dcid = bytes.fromhex(
        "8394c8f03e515708"
    )
    keys = derive_initial_keys(
        QUIC_V1,
        dcid,
    )
    assert keys is not None
    plaintext = (
        b"\x06"
        + _varint(crypto_offset)
        + _varint(len(fragment))
        + fragment
        + b"\x00" * 24
    )
    packet_number_bytes = (
        packet_number.to_bytes(2, "big")
    )
    prefix = (
        b"\xc1"
        + QUIC_V1.to_bytes(4, "big")
        + bytes([len(dcid)])
        + dcid
        + b"\x00"
        + _varint(0)
    )
    header = (
        prefix
        + _varint(
            len(packet_number_bytes)
            + len(plaintext)
            + 16
        )
        + packet_number_bytes
    )
    nonce = bytes(
        left ^ right
        for left, right in zip(
            keys["iv"],
            packet_number.to_bytes(
                12,
                "big",
            ),
        )
    )
    ciphertext = AESGCM(
        keys["key"]
    ).encrypt(
        nonce,
        plaintext,
        header,
    )
    pn_offset = (
        len(header)
        - len(packet_number_bytes)
    )
    protected = bytearray(
        header + ciphertext
    )
    sample = bytes(
        protected[
            pn_offset + 4 : pn_offset + 20
        ]
    )
    encryptor = Cipher(
        algorithms.AES(keys["hp"]),
        modes.ECB(),
    ).encryptor()
    mask = (
        encryptor.update(sample)
        + encryptor.finalize()
    )
    protected[0] ^= mask[0] & 0x0F
    for index in range(
        len(packet_number_bytes)
    ):
        protected[
            pn_offset + index
        ] ^= mask[index + 1]
    return bytes(protected)


def test_tracker_reassembles_split_client_hello() -> None:
    hello = _client_hello()
    split = len(hello) // 2
    tracker = QuicInitialTracker()

    first = tracker.inspect(
        _protected_crypto_fragment(
            hello[:split],
            crypto_offset=0,
            packet_number=0,
        )
    )
    assert first is not None
    assert first["initial_decrypted"] is True
    assert first["sni"] is None

    second = tracker.inspect(
        _protected_crypto_fragment(
            hello[split:],
            crypto_offset=split,
            packet_number=1,
        )
    )
    assert second is not None
    assert second["sni"] == (
        "api.example.com"
    )
    assert second["alpn"] == [
        "h3",
        "h3-29",
    ]
    assert (
        second["application_protocol"]
        == "HTTP/3"
    )
