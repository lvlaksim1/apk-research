from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from apk_research.desktop.android_runtime import (
    AndroidRuntime,
)
from apk_research.desktop.main_window import MainWindow


def _application_icon() -> QIcon:
    candidates: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(
            Path(bundle_root)
            / "apk_research"
            / "resources"
            / "apk-research-icon.png"
        )
    candidates.append(
        Path(__file__).resolve().parents[3]
        / "build"
        / "app-icon"
        / "apk-research-icon.png"
    )
    for path in candidates:
        if path.is_file():
            return QIcon(str(path))
    return QIcon()


def main() -> int:
    # Recover the private Android runtime before any GUI auto-prepare can
    # observe an orphaned emulator or stale AVD lock from a previous crash.
    try:
        AndroidRuntime().cleanup_stale_managed_runtime()
    except Exception:
        # Startup recovery must never prevent the application itself from
        # opening; normal diagnostics/boot logic will report later failures.
        pass

    QApplication.setOrganizationName(
        "apk-research"
    )
    QApplication.setApplicationName(
        "apk-research"
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    icon = _application_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()
    return app.exec()
