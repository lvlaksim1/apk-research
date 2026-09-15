from __future__ import annotations

import base64
import subprocess
import time

import pytest

from mobile_research.desktop.android_runtime import (
    AndroidBootTimeout,
    AndroidRuntime,
    AndroidRuntimeError,
    acceleration_provider,
)
from mobile_research.desktop.components import ComponentManager
from mobile_research.desktop.emulator_grpc import LiveFrame


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
        "_ensure_live_transport",
        lambda progress, **kwargs: True,
    )
    monkeypatch.setattr(
        runtime,
        "stop",
        lambda: None,
    )

    runtime._boot_managed_emulator(None)

    assert attempts == [
        ("host", "grpc-embedded"),
        ("auto", "grpc-embedded"),
        ("swiftshader", "headless"),
        ("host", "dwm-live"),
        ("auto", "dwm-live"),
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
    assert runtime.native_display_supported is True



def test_startup_cleanup_removes_only_avd_lock_entries(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    manager.paths.avd_home.mkdir(
        parents=True,
        exist_ok=True,
    )
    manager.paths.avd_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    keep = manager.paths.avd_dir / "userdata-qemu.img"
    keep.write_bytes(b"data")
    lock_file = (
        manager.paths.avd_dir
        / "hardware-qemu.ini.lock"
    )
    lock_file.write_text("lock", encoding="utf-8")
    lock_dir = (
        manager.paths.avd_home
        / "multiinstance.lock"
    )
    lock_dir.mkdir()

    runtime = AndroidRuntime(manager)
    removed = runtime._remove_stale_avd_locks()

    assert set(removed) == {
        lock_file,
        lock_dir,
    }
    assert keep.is_file()
    assert not lock_file.exists()
    assert not lock_dir.exists()


def test_startup_cleanup_does_not_remove_locks_while_process_remains(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    manager.paths.avd_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    lock_file = manager.paths.avd_dir / "active.lock"
    lock_file.write_text("lock", encoding="utf-8")
    runtime = AndroidRuntime(manager)

    monkeypatch.setattr(
        runtime,
        "_is_windows",
        lambda: True,
    )
    monkeypatch.setattr(
        runtime,
        "_other_mobile_research_instance_running",
        lambda: False,
    )
    monkeypatch.setattr(
        runtime,
        "_windows_managed_avd_processes",
        lambda: [
            {
                "pid": 1234,
                "name": "emulator.exe",
                "command_line": "@mobile_research_api35",
            }
        ],
    )
    monkeypatch.setattr(
        runtime,
        "_wait_for_managed_processes_to_exit",
        lambda timeout: None,
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            1,
            b"",
            b"",
        ),
    )

    report = runtime.cleanup_stale_managed_runtime()

    assert report["remaining_processes"]
    assert lock_file.is_file()



def test_emulator_command_adds_wipe_data_only_for_recovery(
    tmp_path,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)
    runtime._grpc_port = 8554

    assert "-wipe-data" not in runtime._emulator_command()

    runtime._wipe_data_next_start = True
    assert "-wipe-data" in runtime._emulator_command()


def test_wait_for_boot_detects_online_stall(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)
    clock = [0.0]

    monkeypatch.setattr(
        time,
        "monotonic",
        lambda: clock[0],
    )
    monkeypatch.setattr(
        time,
        "sleep",
        lambda seconds: clock.__setitem__(
            0,
            clock[0] + seconds,
        ),
    )
    monkeypatch.setattr(
        runtime,
        "_ensure_process_alive",
        lambda: None,
    )
    monkeypatch.setattr(
        runtime,
        "_device_online",
        lambda: True,
    )
    monkeypatch.setattr(
        runtime,
        "_adb_shell",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            ["adb"],
            0,
            stdout="",
            stderr="",
        ),
    )

    with pytest.raises(
        AndroidBootTimeout,
        match="ADB доступен",
    ):
        runtime._wait_for_boot(
            None,
            boot_timeout=30.0,
            online_stall_timeout=5.0,
        )


def test_stalled_boot_recovery_wipes_once(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    _make_components_ready(manager)
    runtime = AndroidRuntime(manager)
    starts: list[bool] = []

    monkeypatch.setattr(
        runtime,
        "stop",
        lambda: None,
    )
    monkeypatch.setattr(
        runtime,
        "cleanup_stale_managed_runtime",
        lambda: {},
    )
    monkeypatch.setattr(
        runtime,
        "_start_profile_display",
        lambda progress, display_ready: starts.append(
            runtime._wipe_data_next_start
        ),
    )
    monkeypatch.setattr(
        runtime,
        "_wait_for_boot",
        lambda progress, **kwargs: None,
    )

    stage = runtime._recover_stalled_boot(
        None,
        None,
    )

    assert stage == "wipe-data"
    assert starts == [True]
    assert runtime._wipe_data_next_start is False


def test_boot_timeout_does_not_fall_through_to_graphics_profiles(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    runtime = AndroidRuntime(manager)
    runtime._software_acceleration = False
    starts: list[tuple[str, str]] = []

    monkeypatch.setattr(
        runtime,
        "_is_windows",
        lambda: True,
    )

    def fake_start(progress, display_ready):
        starts.append(
            (
                runtime._gpu_mode,
                runtime._display_mode,
            )
        )

    monkeypatch.setattr(
        runtime,
        "_start_profile_display",
        fake_start,
    )
    monkeypatch.setattr(
        runtime,
        "_wait_for_boot",
        lambda progress: (_ for _ in ()).throw(
            AndroidBootTimeout("stalled")
        ),
    )
    monkeypatch.setattr(
        runtime,
        "_recover_stalled_boot",
        lambda progress, display_ready: (
            (_ for _ in ()).throw(
                AndroidBootTimeout(
                    "clean AVD still stalled"
                )
            )
        ),
    )
    monkeypatch.setattr(
        runtime,
        "stop",
        lambda: None,
    )

    with pytest.raises(
        AndroidBootTimeout,
        match="clean AVD still stalled",
    ):
        runtime._boot_managed_emulator(None)

    assert starts == [
        ("host", "grpc-embedded"),
    ]
    assert len(runtime._startup_attempts) == 1
    assert runtime._startup_attempts[0]["status"] == "failed"


def test_windows_startup_profiles_are_embedded_first(
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

    profiles = runtime._startup_profiles()

    assert profiles[0][:2] == (
        "host",
        "grpc-embedded",
    )
    assert profiles[1][:2] == (
        "auto",
        "grpc-embedded",
    )
    assert profiles[-1][1] == "dwm-live"


def test_display_ready_callback_is_emitted_for_embedded_mode(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    runtime = AndroidRuntime(manager)
    runtime._display_mode = "grpc-embedded"
    seen = []

    monkeypatch.setattr(
        runtime,
        "_start_emulator",
        lambda progress: None,
    )
    monkeypatch.setattr(
        runtime,
        "_ensure_live_transport",
        lambda progress, **kwargs: True,
    )

    runtime._start_profile_display(
        None,
        lambda pid, avd, mode: seen.append(
            (pid, avd, mode)
        ),
    )

    assert len(seen) == 1
    assert seen[0][1] == "mobile_research_api35"
    assert seen[0][2] == "grpc-embedded"


def test_screen_frames_upgrades_to_grpc_after_early_fallback(
    tmp_path,
    monkeypatch,
) -> None:
    manager = ComponentManager(tmp_path)
    runtime = AndroidRuntime(manager)

    class FakeStop:
        def is_set(self):
            return False

        def wait(self, _seconds):
            return False

    class FakeClient:
        def stream_frames(self, **kwargs):
            yield LiveFrame(
                encoding="rgba8888",
                data=b"\x00\x00\x00\xff",
                width=1,
                height=1,
                input_width=1,
                input_height=1,
                transport="grpc-mmap",
            )

    client = FakeClient()
    sequence = [None, client]

    monkeypatch.setattr(
        runtime,
        "_get_grpc_client",
        lambda: sequence.pop(0)
        if sequence
        else client,
    )
    monkeypatch.setattr(
        runtime,
        "screenshot_png",
        lambda: b"",
    )

    frame = next(
        runtime.screen_frames(
            FakeStop(),
            width=1,
            height=1,
        )
    )

    assert frame.transport == "grpc-mmap"
