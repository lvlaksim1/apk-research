from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "{{5C5EE2B7-78FB-47E1-95C7-85AA2540195A}"


def test_full_and_update_installers_share_identity() -> None:
    full = (
        ROOT / "packaging" / "full.iss"
    ).read_text(encoding="utf-8")
    update = (
        ROOT / "packaging" / "update.iss"
    ).read_text(encoding="utf-8")

    assert APP_ID in full
    assert APP_ID in update
    assert "apk-research-setup_v{#MyAppVersion}" in full
    assert "apk-research-update_v{#MyAppVersion}" in update
    assert "UsePreviousAppDir=no" in full
    assert "UsePreviousAppDir=yes" in update
    assert "InitializeSetup(): Boolean" in update
    assert "Для первой установки используйте полный установщик" in update


def test_shortcuts_are_owned_by_inno_setup() -> None:
    for name in ("full.iss", "update.iss"):
        text = (
            ROOT / "packaging" / name
        ).read_text(encoding="utf-8")
        assert '[Tasks]' in text
        assert 'Name: "desktopicon"' in text
        assert '{autoprograms}\\apk-research' in text
        assert '{userdesktop}\\apk-research' in text
        assert 'SetupIconFile=..\\build\\app-icon\\apk-research.ico' in text


def test_update_installer_does_not_uninstall_first() -> None:
    text = (
        ROOT / "packaging" / "update.iss"
    ).read_text(encoding="utf-8").lower()

    assert "unins000.exe" not in text
    assert "exec(" not in text or "unins" not in text
