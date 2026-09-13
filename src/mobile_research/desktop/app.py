from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from mobile_research.desktop.main_window import (
    MainWindow,
)


def main() -> int:
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
