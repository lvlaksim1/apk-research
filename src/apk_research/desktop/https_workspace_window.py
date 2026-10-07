from __future__ import annotations

from apk_research.desktop import main_window as main_window_module
from apk_research.desktop.https_controller import (
    HttpsDesktopController,
)
from apk_research.desktop.https_traffic_window import (
    HttpsTrafficWindow,
)
from apk_research.desktop.investigator_workspace_v026_window import (
    InvestigatorWorkspaceV026MainWindow,
)

from PySide6.QtWidgets import QPushButton, QWidget


class HttpsInspectionMainWindow(
    InvestigatorWorkspaceV026MainWindow
):
    """v0.30 window: existing investigator UI plus decrypted HTTP(S) evidence."""

    def __init__(self) -> None:
        original_controller = (
            main_window_module.DesktopController
        )
        main_window_module.DesktopController = (
            HttpsDesktopController
        )
        try:
            super().__init__()
        finally:
            main_window_module.DesktopController = (
                original_controller
            )
        self._https_windows: list[
            HttpsTrafficWindow
        ] = []

    def _build_results_tab(
        self,
    ) -> QWidget:
        page = super()._build_results_tab()
        layout = page.layout()
        button_layout = layout.itemAt(0).layout()
        self.results_https = QPushButton(
            "HTTPS Traffic"
        )
        button_layout.insertWidget(
            max(
                0,
                button_layout.count() - 1,
            ),
            self.results_https,
        )
        return page

    def _connect_signals(self) -> None:
        super()._connect_signals()
        self.results_https.clicked.connect(
            self._inspect_selected_https
        )

    def _inspect_selected_https(
        self,
    ) -> None:
        path = self._selected_table_path(
            self.results_table
        )
        if not path:
            return
        window = HttpsTrafficWindow(
            path,
            self,
        )
        self._https_windows = [
            item
            for item in self._https_windows
            if item.isVisible()
        ]
        self._https_windows.append(
            window
        )
        window.show()
        window.raise_()
        window.activateWindow()

    def _on_research_started(
        self,
        data: dict,
    ) -> None:
        super()._on_research_started(
            data
        )
        self.status_network.setText(
            "● PCAP + HTTPS записываются"
        )

    def _on_research_finished(
        self,
        data: dict,
    ) -> None:
        super()._on_research_finished(
            data
        )
        self.status_network.setText(
            "● PCAP + HTTPS сохранены"
        )
