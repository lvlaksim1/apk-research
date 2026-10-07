from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_installer_updates_existing_installation_in_place() -> None:
    text = (
        ROOT / "packaging" / "apk-research.iss"
    ).read_text(encoding="utf-8")

    assert (
        "AppId={{5C5EE2B7-78FB-47E1-95C7-85AA2540195A}"
        in text
    )
    assert "UsePreviousAppDir=yes" in text
    assert "UsePreviousGroup=yes" in text
    assert "UsePreviousTasks=yes" in text
    assert "CloseApplications=yes" in text
    assert "RestartApplications=no" in text
    assert "{param:UPDATE|0}" in text
    assert "ShouldRelaunchAfterUpdate" in text
    assert "{param:NORELAUNCH|0}" in text
    assert (
        "SetupIconFile=..\\build\\app-icon\\apk-research.ico"
        in text
    )


def test_updater_does_not_request_uninstall_before_update() -> None:
    text = (
        ROOT / "src" / "apk_research" / "desktop" / "updater.py"
    ).read_text(encoding="utf-8")

    assert '"/UPDATE=1"' in text
    assert '"powershell.exe"' not in text.lower()
    assert "build_installer_arguments" in text
    assert "unins000.exe" not in text
    assert "uninstall" not in text.lower()
