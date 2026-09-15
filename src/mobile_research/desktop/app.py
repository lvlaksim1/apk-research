from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from mobile_research.desktop.android_runtime import (
    AndroidRuntime,
)
from mobile_research.desktop.main_window import (
    MainWindow,
)


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
        "MobileResearch"
    )
    QApplication.setApplicationName(
        "Mobile Research"
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()
