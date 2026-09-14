from __future__ import annotations

import base64
import subprocess

import pytest

from mobile_research.desktop.android_runtime import (
    AndroidRuntime,
    AndroidRuntimeError,
    acceleration_provider,
)
from mobile_research.desktop.components import ComponentManager


def _make_components_ready(manager: ComponentManager) -> None:
    manager.paths.adb.parent.mkdir(parents=True, exist_ok=True)
    manager.paths.adb.write_bytes(b"adb")
    manager.paths.emulator.parent.mkdir(parents=True, exist_ok=True)
    manager.paths.emulator.write_bytes(b"emulator")
    manager.paths.aapt2.parent.mkdir(parents=True, exist_ok=True)
    manager.paths.aapt2.write_bytes(b"aapt2")

    manager.paths.system_image.mkdir(parents=True, exist_ok=True)
    (manager.paths.system_image / "system.img").write_bytes(b"system")

    manager.paths.avd_home.mkdir(parents=True, exist_ok=True)
    manager.paths.avd_ini.write_text(
        "target=android-35\n",
        encoding="utf-8",
    )
    manager.paths.avd_dir.mkdir(parents=True, exist_ok=True)
    (manager.paths.avd_dir / "config.ini").write_text(
        "target=android-35\n",
        encoding="utf-8",
    )


def test_diagnostics_reports_component_versions_and_acceleration(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)

    monkeypatch.setattr(
        runtime,
        "_device_online",
        lambda: False,
    )

    def fake_run(
        command,
        *,
        timeout,
        check=True,
    ):
        executable = str(command[0]).lower()
        arguments = list(command[1:])

        if executable.endswith("adb.exe"):
            stdout = (
                "Android Debug Bridge version 1.0.41\n"
                "Version 37.0.1-15733141\n"
            )
        elif executable.endswith("aapt2.exe"):
            stdout = "Android Asset Packaging Tool (aapt) 2.19-11948202\n"
        elif arguments == ["-version"]:
            stdout = (
                "Android emulator version 37.1.11.0 "
                "(build_id 15917651) (CL:N/A)\n"
            )
        elif arguments == ["-accel-check"]:
            stdout = "WHPX is installed and usable.\n"
        else:
            raise AssertionError(command)

        return subprocess.CompletedProcess(
            command,
            0,
            stdout=stdout,
            stderr="",
        )

    monkeypatch.setattr(runtime, "_run", fake_run)

    data = runtime.diagnostics()

    versions = data["versions"]
    assert versions["adb"]["available"] is True
    assert versions["adb"]["version"] == (
        "Android Debug Bridge version 1.0.41"
    )
    assert versions["emulator"]["version"].startswith(
        "Android emulator version 37.1.11.0"
    )
    assert versions["aapt2"]["available"] is True

    acceleration = data["acceleration"]
    assert acceleration["available"] is True
    assert acceleration["provider"] == "whpx"
    assert "WHPX" in acceleration["detail"]


def test_acceleration_provider_distinguishes_hypervisors() -> None:
    assert (
        acceleration_provider(
            "WHPX(10.0.26100) is installed and usable."
        )
        == "whpx"
    )
    assert (
        acceleration_provider(
            "AEHD is installed and usable."
        )
        == "aehd"
    )
    assert (
        acceleration_provider(
            "GVM is installed and usable."
        )
        == "aehd"
    )
    assert (
        acceleration_provider(
            "KVM (version 12) is installed and usable."
        )
        == "kvm"
    )
    assert (
        acceleration_provider(
            "Hypervisor.Framework OS X Version 15"
        )
        == "hypervisor-framework"
    )
    assert acceleration_provider("acceleration available") == "unknown"



def test_windows_aehd_is_accepted_without_uac(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)

    monkeypatch.setattr(
        runtime,
        "_is_windows",
        lambda: True,
    )
    monkeypatch.setattr(
        runtime,
        "_acceleration_check",
        lambda: subprocess.CompletedProcess(
            ["emulator", "-accel-check"],
            0,
            stdout="AEHD (version 2.2) is installed and usable.\n",
            stderr="",
        ),
    )

    called = False

    def fail_enable():
        nonlocal called
        called = True
        raise AssertionError("UAC must not be requested for usable AEHD")

    monkeypatch.setattr(
        runtime,
        "_enable_windows_hypervisor_features",
        fail_enable,
    )

    runtime._check_acceleration()

    assert called is False
    assert runtime._software_acceleration is False


def test_windows_whpx_is_preferred_without_uac(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)

    monkeypatch.setattr(
        runtime,
        "_is_windows",
        lambda: True,
    )
    monkeypatch.setattr(
        runtime,
        "_acceleration_check",
        lambda: subprocess.CompletedProcess(
            ["emulator", "-accel-check"],
            0,
            stdout="WHPX is installed and usable.\n",
            stderr="",
        ),
    )
    monkeypatch.setattr(
        runtime,
        "_enable_windows_hypervisor_features",
        lambda: (_ for _ in ()).throw(
            AssertionError("UAC must not be requested for WHPX")
        ),
    )

    runtime._check_acceleration()

    assert runtime._software_acceleration is False


def test_windows_setup_requires_reboot_when_no_hypervisor(
    tmp_path,
    monkeypatch,
) -> None:
    from mobile_research.desktop.android_runtime import AndroidRuntimeError

    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)

    monkeypatch.setattr(
        runtime,
        "_is_windows",
        lambda: True,
    )
    monkeypatch.setattr(
        runtime,
        "_acceleration_check",
        lambda: subprocess.CompletedProcess(
            ["emulator", "-accel-check"],
            1,
            stdout="accel: 1\nNo usable hypervisor found.\n",
            stderr="",
        ),
    )
    monkeypatch.setattr(
        runtime,
        "_enable_windows_hypervisor_features",
        lambda: 10,
    )

    with pytest.raises(
        AndroidRuntimeError,
        match="нужно перезагрузить компьютер",
    ):
        runtime._check_acceleration()


def test_whpx_enablement_uses_one_uac_and_only_required_feature(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    runtime = AndroidRuntime(manager)
    captured: list[str] = []

    def fake_subprocess_run(command, **kwargs):
        captured.extend(str(item) for item in command)
        return subprocess.CompletedProcess(command, 10)

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_subprocess_run,
    )

    code = runtime._enable_windows_hypervisor_features()

    assert code == 10
    joined = " ".join(captured)
    assert joined.count("Start-Process") == 1
    assert "VirtualMachinePlatform" not in joined

    encoded_index = captured.index("-Command") + 1
    outer = captured[encoded_index]
    marker = "'-EncodedCommand','"
    start = outer.index(marker) + len(marker)
    end = outer.index("'", start)
    script = base64.b64decode(
        outer[start:end]
    ).decode("utf-16-le")
    assert "HypervisorPlatform" in script
    assert "VirtualMachinePlatform" not in script
    assert "hypervisorlaunchtype Auto" in script



def test_emulator_command_uses_auto_gpu_and_grpc(
    tmp_path,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)
    runtime._grpc_port = 8554

    command = runtime._emulator_command()

    gpu_index = command.index("-gpu")
    grpc_index = command.index("-grpc")
    assert command[gpu_index + 1] == "auto"
    assert command[grpc_index + 1] == "8554"
    assert "swiftshader" not in command



def test_windows_prefers_host_gpu(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    runtime = AndroidRuntime(manager)
    runtime._software_acceleration = False
    monkeypatch.setattr(
        runtime,
        "_is_windows",
        lambda: True,
    )
    assert runtime._preferred_gpu_mode() == "host"


def test_software_mode_keeps_swiftshader(
    tmp_path,
) -> None:
    manager = ComponentManager(tmp_path)
    runtime = AndroidRuntime(manager)
    runtime._software_acceleration = True
    assert (
        runtime._preferred_gpu_mode()
        == "swiftshader"
    )



def test_windows_grpc_embedded_uses_qt_hidden_window(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)
    runtime._grpc_port = 8554
    runtime._software_acceleration = False
    monkeypatch.setattr(
        runtime,
        "_is_windows",
        lambda: True,
    )

    runtime._display_mode = "grpc-embedded"
    command = runtime._emulator_command()

    assert "-qt-hide-window" in command
    assert "-no-window" not in command
    assert "-crash-report-mode" in command
    crash_index = command.index("-crash-report-mode")
    assert command[crash_index + 1] == "disabled"
    assert runtime._display_mode == "grpc-embedded"


def test_windows_dwm_live_has_real_window(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)
    runtime._grpc_port = 8554
    runtime._software_acceleration = False
    runtime._display_mode = "dwm-live"
    runtime._gpu_mode = "host"
    monkeypatch.setattr(
        runtime,
        "_is_windows",
        lambda: True,
    )

    command = runtime._emulator_command()

    assert "-qt-hide-window" not in command
    assert "-no-window" not in command
    assert runtime.native_display_supported is True
    gpu_index = command.index("-gpu")
    assert command[gpu_index + 1] == "host"


def test_non_windows_emulator_remains_headless(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)
    runtime._grpc_port = 8554
    monkeypatch.setattr(
        runtime,
        "_is_windows",
        lambda: False,
    )

    command = runtime._emulator_command()

    assert "-no-window" in command
    assert "-qt-hide-window" not in command



def test_windows_runtime_uses_framebuffer_not_native_hwnd(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)
    monkeypatch.setattr(
        runtime,
        "_is_windows",
        lambda: True,
    )
    runtime._display_mode = "grpc-embedded"

    assert runtime.native_display_supported is False
    assert runtime.emulator_pid == 0


def test_windows_headless_mode_disables_native_embedding(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)
    runtime._grpc_port = 8554
    runtime._gpu_mode = "swiftshader"
    runtime._display_mode = "headless"
    monkeypatch.setattr(
        runtime,
        "_is_windows",
        lambda: True,
    )

    command = runtime._emulator_command()

    assert runtime.native_display_supported is False
    assert "-no-window" in command
    assert "-qt-hide-window" not in command
    gpu_index = command.index("-gpu")
    assert command[gpu_index + 1] == "swiftshader"


def test_windows_boot_falls_back_across_embedded_gpu_modes(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    runtime = AndroidRuntime(manager)
    runtime._software_acceleration = False
    attempts: list[tuple[str, str]] = []

    monkeypatch.setattr(
        runtime,
        "_is_windows",
        lambda: True,
    )

    def fake_start(progress):
        attempts.append(
            (
                runtime._gpu_mode,
                runtime._display_mode,
            )
        )
        runtime._last_emulator_command = [
            "emulator",
            "-gpu",
            runtime._gpu_mode,
        ]

    def fake_wait(progress):
        if len(attempts) < 5:
            raise AndroidRuntimeError(
                "synthetic graphics startup failure"
            )

    monkeypatch.setattr(
        runtime,
        "_start_emulator",
        fake_start,
    )
    monkeypatch.setattr(
        runtime,
        "_wait_for_boot",
        fake_wait,
    )
    monkeypatch.setattr(
        runtime,
        "stop",
        lambda: None,
    )

    runtime._boot_managed_emulator(None)

    assert attempts == [
        ("host", "dwm-live"),
        ("auto", "dwm-live"),
        ("host", "grpc-embedded"),
        ("auto", "grpc-embedded"),
        ("swiftshader", "headless"),
    ]
    assert [
        item["status"]
        for item in runtime._startup_attempts
    ] == [
        "failed",
        "failed",
        "failed",
        "failed",
        "completed",
    ]
    assert runtime.native_display_supported is False



def test_reset_userdata_uses_persistent_wipe_marker(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)

    monkeypatch.setattr(
        runtime,
        "stop",
        lambda: None,
    )

    runtime.reset_userdata()

    assert runtime._wipe_marker.is_file()

    runtime._grpc_port = 8554
    command = runtime._emulator_command()
    assert "-wipe-data" in command


def test_successful_boot_clears_wipe_marker(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)
    runtime._wipe_marker.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    runtime._wipe_marker.write_text(
        "pending",
        encoding="utf-8",
    )
    runtime._software_acceleration = False

    monkeypatch.setattr(
        runtime,
        "_is_windows",
        lambda: False,
    )
    monkeypatch.setattr(
        runtime,
        "_start_emulator",
        lambda progress: None,
    )
    monkeypatch.setattr(
        runtime,
        "_wait_for_boot",
        lambda progress: None,
    )

    runtime._boot_managed_emulator(None)

    assert not runtime._wipe_marker.exists()


def test_ensure_ready_terminates_unowned_online_emulator(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)

    online = [True, False]
    recovered = []
    booted = []

    monkeypatch.setattr(
        runtime.components,
        "ensure_all",
        lambda progress=None: manager.state(),
    )
    monkeypatch.setattr(
        runtime,
        "_check_acceleration",
        lambda progress=None: None,
    )
    monkeypatch.setattr(
        runtime,
        "_device_online",
        lambda: online.pop(0) if online else False,
    )
    monkeypatch.setattr(
        runtime,
        "_terminate_orphaned_managed_emulator",
        lambda: recovered.append(True),
    )
    monkeypatch.setattr(
        runtime,
        "_recover_stale_managed_emulator",
        lambda: None,
    )
    monkeypatch.setattr(
        runtime,
        "_boot_managed_emulator",
        lambda progress, display_ready=None: booted.append(True),
    )
    monkeypatch.setattr(
        runtime,
        "_ensure_root",
        lambda progress=None: None,
    )
    monkeypatch.setattr(
        runtime,
        "_normalize_initial_orientation",
        lambda progress=None: None,
    )
    monkeypatch.setattr(
        runtime,
        "_ensure_live_transport",
        lambda progress=None: None,
    )

    runtime.ensure_ready()

    assert recovered == [True]
    assert booted == [True]
