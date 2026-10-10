from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from apk_research.desktop.android_runtime import (
    AndroidRuntime, AndroidRuntimeError,
)


def _runtime(monkeypatch):
    runtime = object.__new__(AndroidRuntime)
    monkeypatch.setattr(runtime, "_device_online", lambda: True)
    runtime.paths = SimpleNamespace(adb=Path("adb"))
    runtime.components = SimpleNamespace(environment=lambda: {})
    runtime.SERIAL = "emulator-5554"
    return runtime


def test_system_keys_and_rotation(monkeypatch):
    runtime = _runtime(monkeypatch)
    calls = []
    monkeypatch.setattr(
        runtime, "_adb_shell",
        lambda *args, **kwargs: (
            calls.append(args)
            or subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        ),
    )
    runtime.emulator_action("recent")
    runtime.emulator_action("volume_up")
    runtime.emulator_action("volume_down")
    runtime.emulator_action("rotate")
    runtime.emulator_action("rotate")
    assert ("input", "keyevent", "187") in calls
    assert ("input", "keyevent", "24") in calls
    assert ("input", "keyevent", "25") in calls
    assert ("settings", "put", "system", "user_rotation", "1") in calls
    assert ("settings", "put", "system", "user_rotation", "0") in calls


def test_selected_app_controls_require_valid_package(monkeypatch):
    runtime = _runtime(monkeypatch)
    calls = []
    monkeypatch.setattr(
        runtime, "_adb_shell",
        lambda *args, **kwargs: (
            calls.append(args)
            or subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        ),
    )
    runtime.emulator_action("stop_app", "com.example.app")
    runtime.emulator_action("settings_app", "com.example.app")
    runtime.emulator_action("clear_app", "com.example.app")
    assert ("am", "force-stop", "com.example.app") in calls
    assert ("pm", "clear", "com.example.app") in calls
    assert any("android.settings.APPLICATION_DETAILS_SETTINGS" in line for line in calls)
    with pytest.raises(Exception):
        runtime.emulator_action("clear_app", "com.example; rm -rf /")


def test_geolocation_uses_emulator_lon_lat_order(monkeypatch):
    runtime = _runtime(monkeypatch)
    commands = []
    monkeypatch.setattr(
        runtime, "_run",
        lambda command, **kwargs: (
            commands.append(command)
            or subprocess.CompletedProcess(command, 0, stdout="OK", stderr="")
        ),
    )
    runtime.emulator_action("location", "59.95", "30.31")
    assert commands[0][-4:] == ["geo", "fix", "30.31", "59.95"]
    with pytest.raises(AndroidRuntimeError):
        runtime.emulator_action("location", "99", "30")


def test_file_receive_only_from_public_android_storage(monkeypatch, tmp_path):
    runtime = _runtime(monkeypatch)
    calls = []
    monkeypatch.setattr(
        runtime, "_run",
        lambda command, **kwargs: (
            calls.append(command)
            or subprocess.CompletedProcess(command, 0, stdout="OK", stderr="")
        ),
    )
    with pytest.raises(AndroidRuntimeError):
        runtime.emulator_action(
            "pull_file", "/data/data/com.example.app/private.db",
            str(tmp_path / "private.db"),
        )
    with pytest.raises(AndroidRuntimeError):
        runtime.emulator_action(
            "pull_file", "/sdcard/../data/secret",
            str(tmp_path / "secret"),
        )
    runtime.emulator_action(
        "pull_file", "/sdcard/Download/report.txt",
        str(tmp_path / "report.txt"),
    )
    assert calls[0][-3] == "pull"
