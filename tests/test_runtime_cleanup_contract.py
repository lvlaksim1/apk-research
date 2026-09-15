from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_removed_display_architectures_do_not_return() -> None:
    desktop = ROOT / "src" / "mobile_research" / "desktop"
    tests = ROOT / "tests"

    assert not (desktop / "dwm_emulator.py").exists()
    assert not (desktop / "native_emulator.py").exists()
    assert not (tests / "test_dwm_emulator.py").exists()
    assert not (tests / "test_native_emulator.py").exists()

    runtime = _read("src/mobile_research/desktop/android_runtime.py")
    grpc = _read("src/mobile_research/desktop/emulator_grpc.py")
    view = _read("src/mobile_research/desktop/android_view.py")
    controller = _read("src/mobile_research/desktop/controller.py")

    for forbidden in (
        "dwm-live",
        "adb-screencap",
        "grpc-bytes",
        "_startup_profiles",
        "_start_profile_display",
        "SetParent",
    ):
        assert forbidden not in runtime
        assert forbidden not in grpc
        assert forbidden not in view
        assert forbidden not in controller


def test_required_interactive_runtime_contract_is_explicit() -> None:
    runtime = _read("src/mobile_research/desktop/android_runtime.py")
    grpc = _read("src/mobile_research/desktop/emulator_grpc.py")

    assert "-qt-hide-window" in runtime
    assert '"required": "grpc-mmap"' in runtime
    assert '"input_required": "streamInputEvent"' in runtime
    assert 'transport="grpc-mmap"' in grpc
    assert "streamScreenshot" in grpc
    assert "streamInputEvent" in grpc


def test_dead_desktop_helpers_stay_removed() -> None:
    controller = _read("src/mobile_research/desktop/controller.py")
    view = _read("src/mobile_research/desktop/android_view.py")

    assert "def _thread_quiet(" not in controller
    assert "def session_root(" not in controller
    assert "_press_pos" not in view


def test_workflows_have_no_manual_dispatch() -> None:
    workflows = ROOT / ".github" / "workflows"
    for path in workflows.glob("*.yml"):
        assert "workflow_dispatch" not in path.read_text(encoding="utf-8")


def test_legacy_cleanup_shims_stay_removed() -> None:
    runtime = _read("src/mobile_research/desktop/android_runtime.py")
    main_window = _read("src/mobile_research/desktop/main_window.py")
    desktop_init = _read("src/mobile_research/desktop/__init__.py")
    components = _read("src/mobile_research/desktop/components.py")

    assert "def emulator_pid(" not in runtime
    assert "_last_gpu_mode" not in main_window
    assert "select_archive_from_repository_xml =" not in desktop_init
    assert "def _local_name(" not in components
    assert "def _child_text(" not in components
    assert "select_stable_archive" in components
