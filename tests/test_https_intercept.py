from __future__ import annotations

import base64
import json
import threading
from pathlib import Path

from cryptography import x509

from apk_research.collectors.https_intercept import (
    HTTPS_INTERCEPTION_ARTIFACT,
    HTTPS_TRANSACTIONS_ARTIFACT,
    _TransactionAddon,
    android_subject_hash_old,
)
from apk_research.https_capture import StagedHttpsCapture
from apk_research.session import SessionManager


_TEST_CA_PEM = b"""-----BEGIN CERTIFICATE-----
MIIBbTCCARSgAwIBAgIBATAKBggqhkjOPQQDAjA2MR0wGwYDVQQDDBRhcGstcmVz
ZWFyY2ggVGVzdCBDQTEVMBMGA1UECgwMYXBrLXJlc2VhcmNoMB4XDTI2MDEwMTAw
MDAwMFoXDTM2MDEwMTAwMDAwMFowNjEdMBsGA1UEAwwUYXBrLXJlc2VhcmNoIFRl
c3QgQ0ExFTATBgNVBAoMDGFway1yZXNlYXJjaDBZMBMGByqGSM49AgEGCCqGSM49
AwEHA0IABGsX0fLhLEJH+Lzm5WOkQPJ3A32BLeszoPShOUXYmMKWT+NC4v4af5uO
5+tKfA+eFivOM1drMV7Oy7ZAaDe/UfWjEzARMA8GA1UdEwEB/wQFMAMBAf8wCgYI
KoZIzj0EAwIDRwAwRAIgLEPt3c4J5GuOyoBkq+rTwpOt0wGNNi0JgBGg5FSEcCwC
ICBieLekBaoxVwoZ8UplMXeJHtnFzYuGfUmA2R9T7dEz
-----END CERTIFICATE-----
"""


class _Headers:
    def __init__(self, items: list[tuple[str, str]]) -> None:
        self._items = list(items)

    def items(self, multi: bool = False):
        assert multi is True
        return list(self._items)


class _Request:
    timestamp_start = 1000.25
    timestamp_end = 1000.5
    pretty_url = "https://api.example.test/v1/items?q=1"
    url = pretty_url
    scheme = "https"
    pretty_host = "api.example.test"
    host = pretty_host
    port = 443
    method = "POST"
    path = "/v1/items?q=1"
    http_version = "HTTP/2"
    headers = _Headers(
        [
            ("content-type", "application/json"),
            ("x-test", "one"),
            ("x-test", "two"),
        ]
    )
    raw_content = b'{"hello":"world"}'


class _Response:
    timestamp_start = 1000.75
    timestamp_end = 1001.0
    status_code = 201
    reason = "Created"
    http_version = "HTTP/2"
    headers = _Headers(
        [
            ("content-type", "application/octet-stream"),
            ("x-response", "ok"),
        ]
    )
    raw_content = b"\x00\x01\xff"


class _Conn:
    tls_version = "TLSv1.3"
    cipher = "TLS_AES_128_GCM_SHA256"
    sni = "api.example.test"


class _Flow:
    id = "flow-1"
    request = _Request()
    response = _Response()
    client_conn = _Conn()
    server_conn = _Conn()
    error = None


def test_android_subject_hash_old_matches_openssl_reference() -> None:
    certificate = x509.load_pem_x509_certificate(
        _TEST_CA_PEM
    )
    assert android_subject_hash_old(
        certificate
    ) == "a8d2161d"


def test_transaction_addon_preserves_exact_request_and_response_bytes(
    tmp_path: Path,
) -> None:
    output = tmp_path / "http-transactions.jsonl"
    addon = _TransactionAddon(
        output,
        threading.Event(),
    )

    addon.response(_Flow())
    addon.response(_Flow())

    lines = output.read_text(
        encoding="utf-8"
    ).splitlines()
    assert len(lines) == 1

    value = json.loads(lines[0])
    assert value["transaction_id"] == "http-000001"
    assert value["capture_mode"] == "active-explicit-proxy"
    assert value["intervention"] is True
    assert value["method"] == "POST"
    assert value["url"] == (
        "https://api.example.test/v1/items?q=1"
    )
    assert value["http_version"] == "HTTP/2"
    assert value["request_headers"] == [
        ["content-type", "application/json"],
        ["x-test", "one"],
        ["x-test", "two"],
    ]
    assert base64.b64decode(
        value["request_body"]["base64"]
    ) == _Request.raw_content

    response = value["response"]
    assert response["status_code"] == 201
    assert response["reason"] == "Created"
    assert base64.b64decode(
        response["body"]["base64"]
    ) == _Response.raw_content
    assert addon.transactions == 1
    assert addon.request_bytes == len(
        _Request.raw_content
    )
    assert addon.response_bytes == len(
        _Response.raw_content
    )


def test_staged_https_capture_attaches_artifacts_to_real_session(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging"
    (staging / "02_normalized").mkdir(
        parents=True
    )
    state_bytes = b'{"schema_version":"0.1","status":"stopped"}\n'
    transactions_bytes = (
        b'{"schema_version":"0.1","transaction_id":"http-000001"}\n'
    )
    (
        staging
        / HTTPS_INTERCEPTION_ARTIFACT
    ).write_bytes(state_bytes)
    (
        staging
        / HTTPS_TRANSACTIONS_ARTIFACT
    ).write_bytes(transactions_bytes)

    capture = StagedHttpsCapture.__new__(
        StagedHttpsCapture
    )
    capture.root = staging

    session = SessionManager.create(
        tmp_path / "sessions",
        target={"serial": "emulator-5554"},
        package={"name": "com.example.app"},
        session_id_factory=lambda: "test-session",
    )

    capture.attach_to_session(session)

    assert (
        session.paths.root
        / HTTPS_INTERCEPTION_ARTIFACT
    ).read_bytes() == state_bytes
    assert (
        session.paths.root
        / HTTPS_TRANSACTIONS_ARTIFACT
    ).read_bytes() == transactions_bytes

    artifacts = {
        item["path"]: item
        for item in session.manifest["artifacts"]
    }
    assert artifacts[
        HTTPS_INTERCEPTION_ARTIFACT
    ]["raw"] is False
    assert artifacts[
        HTTPS_TRANSACTIONS_ARTIFACT
    ]["raw"] is False
    assert artifacts[
        HTTPS_INTERCEPTION_ARTIFACT
    ]["source"] == "https-intercept"
