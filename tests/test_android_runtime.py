from __future__ import annotations

import base64
import subprocess

import pytest

from mobile_research.desktop.android_runtime import (
    AndroidRuntime,
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
