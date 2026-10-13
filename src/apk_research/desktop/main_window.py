from __future__ import annotations

import json
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QSettings,
    QThread,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QSizePolicy,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QMenu,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from apk_research import __version__
from apk_research.desktop.android_view import (
    AndroidView,
)
from apk_research.desktop.controller import (
    DesktopController,
)
from apk_research.desktop.http_window import (
    HttpTransactionsWindow,
)
from apk_research.desktop.live_https import LiveHttpsView
from apk_research.desktop.updater import (
    DownloadedUpdate,
    ReleaseInfo,
    check_latest_release,
    download_release,
    is_newer_version,
    launch_update_installer,
)
from apk_research.session import (
    default_runtime_root,
)


class _UpdateCheckThread(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        current_version: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.current_version = current_version

    def run(self) -> None:
        try:
            release = check_latest_release(
                self.current_version
            )
        except Exception as exc:
            self.failed.emit(
                str(exc) or exc.__class__.__name__
            )
            return
        self.ready.emit(release)


class _UpdateDownloadThread(QThread):
    ready = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(
        self,
        release: ReleaseInfo,
        current_version: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.release = release
        self.current_version = current_version

    def run(self) -> None:
        try:
            downloaded = download_release(
                self.release,
                current_version=self.current_version,
                progress=self._emit_progress,
            )
        except Exception as exc:
            self.failed.emit(
                str(exc) or exc.__class__.__name__
            )
            return
        self.ready.emit(downloaded)

    def _emit_progress(
        self,
        current: int,
        total: int,
    ) -> None:
        self.progress.emit(
            int(current),
            int(total),
        )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("apk-research")
        self.resize(1280, 820)
        self.setMinimumSize(1050, 700)
        self.settings = QSettings(
            "apk-research",
            "apk-research",
        )
        self.controller = DesktopController(self)
        self._research_active = False
        self._analysis_active = False
        self._analysis_starting = False
        self._recording_starting = False
        self._preferred_package: str | None = None
        self._busy = False
        self._last_archive: str | None = None
        self._selected_package_path: str | None = None
        self._latest_release: ReleaseInfo | None = None
        self._update_check_thread: _UpdateCheckThread | None = None
        self._update_download_thread: _UpdateDownloadThread | None = None
        self._update_busy = False
        self._applying_update = False
        self._http_windows: list[HttpTransactionsWindow] = []
        self._build_ui()
        self._connect_signals()
        self._refresh_component_state()
        QTimer.singleShot(
            500,
            self.controller.refresh_diagnostics,
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._applying_update:
            self.settings.setValue(
                "research_splitter", self.research_splitter.saveState()
            )
            self.controller.close()
            event.accept()
            return
        if (
            (
                self._update_check_thread is not None
                and self._update_check_thread.isRunning()
            )
            or (
                self._update_download_thread is not None
                and self._update_download_thread.isRunning()
            )
        ):
            QMessageBox.information(
                self,
                "Обновление",
                "Дождитесь завершения текущей операции обновления.",
            )
            event.ignore()
            return
        if self._research_active:
            response = QMessageBox.question(
                self,
                "Исследование активно",
                "Сначала завершить исследование и "
                "закрыть apk-research?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.Cancel,
            )
            if (
                response
                != QMessageBox.StandardButton.Yes
            ):
                event.ignore()
                return
            self.controller.stop_research()
            QMessageBox.information(
                self,
                "Завершение",
                "Запрошено сохранение исследования. "
                "Закройте программу после появления "
                "Research ZIP.",
            )
            event.ignore()
            return
        self.settings.setValue(
            "research_splitter", self.research_splitter.saveState()
        )
        self.controller.close()
        event.accept()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(
            10,
            10,
            10,
            10,
        )
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("apk-research")
        title.setStyleSheet(
            "font-size: 22px; font-weight: 600;"
        )
        subtitle = QLabel(
            "Полный архив исследования и HTTPS в реальном времени"
        )
        subtitle.setStyleSheet(
            "color: #7b838c;"
        )
        header.addWidget(title)
        header.addSpacing(12)
        header.addWidget(subtitle)
        header.addStretch(1)
        self.global_status = QLabel(
            "Подготовка…"
        )
        self.global_status.setStyleSheet(
            "font-weight: 600;"
        )
        header.addWidget(self.global_status)
        root.addLayout(header)

        self.https_view = LiveHttpsView(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_research_tab(), "Исследование")
        root.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        # Keep evidence collectors and service operations unchanged.
        # Technical pages are no longer part of main navigation.
        self._hidden_pages = [
            self._build_results_tab(),
            self._build_sessions_tab(),
            self._build_diagnostics_tab(),
        ]
        for page in self._hidden_pages:
            page.setParent(self)
            page.hide()

        self._service_dialog = QDialog(self)
        self._service_dialog.setWindowTitle("Обновление и обслуживание")
        self._service_dialog.resize(620, 520)
        service_layout = QVBoxLayout(self._service_dialog)
        service_layout.addWidget(self._build_settings_tab())
        menu = self.menuBar().addMenu("Программа")
        menu.addAction(
            "Открыть папку ZIP",
            lambda: self._open_folder(default_runtime_root()),
        )
        menu.addAction(
            "Обновление и обслуживание…",
            self._service_dialog.show,
        )

    def _build_research_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )
        splitter.setChildrenCollapsible(False)
        self.research_splitter = splitter

        left = QWidget()
        left.setMinimumWidth(235)
        left.setMaximumWidth(420)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(9)

        self.prepare_button = QPushButton("1. Подготовить Android")
        self.prepare_button.setMinimumHeight(38)
        left_layout.addWidget(self.prepare_button)

        self.status_android = QLabel("○ Android не подготовлен")
        self.status_android.setWordWrap(True)
        left_layout.addWidget(self.status_android)
        self.status_adb = QLabel("○ ADB")
        self.status_root = QLabel("○ Root")
        self.status_adb.hide()
        self.status_root.hide()

        self.choose_apk_button = QPushButton("2. Выбрать приложение (APK/XAPK)")
        self.choose_apk_button.setMinimumHeight(38)
        left_layout.addWidget(self.choose_apk_button)
        self.apk_path = QLineEdit()
        self.apk_path.setReadOnly(True)
        self.apk_path.setPlaceholderText("Файл APK/XAPK не выбран")
        left_layout.addWidget(self.apk_path)
        self.install_package_button = QPushButton("3. Установить выбранное приложение")
        self.install_package_button.setMinimumHeight(38)
        self.install_package_button.setEnabled(False)
        left_layout.addWidget(self.install_package_button)
        self.package_label = QLabel("Выбранное приложение: —")
        self.package_label.setWordWrap(True)
        self.status_package = QLabel("○ Приложение не выбрано")
        self.status_package.setWordWrap(True)
        left_layout.addWidget(self.package_label)

        app_label = QLabel("4. Установленные приложения")
        app_label.setStyleSheet("font-weight: 600;")
        app_header = QHBoxLayout()
        app_header.addWidget(app_label)
        app_header.addStretch(1)
        self.refresh_apps_button = QPushButton("⟳")
        self.refresh_apps_button.setToolTip("Обновить список установленных приложений")
        self.refresh_apps_button.setFixedWidth(32)
        app_header.addWidget(self.refresh_apps_button)
        left_layout.addLayout(app_header)
        choice_row = QHBoxLayout()
        choice_row.setSpacing(5)
        self.installed_apps = QComboBox()
        self.installed_apps.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.installed_apps.setMinimumHeight(38)
        self.installed_apps.setToolTip("Выберите приложение для анализа")
        choice_row.addWidget(self.installed_apps, 1)
        self.start_button = QPushButton("Начать анализ")
        self.start_button.setToolTip("Включить HTTPS и запустить выбранное приложение")
        self.start_button.setMinimumHeight(38)
        self.start_button.setEnabled(False)
        self.start_button.setStyleSheet("font-weight: 600;")
        choice_row.addWidget(self.start_button)
        left_layout.addLayout(choice_row)

        self.stop_button = QPushButton("5. Начать запись ZIP")
        self.stop_button.setMinimumHeight(44)
        self.stop_button.setEnabled(False)
        left_layout.addWidget(self.stop_button)
        self.session_label = QLabel("Анализ выключен · запись ZIP выключена")
        self.session_label.setWordWrap(True)
        left_layout.addWidget(self.session_label)
        self.status_network = QLabel("○ Запись ZIP выключена")
        self.status_network.setWordWrap(True)
        left_layout.addWidget(self.status_network)

        self.zip_folder_button = QPushButton("6. Открыть папку с ZIP")
        self.zip_folder_button.setMinimumHeight(38)
        self.zip_folder_button.clicked.connect(
            lambda: self._open_folder(default_runtime_root())
        )
        left_layout.addWidget(self.zip_folder_button)

        self.progress_label = QLabel("Готово")
        self.progress_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        left_layout.addWidget(self.progress_label)
        left_layout.addWidget(self.progress_bar)
        left_layout.addStretch(1)

        # Compatibility with older event handlers: launch is now automatic.
        self.launch_package_button = QPushButton(left)
        self.launch_package_button.hide()

        android_container = QWidget()
        android_layout = QVBoxLayout(
            android_container
        )
        android_layout.setContentsMargins(
            8,
            0,
            0,
            0,
        )
        toolbar = QHBoxLayout()
        android_title = QLabel("Android")
        android_title.setStyleSheet(
            "font-size: 16px; font-weight: 600;"
        )
        android_title.setToolTip(
            "Мышь: касание • Ctrl+перетаскивание: жест двумя пальцами • "
            "Shift+перетаскивание: наклон • колесо: прокрутка"
        )
        toolbar.addWidget(android_title)
        toolbar.addStretch(1)
        android_layout.addLayout(toolbar)
        self.android_view = AndroidView()
        screen_and_tools = QHBoxLayout()
        screen_and_tools.setSpacing(5)
        screen_and_tools.addWidget(self.android_view, 1)
        screen_and_tools.addWidget(self._build_emulator_toolbar())
        android_layout.addLayout(screen_and_tools, 1)

        splitter.addWidget(left)
        splitter.addWidget(android_container)
        splitter.addWidget(self.https_view)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 4)
        splitter.setSizes([255, 455, 510])
        saved = self.settings.value("research_splitter")
        if saved is not None:
            splitter.restoreState(saved)
        layout.addWidget(splitter, 1)
        return page

    def _build_emulator_toolbar(self) -> QWidget:
        from PySide6.QtWidgets import QScrollArea

        panel = QScrollArea()
        panel.setFixedWidth(53)
        panel.setWidgetResizable(True)
        panel.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel.setFrameShape(QFrame.Shape.NoFrame)
        panel.setObjectName("emulatorControls")
        panel.setStyleSheet(
            "QScrollArea#emulatorControls {background:#242630; border:0;}"
            "QWidget#emulatorButtons {background:#242630;}"
            "QToolButton {background:transparent; color:#e4e7ee;"
            " font-size:17px; border:0; padding:1px;}"
            "QToolButton:hover {background:#3b4153; border-radius:5px;}"
        )
        inner = QWidget()
        inner.setObjectName("emulatorButtons")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(1)
        self.emulator_buttons = {}

        def add_button(action: str, symbol: str, hint: str):
            button = QToolButton(inner)
            button.setText(symbol)
            button.setToolTip(hint)
            button.setAccessibleName(hint)
            button.setFixedSize(35, 28)
            button.clicked.connect(
                lambda checked=False, name=action:
                self._emulator_button_action(name)
            )
            layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignHCenter)
            self.emulator_buttons[action] = button

        groups = (
            (
                ("back", "‹", "Назад"),
                ("home", "⌂", "Главный экран Android"),
                ("recent", "▣", "Последние приложения"),
                ("volume_up", "＋", "Громкость выше"),
                ("volume_down", "－", "Громкость ниже"),
                ("rotate", "⟳", "Повернуть экран"),
                ("screenshot", "▧", "Снимок экрана в PNG"),
                ("fullscreen", "⛶", "Полноэкранный режим"),
                ("install", "APK", "Выбрать и установить APK/XAPK"),
                ("restart", "↻", "Перезагрузить Android"),
            ),
            (
                ("push_file", "⇧", "Передать файл в Android"),
                ("pull_file", "⇩", "Получить файл из Android"),
                ("stop_app", "■", "Остановить приложение"),
                ("clear_app", "⌫", "Очистить данные приложения"),
                ("settings_app", "⚙", "Настройки приложения"),
                ("location", "⌖", "Задать геолокацию"),
                ("shake", "≈", "Встряхнуть устройство"),
                ("paste_text", "T", "Ввести текст из буфера ПК"),
            ),
        )
        for i, group in enumerate(groups):
            if i:
                layout.addSpacing(8)
            for entry in group:
                add_button(*entry)
        layout.addStretch(1)
        panel.setWidget(inner)
        return panel

    def _emulator_button_action(self, action: str) -> None:
        if action == "back":
            self.controller.keyevent(4)
            return
        if action == "home":
            self.controller.keyevent(3)
            return
        if action == "fullscreen":
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
            return
        if action == "install":
            if self._analysis_active or self._research_active:
                QMessageBox.information(
                    self, "Анализ выполняется",
                    "Остановите анализ перед установкой другого приложения.",
                )
                return
            if self._choose_apk():
                self._install_selected_package()
            return
        if action == "screenshot":
            folder = default_runtime_root() / "screenshots"
            folder.mkdir(parents=True, exist_ok=True)
            suggested = folder / (
                "android-" + datetime.now().strftime("%Y%m%d-%H%M%S")
                + ".png"
            )
            path, _ = QFileDialog.getSaveFileName(
                self, "Сохранить снимок Android", str(suggested),
                "Изображения PNG (*.png)",
            )
            if path:
                if not self.android_view.save_screenshot(path):
                    QMessageBox.warning(
                        self, "Снимок экрана",
                        "Изображение Android пока недоступно",
                    )
            return
        if action == "paste_text":
            value = QApplication.clipboard().text()
            if value:
                self.controller.text_input(value)
            return
        active = self._research_active or self._analysis_active
        if action in {
            "restart", "push_file", "pull_file", "stop_app",
            "clear_app", "settings_app", "shake",
        } and active:
            QMessageBox.information(
                self, "Исследование выполняется",
                "Завершите исследование и сохраните ZIP перед этим действием.",
            )
            return
        if action in {"restart", "clear_app"}:
            message = (
                "Android будет перезапущен. Данные приложений сохранятся."
                if action == "restart"
                else "Все данные выбранного приложения будут удалены. Продолжить?"
            )
            if QMessageBox.question(
                self, "Подтверждение действия", message,
            ) != QMessageBox.StandardButton.Yes:
                return
        if action in {"stop_app", "clear_app", "settings_app"}:
            if not self.controller.package_name:
                QMessageBox.information(
                    self, "Приложение", "Сначала установите APK/XAPK",
                )
                return
            self.controller.run_emulator_action(
                action, self.controller.package_name,
            )
            return
        if action == "push_file":
            path, _ = QFileDialog.getOpenFileName(
                self, "Файл для Android",
            )
            if not path:
                return
            self.controller.run_emulator_action(action, path)
            return
        if action == "pull_file":
            remote, ok = QInputDialog.getText(
                self, "Получить файл", "Путь Android (начинается с /sdcard/):",
                text="/sdcard/Download/",
            )
            if not ok or not remote.strip():
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "Куда сохранить файл", Path(remote).name,
            )
            if path:
                self.controller.run_emulator_action(
                    action, remote.strip(), path,
                )
            return
        if action == "location":
            lat, ok = QInputDialog.getDouble(
                self, "Координаты Android", "Широта:", 0.0, -90, 90, 6,
            )
            if not ok:
                return
            lon, ok = QInputDialog.getDouble(
                self, "Координаты Android", "Долгота:", 0.0, -180, 180, 6,
            )
            if ok:
                self.controller.run_emulator_action(
                    action, str(lat), str(lon),
                )
            return
        self.controller.run_emulator_action(action)

    def _build_results_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        buttons = QHBoxLayout()
        self.results_refresh = QPushButton(
            "Обновить"
        )
        self.results_verify = QPushButton(
            "Проверить целостность"
        )
        self.results_audit = QPushButton(
            "Полный аудит"
        )
        self.results_timeline = QPushButton(
            "Research Timeline"
        )
        self.results_http = QPushButton(
            "HTTP/HTTPS"
        )
        self.results_open = QPushButton(
            "Открыть папку"
        )
        buttons.addWidget(
            self.results_refresh
        )
        buttons.addWidget(
            self.results_verify
        )
        buttons.addWidget(
            self.results_audit
        )
        buttons.addWidget(
            self.results_timeline
        )
        buttons.addWidget(
            self.results_http
        )
        buttons.addWidget(
            self.results_open
        )
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.results_table = QTableWidget(
            0,
            4,
        )
        self.results_table.setHorizontalHeaderLabels(
            [
                "Research ZIP",
                "Статус",
                "Package",
                "Размер",
            ]
        )
        self.results_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.results_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.results_table.horizontalHeader().setStretchLastSection(
            True
        )
        layout.addWidget(
            self.results_table,
            1,
        )

        self.result_details = QPlainTextEdit()
        self.result_details.setReadOnly(True)
        self.result_details.setMaximumHeight(
            230
        )
        layout.addWidget(
            self.result_details
        )
        return page

    def _build_sessions_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        buttons = QHBoxLayout()
        self.sessions_refresh = QPushButton(
            "Обновить"
        )
        self.sessions_open = QPushButton(
            "Открыть папку сессии"
        )
        buttons.addWidget(
            self.sessions_refresh
        )
        buttons.addWidget(
            self.sessions_open
        )
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.sessions_table = QTableWidget(
            0,
            4,
        )
        self.sessions_table.setHorizontalHeaderLabels(
            [
                "Session ID",
                "Статус",
                "Package",
                "Updated",
            ]
        )
        self.sessions_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.sessions_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.sessions_table.horizontalHeader().setStretchLastSection(
            True
        )
        layout.addWidget(
            self.sessions_table,
            1,
        )
        return page

    def _build_diagnostics_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        buttons = QHBoxLayout()
        self.diagnostics_refresh = QPushButton(
            "Обновить диагностику"
        )
        buttons.addWidget(
            self.diagnostics_refresh
        )
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.diagnostics_text = (
            QPlainTextEdit()
        )
        self.diagnostics_text.setReadOnly(True)
        layout.addWidget(
            self.diagnostics_text,
            1,
        )

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(240)
        layout.addWidget(
            QLabel("Журнал apk-research")
        )
        layout.addWidget(self.log_text)
        return page

    def _build_settings_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        component_group = QGroupBox(
            "Локальные компоненты"
        )
        component_layout = QVBoxLayout(
            component_group
        )
        self.components_path_label = QLabel(
            str(
                self.controller.runtime.paths.root
            )
        )
        self.components_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.open_components = QPushButton(
            "Открыть папку компонентов"
        )
        self.reset_android_button = QPushButton(
            "Сбросить Android в чистое состояние"
        )
        self.repair_components_button = QPushButton(
            "Переустановить Android-компоненты"
        )
        component_layout.addWidget(
            QLabel(
                "Android SDK, Emulator и AVD "
                "хранятся только внутри apk-research:"
            )
        )
        component_layout.addWidget(
            self.components_path_label
        )
        component_layout.addWidget(
            self.open_components
        )
        component_layout.addWidget(
            self.reset_android_button
        )
        component_layout.addWidget(
            self.repair_components_button
        )
        layout.addWidget(component_group)

        session_group = QGroupBox(
            "Данные исследований"
        )
        session_layout = QVBoxLayout(
            session_group
        )
        self.sessions_path_label = QLabel(
            str(default_runtime_root())
        )
        self.sessions_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.open_sessions = QPushButton(
            "Открыть папку исследований"
        )
        session_layout.addWidget(
            self.sessions_path_label
        )
        session_layout.addWidget(
            self.open_sessions
        )
        layout.addWidget(session_group)

        update_group = QGroupBox(
            "Обновление программы"
        )
        update_layout = QVBoxLayout(
            update_group
        )
        self.update_version_label = QLabel(
            f"Текущая версия: {__version__}"
        )
        self.update_status_label = QLabel(
            "Обновления ещё не проверялись."
        )
        self.update_status_label.setWordWrap(True)
        update_buttons = QHBoxLayout()
        self.check_updates_button = QPushButton(
            "Проверить обновления"
        )
        self.install_update_button = QPushButton(
            "Обновить"
        )
        self.install_update_button.setVisible(False)
        update_buttons.addWidget(
            self.check_updates_button
        )
        update_buttons.addWidget(
            self.install_update_button
        )
        update_buttons.addStretch(1)
        self.update_progress = QProgressBar()
        self.update_progress.setRange(0, 1000)
        self.update_progress.setValue(0)
        self.update_progress.setVisible(False)
        update_layout.addWidget(
            self.update_version_label
        )
        update_layout.addWidget(
            self.update_status_label
        )
        update_layout.addLayout(update_buttons)
        update_layout.addWidget(
            self.update_progress
        )
        layout.addWidget(update_group)

        note = QLabel(
            "Python, Android Studio и отдельный ADB "
            "пользователю не требуются. При первом "
            "запуске apk-research сама загружает "
            "необходимые Android-компоненты в свой каталог."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "color: #7b838c;"
        )
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _connect_signals(self) -> None:
        c = self.controller
        self.choose_apk_button.clicked.connect(
            self._choose_apk
        )
        self.install_package_button.clicked.connect(
            self._install_selected_package
        )
        self.prepare_button.clicked.connect(self._prepare_environment)
        self.refresh_apps_button.clicked.connect(c.refresh_installed_apps)
        self.installed_apps.currentIndexChanged.connect(
            self._on_selected_app
        )
        self.start_button.clicked.connect(self._toggle_analysis)
        self.stop_button.clicked.connect(self._toggle_zip)
        self.android_view.swipeRequested.connect(
            c.swipe
        )
        self.android_view.touchStateRequested.connect(
            c.touch_state
        )
        self.android_view.keyRequested.connect(
            c.keyevent
        )
        self.android_view.textRequested.connect(
            c.text_input
        )
        c.progress.connect(
            self._on_progress
        )
        c.log.connect(self._append_log)
        c.emulatorActionFinished.connect(self._on_emulator_action_finished)
        c.error.connect(self._on_error)
        c.environmentReady.connect(
            self._on_environment_ready
        )
        c.apkReady.connect(
            self._on_apk_ready
        )
        c.installedAppsReady.connect(self._on_installed_apps)
        c.analysisStarted.connect(self._on_analysis_started)
        c.analysisStopped.connect(self._on_analysis_stopped)
        c.researchStarted.connect(
            self._on_research_started
        )
        c.researchHealth.connect(
            self._on_research_health
        )
        c.researchFinished.connect(
            self._on_research_finished
        )
        c.researchFailed.connect(self._on_research_failed)
        c.screenFrame.connect(
            self.android_view.set_frame
        )
        c.operationBusy.connect(
            self._on_busy
        )
        c.archiveInspection.connect(
            self._on_archive_inspection
        )
        c.timelineReady.connect(
            self._on_timeline_ready
        )
        c.diagnosticsReady.connect(
            self._on_diagnostics
        )

        self.results_refresh.clicked.connect(
            self._refresh_results
        )
        self.results_verify.clicked.connect(
            lambda: self._inspect_selected_archive(
                False
            )
        )
        self.results_audit.clicked.connect(
            lambda: self._inspect_selected_archive(
                True
            )
        )
        self.results_timeline.clicked.connect(
            self._inspect_selected_timeline
        )
        self.results_http.clicked.connect(
            self._inspect_selected_http
        )
        self.results_open.clicked.connect(
            self._open_selected_archive_folder
        )
        self.sessions_refresh.clicked.connect(
            self._refresh_sessions
        )
        self.sessions_open.clicked.connect(
            self._open_selected_session
        )
        self.diagnostics_refresh.clicked.connect(
            c.refresh_diagnostics
        )
        self.open_components.clicked.connect(
            lambda: self._open_folder(
                self.controller.runtime.paths.root
            )
        )
        self.open_sessions.clicked.connect(
            lambda: self._open_folder(
                default_runtime_root()
            )
        )
        self.reset_android_button.clicked.connect(
            self._reset_android
        )
        self.repair_components_button.clicked.connect(
            self._repair_components
        )
        self.check_updates_button.clicked.connect(
            self._check_for_updates
        )
        self.install_update_button.clicked.connect(
            self._install_latest_update
        )

    def _check_for_updates(self) -> None:
        if self._update_busy:
            return
        self._latest_release = None
        self._update_busy = True
        self.install_update_button.setVisible(False)
        self.update_progress.setVisible(False)
        self.update_status_label.setText(
            "Проверка последнего стабильного релиза GitHub…"
        )
        self._refresh_update_controls()

        thread = _UpdateCheckThread(
            __version__,
            self,
        )
        self._update_check_thread = thread
        thread.ready.connect(
            self._on_update_check_ready
        )
        thread.failed.connect(
            self._on_update_check_failed
        )
        thread.finished.connect(
            self._on_update_check_finished
        )
        thread.start()

    def _on_update_check_ready(
        self,
        release: ReleaseInfo,
    ) -> None:
        if is_newer_version(
            release.version,
            __version__,
        ):
            self._latest_release = release
            self.update_status_label.setText(
                "Доступна новая версия: "
                f"{release.version}. "
                "Установщик будет скачан напрямую "
                "из последнего релиза GitHub."
            )
            self.install_update_button.setText(
                f"Обновить до {release.version}"
            )
            self.install_update_button.setVisible(
                True
            )
        else:
            self._latest_release = None
            self.update_status_label.setText(
                "Установлена последняя версия: "
                f"{__version__}."
            )
            self.install_update_button.setVisible(
                False
            )

    def _on_update_check_failed(
        self,
        message: str,
    ) -> None:
        self._latest_release = None
        self.update_status_label.setText(
            "Не удалось проверить обновления: "
            + message
        )
        self.install_update_button.setVisible(
            False
        )

    def _on_update_check_finished(
        self,
    ) -> None:
        thread = self._update_check_thread
        self._update_check_thread = None
        self._update_busy = False
        if thread is not None:
            thread.deleteLater()
        self._refresh_update_controls()

    def _install_latest_update(self) -> None:
        release = self._latest_release
        if release is None or self._update_busy:
            return
        if self._research_active or self._busy:
            QMessageBox.warning(
                self,
                "Обновление",
                "Завершите текущую операцию или исследование "
                "перед обновлением программы.",
            )
            return
        if os.name != "nt" or not getattr(
            sys,
            "frozen",
            False,
        ):
            QMessageBox.information(
                self,
                "Обновление",
                "Автоматическая установка доступна "
                "в установленной Windows-версии apk-research.",
            )
            return

        response = QMessageBox.question(
            self,
            "Обновление apk-research",
            "Скачать, проверить и установить "
            f"apk-research {release.version}?\n\n"
            "После проверки откроется отдельный установщик "
            "обновления, а apk-research закроется. "
            "Завершите обновление в открывшемся окне.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        self._update_busy = True
        self.update_status_label.setText(
            f"Скачивание apk-research {release.version}…"
        )
        self.update_progress.setRange(0, 0)
        self.update_progress.setVisible(True)
        self._refresh_update_controls()

        thread = _UpdateDownloadThread(
            release,
            __version__,
            self,
        )
        self._update_download_thread = thread
        thread.progress.connect(
            self._on_update_download_progress
        )
        thread.ready.connect(
            self._on_update_download_ready
        )
        thread.failed.connect(
            self._on_update_download_failed
        )
        thread.finished.connect(
            self._on_update_download_finished
        )
        thread.start()

    def _on_update_download_progress(
        self,
        current: int,
        total: int,
    ) -> None:
        if total <= 0:
            self.update_progress.setRange(0, 0)
            return
        ratio = min(
            1.0,
            max(0.0, current / total),
        )
        self.update_progress.setRange(0, 1000)
        self.update_progress.setValue(
            int(ratio * 1000)
        )
        self.update_status_label.setText(
            "Скачивание обновления — "
            f"{current / (1024 * 1024):.1f} / "
            f"{total / (1024 * 1024):.1f} МБ "
            f"({ratio * 100:.0f}%)"
        )

    def _on_update_download_ready(
        self,
        downloaded: DownloadedUpdate,
    ) -> None:
        try:
            launch_update_installer(downloaded)
        except Exception as exc:
            self._on_update_download_failed(
                str(exc) or exc.__class__.__name__
            )
            return

        self._applying_update = True
        self.update_progress.setRange(0, 1000)
        self.update_progress.setValue(1000)
        self.update_status_label.setText(
            "Установщик обновления запущен. "
            "apk-research закрывается…"
        )
        QApplication.quit()

    def _on_update_download_failed(
        self,
        message: str,
    ) -> None:
        self.update_status_label.setText(
            "Обновление не установлено: "
            + message
        )
        self.update_progress.setVisible(False)

    def _on_update_download_finished(
        self,
    ) -> None:
        thread = self._update_download_thread
        self._update_download_thread = None
        self._update_busy = False
        if thread is not None:
            thread.deleteLater()
        self._refresh_update_controls()

    def _refresh_update_controls(self) -> None:
        self.check_updates_button.setEnabled(
            not self._update_busy
        )
        self.install_update_button.setEnabled(
            not self._update_busy
            and not self._research_active
            and not self._busy
            and self._latest_release is not None
        )

    def _on_installed_apps(self, packages: list[str]) -> None:
        preferred = (
            self._preferred_package
            or self.installed_apps.currentData()
            or self.controller.package_name
        )
        self.installed_apps.blockSignals(True)
        self.installed_apps.clear()
        for package in packages:
            self.installed_apps.addItem(package, package)
        index = self.installed_apps.findData(preferred)
        if index >= 0:
            self.installed_apps.setCurrentIndex(index)
        self.installed_apps.blockSignals(False)
        self._preferred_package = None
        self._on_selected_app(self.installed_apps.currentIndex())

    def _on_selected_app(self, index: int) -> None:
        if self._analysis_active or self._research_active:
            return
        package = self.installed_apps.itemData(index) if index >= 0 else None
        self.controller.package_name = str(package) if package else None
        if package:
            self.package_label.setText("Установлено: " + str(package))
            self.status_package.setText("● Приложение установлено")
        self._update_workflow_buttons()

    def _update_workflow_buttons(self) -> None:
        editable = (
            not self._busy and not self._analysis_active
            and not self._analysis_starting and not self._research_active
        )
        self.prepare_button.setEnabled(editable)
        self.choose_apk_button.setEnabled(editable)
        self.install_package_button.setEnabled(
            editable and bool(self._selected_package_path)
        )
        self.installed_apps.setEnabled(editable)
        self.refresh_apps_button.setEnabled(editable)
        self.start_button.setText(
            "Остановить"
            if self._analysis_active else "Начать анализ"
        )
        self.start_button.setEnabled(
            (self._analysis_active and not self._research_active and not self._busy)
            or (editable and bool(self.installed_apps.currentData()))
        )
        self.stop_button.setText(
            "5. Завершить и сохранить ZIP"
            if self._research_active else "5. Начать запись ZIP"
        )
        self.stop_button.setEnabled(
            self._research_active
            or (
                self._analysis_active and not self._recording_starting
                and not self._busy
            )
        )

    def _toggle_analysis(self) -> None:
        if self._analysis_active:
            if not self._research_active:
                self.controller.stop_analysis()
            return
        package = self.installed_apps.currentData()
        if not package:
            QMessageBox.information(
                self, "Анализ HTTPS", "Выберите установленное приложение."
            )
            return
        self._analysis_starting = True
        self.session_label.setText("Подготовка анализа HTTPS…")
        self._update_workflow_buttons()
        self.controller.start_analysis(str(package))

    def _toggle_zip(self) -> None:
        if self._research_active:
            self.stop_button.setEnabled(False)
            self.controller.stop_research()
            return
        if not self._analysis_active:
            return
        self._recording_starting = True
        self.session_label.setText("Подготовка записи ZIP…")
        self._update_workflow_buttons()
        self.controller.start_research()

    def _on_analysis_started(self, data: dict) -> None:
        self._analysis_starting = False
        self._analysis_active = True
        self.https_view.begin_session(
            str(data["session_root"]), str(data["package"])
        )
        self.session_label.setText(
            "● HTTPS-анализ выполняется · ZIP не записывается"
        )
        self.global_status.setText("● HTTPS-анализ включён")
        self._update_workflow_buttons()

    def _on_analysis_stopped(self, package: str) -> None:
        self._analysis_starting = False
        self._analysis_active = False
        self.https_view.finish_session(None)
        self.https_view.note.setText(
            "HTTPS-анализ остановлен. Запросы текущего сеанса доступны для просмотра."
        )
        self.session_label.setText(
            "Анализ HTTPS остановлен · ZIP не записывается"
        )
        self.global_status.setText("Анализ остановлен")
        self._update_workflow_buttons()

    def _choose_apk(self) -> bool:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите APK или XAPK",
            "",
            "Пакеты Android (*.apk *.xapk)",
        )
        if not path:
            return False
        self._selected_package_path = path
        self.apk_path.setText(path)
        self.package_label.setText(
            "Package: файл выбран, нажмите «Установить в эмулятор»"
        )
        self._update_workflow_buttons()
        self.status_package.setText(
            "○ Пакет выбран — не установлен"
        )
        self.status_package.setStyleSheet("")
        return True

    def _install_selected_package(self) -> None:
        path = self._selected_package_path
        if not path:
            QMessageBox.information(
                self,
                "Установка приложения",
                "Сначала выберите APK или XAPK.",
            )
            return
        if not self._ensure_android_license_consent():
            return
        self.package_label.setText(
            "Package: установка…"
        )
        self.install_package_button.setEnabled(False)
        self.status_package.setText(
            "◌ Установка APK/XAPK"
        )
        self.controller.prepare_apk(path)

    def _prepare_environment(self) -> None:
        if not self._ensure_android_license_consent():
            return
        self.controller.prepare_environment()

    def _ensure_android_license_consent(
        self,
    ) -> bool:
        if self.controller.component_state.ready:
            return True
        if self.settings.value(
            "android_sdk_license_accepted",
            False,
            type=bool,
        ):
            return True
        message = QMessageBox(self)
        message.setWindowTitle(
            "Android-компоненты"
        )
        message.setIcon(
            QMessageBox.Icon.Information
        )
        message.setText(
            "apk-research загрузит Android SDK, "
            "Emulator и системный образ автоматически."
        )
        message.setInformativeText(
            "Компоненты загружаются напрямую с "
            "dl.google.com и используются только внутри "
            "apk-research. Продолжая, вы подтверждаете "
            "принятие Android SDK License Agreement: "
            "https://developer.android.com/studio/terms"
        )
        message.setStandardButtons(
            QMessageBox.StandardButton.Ok
            | QMessageBox.StandardButton.Cancel
        )
        if (
            message.exec()
            != QMessageBox.StandardButton.Ok
        ):
            return False
        self.settings.setValue(
            "android_sdk_license_accepted",
            True,
        )
        return True

    def _on_progress(
        self,
        message: str,
        current,
        total,
    ) -> None:
        if current is None or not total:
            self.progress_label.setText(message)
            self.progress_bar.setRange(0, 0)
            return

        current_value = max(0, int(current))
        total_value = max(1, int(total))
        ratio = min(
            1.0,
            current_value / total_value,
        )
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(
            int(1000 * ratio)
        )

        current_mb = current_value / (1024 * 1024)
        total_mb = total_value / (1024 * 1024)
        self.progress_label.setText(
            f"{message} — "
            f"{current_mb:.1f} / {total_mb:.1f} МБ "
            f"({ratio * 100:.0f}%)"
        )

    def _on_busy(self, busy: bool) -> None:
        self._busy = busy
        if not busy:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(1)
            self.progress_label.setText("Готово")
        self._update_workflow_buttons()
        settings_enabled = (
            not busy and not self._research_active and not self._analysis_active
        )
        self.reset_android_button.setEnabled(settings_enabled)
        self.repair_components_button.setEnabled(settings_enabled)
        self._refresh_update_controls()

    def _on_environment_ready(
        self,
        data: dict,
    ) -> None:
        self._refresh_component_state()
        if data.get("device_online"):
            transport = (
                data.get("interactive_transport")
                or {}
            )
            transport_name = (
                transport.get("active")
                if isinstance(transport, dict)
                else ""
            )
            gpu_mode = (
                transport.get("gpu_mode")
                if isinstance(transport, dict)
                else ""
            )
            suffix = ""
            if transport_name:
                suffix += f" • {transport_name}"
            if gpu_mode:
                suffix += f" • GPU {gpu_mode}"
            self.android_view.setToolTip(
                "Мышь: касание • Ctrl+перетаскивание: жест двумя пальцами • "
                "Shift+перетаскивание: наклон • колесо: прокрутка"
            )
            self.status_android.setText(
                "● Android готов" + suffix
            )
            self.status_android.setStyleSheet(
                "color: #238636;"
            )
            self.status_adb.setText(
                "● ADB подключён"
            )
            self.status_adb.setStyleSheet(
                "color: #238636;"
            )
        target = (
            data.get("target_info")
            or {}
        )
        if (
            data.get("root")
            or (
                isinstance(target, dict)
                and target.get("is_root")
            )
        ):
            self.status_root.setText(
                "● Root доступен"
            )
            self.status_root.setStyleSheet(
                "color: #238636;"
            )
        tcpdump = (
            data.get("tcpdump")
            or {}
        )
        if (
            isinstance(tcpdump, dict)
            and tcpdump.get("available")
        ):
            self.status_network.setText(
                "● PCAP готов"
            )
            self.status_network.setStyleSheet(
                "color: #238636;"
            )
        if data.get("device_online"):
            self.global_status.setText(
                "Android готов"
            )

    def _on_apk_ready(self, path: str, package: str) -> None:
        self._selected_package_path = path
        self.apk_path.setText(path)
        self._preferred_package = package
        self.package_label.setText("Установлено: " + package)
        self.status_package.setText("● Приложение установлено")
        self.global_status.setText("Приложение установлено")
        self._update_workflow_buttons()

    def _on_research_started(self, data: dict) -> None:
        self._recording_starting = False
        self._research_active = True
        self.session_label.setText(
            "● Запись ZIP идёт\n" + str(data.get("package") or "")
        )
        self.global_status.setText("● ЗАПИСЬ ZIP")
        self.global_status.setStyleSheet(
            "color: #d29922; font-weight: 700;"
        )
        self.status_network.setText("● Запись полных данных выполняется")
        self.status_network.setStyleSheet("color: #238636;")
        self._update_workflow_buttons()

    def _on_research_health(
        self,
        data: dict,
    ) -> None:
        healthy = bool(
            data.get("healthy")
        )
        base = self.session_label.text().split(
            "\nСостояние записи:"
        )[0]
        self.session_label.setText(
            base
            + "\nСостояние записи: "
            + (
                "нормально"
                if healthy
                else "есть замечания"
            )
        )

    def _on_research_finished(self, data: dict) -> None:
        self._recording_starting = False
        self._research_active = False
        self._last_archive = str(data.get("archive") or "")
        status = str(data.get("session_status") or "unknown")
        issues = data.get("validation_issues")
        self.session_label.setText(
            ("● ZIP сохранён" if status == "complete"
             else "● Запись завершена: " + status)
            + (" · есть замечания" if issues else "")
            + "\n" + self._last_archive
        )
        self.global_status.setText(
            "ZIP сохранён · HTTPS-анализ продолжается"
            if self._analysis_active else "Запись завершена"
        )
        self.global_status.setStyleSheet("font-weight: 600;")
        self.status_network.setText("○ Запись ZIP выключена")
        # Do NOT reload the archived slice into the live HTTPS table: the
        # sole analyzer remains active and supplies subsequent transactions.
        if self._analysis_active:
            self.https_view.note.setText(
                "● Анализ HTTPS продолжается. Последний ZIP сохранён отдельно."
            )
        self._refresh_results()
        self._update_workflow_buttons()

    def _on_research_failed(self, message: str) -> None:
        self._recording_starting = False
        self._research_active = False
        self.status_network.setText("○ Запись ZIP выключена")
        self.session_label.setText("Запись ZIP завершилась с ошибкой")
        self._update_workflow_buttons()

    def _on_archive_inspection(
        self,
        data: dict,
    ) -> None:
        self.result_details.setPlainText(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )
        )
        self.tabs.setCurrentIndex(0)

    def _on_timeline_ready(
        self,
        data: dict,
    ) -> None:
        self.result_details.setPlainText(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )
        )
        self.tabs.setCurrentIndex(0)

    def _on_diagnostics(
        self,
        data: dict,
    ) -> None:
        self.diagnostics_text.setPlainText(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )
        )
        target = data.get("target_info")
        if (
            isinstance(target, dict)
            and target.get("is_root")
        ):
            self.status_root.setText(
                "● Root доступен"
            )
            self.status_root.setStyleSheet(
                "color: #238636;"
            )
        if data.get("device_online"):
            self.status_android.setText(
                "● Android готов"
            )
            self.status_android.setStyleSheet(
                "color: #238636;"
            )
            self.status_adb.setText(
                "● ADB подключён"
            )
            self.status_adb.setStyleSheet(
                "color: #238636;"
            )

    def _on_emulator_action_finished(
        self, action: str, detail: str,
    ) -> None:
        self.global_status.setText(detail)
        if action in {"push_file", "pull_file", "clear_app", "restart"}:
            QMessageBox.information(self, "Android", detail)

    def _on_error(
        self,
        message: str,
    ) -> None:
        self._append_log(
            "ERROR: " + message
        )
        self.global_status.setText("Ошибка")
        self.global_status.setStyleSheet(
            "color: #f85149; font-weight: 700;"
        )
        self._analysis_starting = False
        self._recording_starting = False
        self._update_workflow_buttons()
        QMessageBox.critical(
            self,
            "apk-research",
            message,
        )

    def _append_log(
        self,
        message: str,
    ) -> None:
        self.log_text.appendPlainText(
            message
        )

    def _refresh_component_state(self) -> None:
        state = (
            self.controller.component_state
        )

        self.status_android.setText("○ Android")
        self.status_android.setStyleSheet("")
        self.status_adb.setText("○ ADB")
        self.status_adb.setStyleSheet("")
        self.status_root.setText("○ Root")
        self.status_root.setStyleSheet("")
        self.status_network.setText("○ Полная запись")
        self.status_network.setStyleSheet("")

        if self.controller.package_name:
            self.status_package.setText(
                "● Пакет установлен"
            )
            self.status_package.setStyleSheet(
                "color: #238636;"
            )
        else:
            self.status_package.setText("○ APK/XAPK")
            self.status_package.setStyleSheet("")

        if state.platform_tools:
            self.status_adb.setText(
                "● ADB установлен"
            )
            self.status_adb.setStyleSheet(
                "color: #238636;"
            )
        if (
            state.emulator
            and state.system_image
            and state.avd_profile
        ):
            self.status_android.setText(
                "● Android-компоненты установлены"
            )
            self.status_android.setStyleSheet(
                "color: #238636;"
            )
        if state.ready:
            self.global_status.setText(
                "Компоненты готовы"
            )
        elif not self._research_active:
            self.global_status.setText(
                "Android-компоненты не готовы"
            )

    def _refresh_results(self) -> None:
        root = default_runtime_root()
        root.mkdir(
            parents=True,
            exist_ok=True,
        )
        archives = sorted(
            root.glob("*.research.zip"),
            key=lambda path: (
                path.stat().st_mtime
            ),
            reverse=True,
        )
        self.results_table.setRowCount(
            len(archives)
        )
        for row, archive in enumerate(
            archives
        ):
            status = "—"
            package = "—"
            try:
                with zipfile.ZipFile(
                    archive
                ) as handle:
                    manifest = json.loads(
                        handle.read(
                            "00_manifest/session.json"
                        )
                    )
                    status = str(
                        manifest.get("status")
                        or "—"
                    )
                    package = str(
                        (
                            manifest.get(
                                "package"
                            )
                            or {}
                        ).get("name")
                        or "—"
                    )
            except Exception:
                status = "invalid"
            values = [
                archive.name,
                status,
                package,
                self._format_size(
                    archive.stat().st_size
                ),
            ]
            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    value
                )
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    str(archive),
                )
                self.results_table.setItem(
                    row,
                    column,
                    item,
                )
        self.results_table.resizeColumnsToContents()

    def _refresh_sessions(self) -> None:
        root = default_runtime_root()
        root.mkdir(
            parents=True,
            exist_ok=True,
        )
        sessions: list[
            tuple[Path, dict]
        ] = []
        for manifest_path in root.glob(
            "*/00_manifest/session.json"
        ):
            try:
                manifest = json.loads(
                    manifest_path.read_text(
                        encoding="utf-8"
                    )
                )
                sessions.append(
                    (
                        manifest_path.parent.parent,
                        manifest,
                    )
                )
            except Exception:
                continue
        sessions.sort(
            key=lambda item: str(
                (
                    item[1].get("timestamps")
                    or {}
                ).get("updated")
                or ""
            ),
            reverse=True,
        )
        self.sessions_table.setRowCount(
            len(sessions)
        )
        for row, (
            session_path,
            manifest,
        ) in enumerate(sessions):
            values = [
                str(
                    manifest.get("session_id")
                    or session_path.name
                ),
                str(
                    manifest.get("status")
                    or "—"
                ),
                str(
                    (
                        manifest.get("package")
                        or {}
                    ).get("name")
                    or "—"
                ),
                str(
                    (
                        manifest.get("timestamps")
                        or {}
                    ).get("updated")
                    or "—"
                ),
            ]
            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    value
                )
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    str(session_path),
                )
                self.sessions_table.setItem(
                    row,
                    column,
                    item,
                )
        self.sessions_table.resizeColumnsToContents()

    def _inspect_selected_archive(
        self,
        audit: bool,
    ) -> None:
        path = self._selected_table_path(
            self.results_table
        )
        if path:
            self.controller.inspect_archive(
                path,
                audit=audit,
            )

    def _inspect_selected_timeline(
        self,
    ) -> None:
        path = self._selected_table_path(
            self.results_table
        )
        if path:
            self.controller.inspect_timeline(
                path
            )

    def _inspect_selected_http(
        self,
    ) -> None:
        path = self._selected_table_path(
            self.results_table
        )
        if not path:
            return
        window = HttpTransactionsWindow(
            path,
            self,
        )
        window.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            True,
        )
        self._http_windows.append(window)
        window.show()

    def _open_selected_archive_folder(
        self,
    ) -> None:
        path = self._selected_table_path(
            self.results_table
        )
        if path:
            self._open_folder(
                Path(path).parent
            )

    def _open_selected_session(self) -> None:
        path = self._selected_table_path(
            self.sessions_table
        )
        if path:
            self._open_folder(Path(path))

    def _selected_table_path(
        self,
        table: QTableWidget,
    ) -> str | None:
        row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, 0)
        if item is None:
            return None
        value = item.data(
            Qt.ItemDataRole.UserRole
        )
        return (
            str(value)
            if value
            else None
        )

    def _reset_android(self) -> None:
        if self._research_active:
            QMessageBox.warning(
                self,
                "apk-research",
                "Нельзя сбросить Android "
                "во время исследования",
            )
            return
        response = QMessageBox.question(
            self,
            "Сброс Android",
            "Удалить пользовательские данные "
            "встроенного Android и создать чистую "
            "среду при следующем запуске?",
        )
        if (
            response
            == QMessageBox.StandardButton.Yes
        ):
            self.controller.reset_android()

    def _repair_components(self) -> None:
        if self._research_active or self._busy:
            QMessageBox.warning(
                self,
                "apk-research",
                "Нельзя переустановить Android-компоненты "
                "во время другой операции.",
            )
            return

        response = QMessageBox.question(
            self,
            "Переустановка Android-компонентов",
            "Удалить управляемые apk-research Android SDK, "
            "Emulator, system image и AVD?\n\n"
            "Данные исследований не удаляются. "
            "При следующей подготовке Android-компоненты "
            "будут загружены заново.",
        )
        if (
            response
            == QMessageBox.StandardButton.Yes
        ):
            self.controller.repair_components()

    @staticmethod
    def _open_folder(path: Path) -> None:
        path.mkdir(
            parents=True,
            exist_ok=True,
        )
        if os.name == "nt":
            os.startfile(  # type: ignore[attr-defined]
                path
            )
        else:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(
                    str(path)
                )
            )

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in (
            "B",
            "KB",
            "MB",
            "GB",
        ):
            if (
                value < 1024
                or unit == "GB"
            ):
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{size} B"
