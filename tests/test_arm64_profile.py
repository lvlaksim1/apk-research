from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

from apk_research.desktop.android_runtime import (
    AndroidRuntime,
    AndroidRuntimeError,
)
from apk_research.desktop.components import (
    ARM_COMPATIBLE_AVD_NAME,
    ARM_COMPATIBLE_SYSTEM_IMAGE_PACKAGE,
    ComponentInstallError,
    ComponentManager,
)
from apk_research.desktop.package_input import ApkBadging


def _runtime(tmp_path: Path) -> AndroidRuntime:
    manager = ComponentManager(tmp_path / "runtime")
    manager.paths.aapt2.parent.mkdir(parents=True, exist_ok=True)
    manager.paths.aapt2.write_bytes(b"stub")
    return AndroidRuntime(manager)


def _xapk(tmp_path: Path, split_abi: str) -> Path:
    archive_path = tmp_path / "app.xapk"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("base.apk", b"base")
        archive.writestr(f"config.{split_abi.replace('-', '_')}.apk", b"split")
    return archive_path


def _badging(apk: Path, native_abi: str) -> ApkBadging:
    is_base = apk.name == "base.apk"
    return ApkBadging(
        apk, "com.example.test", "42",
        None if is_base else apk.name.removesuffix(".apk"),
        () if is_base else (native_abi,),
    )


def test_google_apis_profile_keeps_legacy_userdata(tmp_path: Path) -> None:
    manager = ComponentManager(tmp_path)
    old_avd = manager.paths.avd_dir
    old_avd.mkdir(parents=True)
    (old_avd / "userdata-qemu.img").write_bytes(b"existing user data")

    manager.select_profile("google_apis")
    assert manager.avd_name == ARM_COMPATIBLE_AVD_NAME
    assert manager.system_image_package == ARM_COMPATIBLE_SYSTEM_IMAGE_PACKAGE
    assert manager.paths.avd_dir != old_avd
    assert manager.paths.system_image.parts[-2:] == ("google_apis", "x86_64")

    manager.paths.system_image.mkdir(parents=True)
    (manager.paths.system_image / "system.img").write_bytes(b"system")
    manager.create_avd_profile()
    config = (manager.paths.avd_dir / "config.ini").read_text(encoding="utf-8")
    assert "tag.id=google_apis" in config
    assert r"image.sysdir.1=system-images\android-35\google_apis\x86_64\" in config
    assert f"AvdId={ARM_COMPATIBLE_AVD_NAME}" in config
    assert (old_avd / "userdata-qemu.img").read_bytes() == b"existing user data"

    manager.persist_selected_profile()
    second = ComponentManager(tmp_path)
    assert second.profile == "google_apis"
    assert second.paths.avd_dir == manager.paths.avd_dir


def test_unknown_profile_cannot_be_selected(tmp_path: Path) -> None:
    manager = ComponentManager(tmp_path)
    with pytest.raises(ComponentInstallError, match="Неподдерживаемый профиль"):
        manager.select_profile("arm64-v8a")
    assert manager.profile == "default"


def test_x86_xapk_keeps_default_avd(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path)
    archive = _xapk(tmp_path, "x86_64")
    monkeypatch.setattr(
        runtime.components, "ensure_host_tools", lambda progress=None: None,
    )
    monkeypatch.setattr(
        runtime, "_apk_badging", lambda apk: _badging(apk, "x86_64"),
    )

    runtime.prepare_package_environment(archive)
    assert runtime.components.profile == "default"
    assert "@apk_research_api35" in runtime._emulator_command()


def test_arm64_xapk_selects_google_apis_before_boot(
    tmp_path: Path, monkeypatch,
) -> None:
    runtime = _runtime(tmp_path)
    archive = _xapk(tmp_path, "arm64-v8a")
    monkeypatch.setattr(
        runtime.components, "ensure_host_tools", lambda progress=None: None,
    )
    monkeypatch.setattr(
        runtime, "_apk_badging", lambda apk: _badging(apk, "arm64-v8a"),
    )
    monkeypatch.setattr(runtime, "_device_online", lambda: False)
    messages: list[str] = []

    runtime.prepare_package_environment(
        archive, lambda message, current, total: messages.append(message),
    )
    assert runtime.components.profile == "google_apis"
    assert "@apk_research_api35_google_apis" in runtime._emulator_command()
    assert any("ARM64" in message for message in messages)


def test_invalid_xapk_does_not_switch_profile(
    tmp_path: Path, monkeypatch,
) -> None:
    runtime = _runtime(tmp_path)
    archive = _xapk(tmp_path, "arm64-v8a")
    monkeypatch.setattr(
        runtime.components, "ensure_host_tools", lambda progress=None: None,
    )

    def badging(apk: Path) -> ApkBadging:
        entry = _badging(apk, "arm64-v8a")
        return ApkBadging(
            entry.path,
            "com.example.base" if apk.name == "base.apk" else "com.example.other",
            entry.version_code, entry.split_name, entry.native_codes,
        )

    monkeypatch.setattr(runtime, "_apk_badging", badging)
    with pytest.raises(AndroidRuntimeError, match="разных package name"):
        runtime.prepare_package_environment(archive)
    assert runtime.components.profile == "default"


def test_arm64_install_uses_actual_supported_abi_and_split(
    tmp_path: Path, monkeypatch,
) -> None:
    runtime = _runtime(tmp_path)
    archive = _xapk(tmp_path, "arm64-v8a")
    runtime.components.select_profile("google_apis")
    monkeypatch.setattr(runtime, "device_abis", lambda: ("x86_64", "arm64-v8a"))
    commands: list[list[str]] = []

    def fake_run(command, *, timeout, check=True):
        cmd = [str(x) for x in command]
        commands.append(cmd)
        if "aapt2" in Path(cmd[0]).name.lower():
            badging = _badging(Path(cmd[-1]), "arm64-v8a")
            extra = (
                f" split='{badging.split_name}'" if badging.split_name else ""
            )
            native = (
                "native-code: 'arm64-v8a'\n"
                if badging.split_name else ""
            )
            return subprocess.CompletedProcess(
                cmd, 0,
                stdout=(
                    f"package: name='{badging.package_name}' "
                    f"versionCode='{badging.version_code}'{extra}\n{native}"
                ),
                stderr="",
            )
        if "install-multiple" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="Success\n", stderr="",
            )
        raise AssertionError(cmd)

    monkeypatch.setattr(runtime, "_run", fake_run)
    assert runtime.install_package(archive) == "com.example.test"
    install = next(cmd for cmd in commands if "install-multiple" in cmd)
    assert any("config.arm64_v8a.apk" in x for x in install)


def test_google_apis_boot_rejects_missing_native_bridge(
    tmp_path: Path, monkeypatch,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.components.select_profile("google_apis")
    monkeypatch.setattr(
        runtime.components, "ensure_all", lambda progress=None: None,
    )
    monkeypatch.setattr(runtime, "_check_acceleration", lambda progress: None)
    monkeypatch.setattr(runtime, "_device_online", lambda: True)
    runtime._grpc_port = 8554
    monkeypatch.setattr(runtime, "_wait_for_boot", lambda progress: None)
    monkeypatch.setattr(runtime, "_ensure_root", lambda progress: None)
    monkeypatch.setattr(runtime, "_normalize_initial_orientation", lambda progress: None)
    monkeypatch.setattr(runtime, "_ensure_live_transport", lambda progress: None)
    monkeypatch.setattr(runtime, "device_abis", lambda: ("x86_64", "x86"))

    with pytest.raises(AndroidRuntimeError, match="не сообщил поддержку ARM64"):
        runtime.ensure_ready()
    assert not runtime.components._profile_file.exists()
