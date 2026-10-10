from __future__ import annotations

import json
from pathlib import Path

from apk_research.https_proxy_worker import (
    ResearchTransactionRecorder,
)


class _Headers:
    def __init__(self, values):
        self._values = list(values)

    def items(self, multi=False):
        assert multi is True
        return iter(self._values)

    def get(self, name, default=None):
        lowered = str(name).lower()
        for key, value in self._values:
            if str(key).lower() == lowered:
                return value
        return default


class _Message:
    def __init__(
        self,
        content: bytes,
        *,
        headers=(),
        http_version="HTTP/2.0",
        timestamp_start=100.0,
        timestamp_end=100.2,
    ):
        self._content = content
        self.raw_content = content
        self.headers = _Headers(headers)
        self.http_version = http_version
        self.timestamp_start = timestamp_start
        self.timestamp_end = timestamp_end

    def get_content(self, strict=True):
        return self._content


class _Request(_Message):
    scheme = "https"
    method = "POST"
    pretty_url = "https://api.example.test/v1/login?x=1"
    host = "api.example.test"
    port = 443


class _Response(_Message):
    status_code = 200
    reason = "OK"


class _Flow:
    id = "flow-test-1"
    error = None

    def __init__(self):
        self.request = _Request(
            b'{"login":"demo"}',
            headers=(
                ("content-type", "application/json"),
                ("x-test", "request"),
            ),
        )
        self.response = _Response(
            b'{"ok":true}',
            headers=(
                ("content-type", "application/json"),
                ("x-test", "response"),
            ),
        )


def test_recorder_writes_http_transaction_and_bodies(
    tmp_path: Path,
) -> None:
    transactions = tmp_path / "transactions.jsonl"
    bodies = tmp_path / "bodies"
    ready = tmp_path / "ready.json"
    error = tmp_path / "error.txt"
    recorder = ResearchTransactionRecorder(
        transactions,
        bodies,
        ready,
        error,
    )

    recorder.response(_Flow())

    value = json.loads(
        transactions.read_text(encoding="utf-8")
    )
    assert value["transaction_id"] == "http-00000001"
    assert value["method"] == "POST"
    assert value["url"] == (
        "https://api.example.test/v1/login?x=1"
    )
    assert value["response"]["status_code"] == 200
    assert value["interception"]["tls_decrypted"] is True

    request_name = value["request"]["body"]["path"]
    response_name = value["response"]["body"]["path"]
    assert (bodies / request_name).read_bytes() == b'{"login":"demo"}'
    assert (bodies / response_name).read_bytes() == b'{"ok":true}'


def test_recorder_writes_error_transaction(
    tmp_path: Path,
) -> None:
    transactions = tmp_path / "transactions.jsonl"
    recorder = ResearchTransactionRecorder(
        transactions,
        tmp_path / "bodies",
        tmp_path / "ready.json",
        tmp_path / "error.txt",
    )
    flow = _Flow()
    flow.response = None
    flow.error = RuntimeError("TLS client disconnected")

    recorder.error(flow)

    value = json.loads(
        transactions.read_text(encoding="utf-8")
    )
    assert value["state"] == "error"
    assert value["response"] is None
    assert "TLS client disconnected" in value["error"]
    assert value["interception"]["tls_decrypted"] is False

def test_direct_route_marker_is_preserved_per_https_transaction(tmp_path):
    from types import SimpleNamespace

    transactions = tmp_path / "http.jsonl"
    recorder = ResearchTransactionRecorder(
        transactions, tmp_path / "bodies",
        tmp_path / "ready.json", tmp_path / "error.txt",
    )
    connection = SimpleNamespace(id="device-tunnel-001")
    tunnel = _Flow()
    tunnel.client_conn = connection
    tunnel.request.headers = _Headers(
        [("X-Apk-Research-Route", "direct")]
    )
    recorder.http_connect(tunnel)

    flow = _Flow()
    flow.client_conn = connection
    recorder.response(flow)
    data = json.loads(transactions.read_text(encoding="utf-8"))
    assert data["interception"]["route"] == "direct"

    other = _Flow()
    other.client_conn = SimpleNamespace(id="system-tunnel")
    recorder.response(other)
    records = [json.loads(line) for line in transactions.read_text().splitlines()]
    assert records[1]["interception"]["route"] == "system-or-undetermined"
