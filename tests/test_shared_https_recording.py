"""Contract: HTTPS-only mode creates no ZIP; ZIP snapshot owns only its interval."""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from apk_research.desktop.shared_https_recording import SharedHttpsRecording
from apk_research.collectors.https_interception import HttpsInterceptionCollector
from apk_research.session import SessionManager


class RunningAnalyzer:
    NAME = HttpsInterceptionCollector.NAME
    TRANSACTIONS_ARTIFACT = HttpsInterceptionCollector.TRANSACTIONS_ARTIFACT
    BODIES_DIR = HttpsInterceptionCollector.BODIES_DIR
    METADATA_ARTIFACT = HttpsInterceptionCollector.METADATA_ARTIFACT
    STDERR_ARTIFACT = HttpsInterceptionCollector.STDERR_ARTIFACT
    ROUTE_LOG_ARTIFACT = HttpsInterceptionCollector.ROUTE_LOG_ARTIFACT
    ROUTE_ROOT = HttpsInterceptionCollector.ROUTE_ROOT

    def __init__(self, root: Path, package_name: str = "com.example.app"):
        self.package_name = package_name
        self.session = SimpleNamespace(paths=SimpleNamespace(root=root))
        self.running = True
        self._serial = "emulator-5554"
        self.stop_calls = 0
        self.adb = SimpleNamespace(
            shell_output=lambda *args, **kwargs: "ROUTE_ACTIVE\n"
        )

    def stop(self):
        self.stop_calls += 1
        self.running = False


def make_session(tmp_path):
    session = SessionManager.create(
        tmp_path / "record",
        target={"serial": "emulator-5554", "kind": "emulator"},
        package={"name": "com.example.app"},
    )
    session.begin_preflight()
    session.mark_ready()
    session.begin_start()
    return session


def _transaction(timestamp: float, name: str):
    return {
        "timestamp_start": timestamp,
        "method": "GET",
        "url": "https://example.org/" + name,
        "request": {"body": {"present": False}},
        "response": {"status_code": 200, "body": {
            "present": True,
            "path": name + ".response.body",
        }},
    }


def test_shared_https_snapshot_keeps_analyzer_running_and_bounds_zip(tmp_path):
    source = tmp_path / "analyzer"
    journal = source / HttpsInterceptionCollector.TRANSACTIONS_ARTIFACT
    journal.parent.mkdir(parents=True)
    (journal.parent / "http-bodies").mkdir()
    before = _transaction(time.time() - 300, "before")
    journal.write_text(json.dumps(before) + "\n", encoding="utf-8")
    source_collector = RunningAnalyzer(source)
    session = make_session(tmp_path)
    recorder = SharedHttpsRecording(source_collector, session, "com.example.app")
    assert recorder.preflight() is None
    recorder.start()
    session.mark_active()
    current = _transaction(time.time() + 1, "during")
    body = source / "02_normalized/http-bodies/during.response.body"
    body.write_text('{"done":true}', encoding="utf-8")
    with journal.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(current) + "\n")
    session.begin_stop()
    recorder.stop()
    session.finish()
    assert source_collector.running is True
    assert source_collector.stop_calls == 0
    target = session.paths.root / HttpsInterceptionCollector.TRANSACTIONS_ARTIFACT
    rows = [json.loads(line) for line in target.read_text().splitlines()]
    assert [row["url"] for row in rows] == ["https://example.org/during"]
    assert (session.paths.root / "02_normalized/http-bodies"
            / "during.response.body").read_bytes() == body.read_bytes()
    assert session.manifest["collectors"]["https_interception"]["status"] == "completed"
    assert not list(tmp_path.rglob("*.zip"))


def test_shared_https_requires_matching_live_target(tmp_path):
    analyzer = RunningAnalyzer(tmp_path, package_name="org.other.app")
    session = make_session(tmp_path)
    with pytest.raises(ValueError, match="packages differ"):
        SharedHttpsRecording(analyzer, session, "com.example.app")
    analyzer.package_name = "com.example.app"
    analyzer.running = False
    with pytest.raises(RuntimeError, match="must be active"):
        SharedHttpsRecording(analyzer, session, "com.example.app").preflight()
