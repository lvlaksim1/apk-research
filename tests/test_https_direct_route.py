from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from apk_research.collectors.https_interception import (
    HttpsInterceptionCollector,
    HttpsInterceptionCollectorError,
)


class FakeAdb:
    def __init__(self, listed: str = "package:com.example.target uid:10156\n"):
        self.listed = listed
        self.shells: list[str] = []
        self.remote_dirs: list[str] = []
        self.uploads: list[tuple[str, str]] = []
        self.downloads: list[str] = []

    def shell_output(self, serial, *arguments, timeout=10):
        assert serial == "emulator-5554"
        self.shells.append(" ".join(str(a) for a in arguments))
        if arguments[0] == "cmd":
            return self.listed
        if any("ROUTE_REMOVED" in str(a) for a in arguments):
            return "ROUTE_REMOVED\n"
        if any("ROUTE_ACTIVE" in str(a) for a in arguments):
            return "ROUTE_ACTIVE\n"
        return ""

    def make_remote_directory(self, serial, path):
        self.remote_dirs.append(path)

    def push_file(self, serial, source, target, timeout=120.0):
        self.uploads.append((str(source), target))

    def pull_file(self, serial, source, target, timeout=120.0):
        self.downloads.append(source)
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(
            "ROUTE_READY port=38888 analyzer_port=38887\n"
            "CONNECTION_ROUTED destination=93.184.215.14:443\n",
            encoding="utf-8",
        )


def _collector(tmp_path, adb):
    session = SimpleNamespace(paths=SimpleNamespace(root=tmp_path))
    collector = HttpsInterceptionCollector(
        adb, session, package_name="com.example.target",
    )
    collector._serial = "emulator-5554"
    return collector


def test_selected_app_uid_is_taken_from_android_package_manager(tmp_path):
    collector = _collector(tmp_path, FakeAdb())
    assert collector._target_uid() == 10156


def test_invalid_or_other_package_uid_is_not_guessed(tmp_path):
    collector = _collector(
        tmp_path,
        FakeAdb("package:com.example.other uid:10156\n"),
    )
    with pytest.raises(HttpsInterceptionCollectorError, match="UID"):
        collector._target_uid()


def test_direct_route_limits_output_rule_to_target_uid_and_tcp443(
    tmp_path, monkeypatch,
):
    adb = FakeAdb()
    collector = _collector(tmp_path, adb)
    binary = tmp_path / "apk-research-https-route"
    binary.write_bytes(b"test-binary")
    monkeypatch.setattr(collector, "_route_executable", lambda: binary)

    collector._configure_direct_route()
    commands = "\n".join(adb.shells)
    assert collector._route_active is True
    assert collector._route_ever_active is True
    assert collector._route_uid == 10156
    assert "iptables -t nat -I OUTPUT 1 -m owner --uid-owner 10156" in commands
    assert "iptables -t nat -A \"$CHAIN\" -p tcp --dport 443" in commands
    assert "-j REDIRECT --to-ports 38888" in commands
    assert "CONNECTION_ROUTED" not in commands
    assert adb.uploads[0][1].endswith("/apk-research-https-route")

    collector._stop_direct_route()
    assert collector._route_active is False
    assert collector._route_attempted is False
    assert collector._route_cleanup_confirmed is True
    assert adb.downloads == [
        "/data/local/tmp/apk-research/https-route32/route.log"
    ]
    saved = (
        tmp_path / "01_raw/network/https-direct-route.log"
    ).read_text(encoding="utf-8")
    assert "CONNECTION_ROUTED" in saved
    restored = "\n".join(adb.shells)
    assert "iptables -t nat -D OUTPUT \"$@\"" in restored
    assert '-j $CHAIN' in restored


def test_metadata_records_scope_and_route_usage(tmp_path):
    adb = FakeAdb()
    collector = _collector(tmp_path, adb)
    collector._started_utc = "2026-10-10T01:00:00Z"
    collector._route_uid = 10156
    collector._route_ever_active = True
    collector._route_active = False
    collector._write_metadata("completed", error=None, transaction_count=2)
    data = json.loads(
        (tmp_path / collector.METADATA_ARTIFACT).read_text(encoding="utf-8")
    )
    assert data["target_uid"] == 10156
    assert data["direct_tcp443_route_used"] is True
    assert data["direct_tcp443_route_configured"] is False
    assert data["transport_intervention"]["other_android_apps_unmodified"]
    assert data["transport_intervention"]["quic_udp443_not_handled"]
