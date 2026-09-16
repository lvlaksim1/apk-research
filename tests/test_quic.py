from __future__ import annotations

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from apk_research import quic
from apk_research.desktop.network_view_model import (
    flow_host,
    format_flow_details,
)
from apk_research.network_attribution import (
    SocketAttributionIndex,
    build_flow_inventory,
)


def _encode_varint(value: int) -> bytes:
    if value < 1 << 6:
        return bytes([value])
    if value < 1 << 14:
        return (value | 0x4000).to_bytes(2, "big")
    if value < 1 << 30:
        return (value | 0x80000000).to_bytes(4, "big")
    raise ValueError("test value is too large")


def _client_hello(
    host: str,
    alpns: list[str],
) -> bytes:
    host_bytes = host.encode("ascii")
    server_name = (
        b"\x00"
        + len(host_bytes).to_bytes(2, "big")
        + host_bytes
    )
    server_name = (
        len(server_name).to_bytes(2, "big")
        + server_name
    )
    alpn_entries = b"".join(
        bytes([len(item.encode("ascii"))])
        + item.encode("ascii")
        for item in alpns
    )
    alpn = (
        len(alpn_entries).to_bytes(2, "big")
        + alpn_entries
    )
    extensions = (
        b"\x00\x00"
        + len(server_name).to_bytes(2, "big")
        + server_name
        + b"\x00\x10"
        + len(alpn).to_bytes(2, "big")
        + alpn
    )
    body = (
        b"\x03\x03"
        + bytes(range(32))
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


def _nonce(
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


def _protected_initial(
    version: int,
    host: str = "example.com",
) -> bytes:
    dcid = bytes.fromhex("8394c8f03e515708")
    packet_number = 2
    packet_number_length = 4
    hello = _client_hello(
        host,
        ["h3", "h3-29"],
    )
    crypto = (
        b"\x06"
        + _encode_varint(0)
        + _encode_varint(len(hello))
        + hello
    )
    plaintext = crypto + b"\x00" * 1200
    type_bits = (
        0
        if version == quic.QUIC_VERSION_1
        else 1
    )
    first = (
        0xC0
        | (type_bits << 4)
        | (packet_number_length - 1)
    )
    header_prefix = (
        bytes([first])
        + version.to_bytes(4, "big")
        + bytes([len(dcid)])
        + dcid
        + b"\x00"
        + _encode_varint(0)
    )
    protected_length = (
        packet_number_length
        + len(plaintext)
        + 16
    )
    header_prefix += _encode_varint(
        protected_length
    )
    packet_number_bytes = packet_number.to_bytes(
        packet_number_length,
        "big",
    )
    associated_data = (
        header_prefix
        + packet_number_bytes
    )
    keys = quic.derive_initial_keys(
        version,
        dcid,
        "client",
    )
    ciphertext = AESGCM(keys["key"]).encrypt(
        _nonce(
            keys["iv"],
            packet_number,
        ),
        plaintext,
        associated_data,
    )
    packet = bytearray(
        associated_data + ciphertext
    )
    packet_number_offset = len(header_prefix)
    sample = bytes(
        packet[
            packet_number_offset + 4 :
            packet_number_offset + 20
        ]
    )
    encryptor = Cipher(
        algorithms.AES(keys["hp"]),
        modes.ECB(),
    ).encryptor()
    mask = (
        encryptor.update(sample)
        + encryptor.finalize()
    )[:5]
    packet[0] ^= mask[0] & 0x0F
    for index in range(packet_number_length):
        packet[
            packet_number_offset + index
        ] ^= mask[index + 1]
    return bytes(packet)


def test_rfc9001_v1_initial_keys() -> None:
    keys = quic.derive_initial_keys(
        quic.QUIC_VERSION_1,
        bytes.fromhex("8394c8f03e515708"),
        "client",
    )
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


def test_rfc9369_v2_initial_keys() -> None:
    keys = quic.derive_initial_keys(
        quic.QUIC_VERSION_2,
        bytes.fromhex("8394c8f03e515708"),
        "client",
    )
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


def test_quic_v1_client_initial_exposes_sni_and_http3_alpn() -> None:
    inspector = quic.QuicFlowInspector()
    result = inspector.inspect(
        _protected_initial(
            quic.QUIC_VERSION_1
        ),
        direction="outbound",
    )
    assert result is not None
    assert result["version"] == "v1"
    assert result["packet_type"] == "initial"
    assert result["initial_decrypted"] is True
    assert result["initial_sender"] == "client"
    assert result["packet_number"] == 2
    assert result["sni"] == "example.com"
    assert result["alpn"] == ["h3", "h3-29"]


def test_quic_v2_client_initial_exposes_sni_and_http3_alpn() -> None:
    inspector = quic.QuicFlowInspector()
    result = inspector.inspect(
        _protected_initial(
            quic.QUIC_VERSION_2,
            "v2.example",
        ),
        direction="outbound",
    )
    assert result is not None
    assert result["version"] == "v2"
    assert result["packet_type"] == "initial"
    assert result["initial_decrypted"] is True
    assert result["sni"] == "v2.example"
    assert "h3" in result["alpn"]


def test_flow_inventory_and_view_keep_quic_evidence_explicit() -> None:
    index = SocketAttributionIndex(
        {},
        [],
    )
    packet = {
        "epoch": 1_700_000_000.0,
        "captured_length": 1250,
        "direction": "outbound",
        "protocol": "udp",
        "src": "10.0.2.16",
        "src_port": 50000,
        "dst": "203.0.113.10",
        "dst_port": 443,
        "application_protocol": "http3",
        "quic_version": "v1",
        "quic_packet_type": "initial",
        "quic_initial_decrypted": True,
        "quic_sni": "example.com",
        "quic_alpn": ["h3"],
        "tls_sni": "example.com",
        "dns_query": None,
    }
    inventory = build_flow_inventory(
        [packet],
        index,
    )
    assert inventory["schema_version"] == "0.3"
    assert inventory["summary"]["quic_flow_count"] == 1
    assert inventory["summary"]["http3_flow_count"] == 1
    assert (
        inventory["summary"][
            "quic_initial_decrypted_flow_count"
        ]
        == 1
    )
    flow = inventory["flows"][0]
    assert flow["application_protocols"] == [
        "http3"
    ]
    assert flow["quic_versions"] == ["v1"]
    assert flow["quic_sni"] == ["example.com"]
    assert flow["quic_alpn"] == ["h3"]
    assert flow_host(flow) == "example.com"
    details = format_flow_details(
        flow,
        {},
    )
    assert "QUIC / HTTP/3" in details
    assert "Initial decrypted: yes" in details
    assert "ALPN: h3" in details
