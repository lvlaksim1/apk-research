from __future__ import annotations

import subprocess

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
