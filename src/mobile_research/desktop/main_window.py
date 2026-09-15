from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

from PySide6.QtCore import (
    QSettings,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
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
    QVBoxLayout,
    QWidget,
)

from mobile_research.desktop.android_view import (
    AndroidView,
)
from mobile_research.desktop.controller import (
    DesktopController,
)
from mobile_research.session import (
    default_runtime_root,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Mobile Research")
        self.resize(1280, 820)
        self.setMinimumSize(1050, 700)
        self.settings = QSettings(
            "MobileResearch",
            "MobileResearch",
        )
        self.controller = DesktopController(self)
        self._research_active = False
        self._busy = False
        self._last_archive: str | None = None
        self._last_gpu_mode = ""
        self._build_ui()
        self._connect_signals()
        self._refresh_component_state()
        self._refresh_results()
        self._refresh_sessions()
        QTimer.singleShot(
            500,
            self.controller.refresh_diagnostics,
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._research_active:
            response = QMessageBox.question(
                self,
                "Исследование активно",
                "Сначала завершить исследование и "
                "закрыть Mobile Research?",
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
        # Keep the DWM thumbnail registered until the source Emulator
        # process has stopped. Unregistering first would briefly reveal
        # the off-screen standalone source window during shutdown.
        self.controller.close()
        self.android_view.detach_native()
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
        title = QLabel("Mobile Research")
        title.setStyleSheet(
            "font-size: 22px; font-weight: 600;"
        )
        subtitle = QLabel(
            "Android application research environment"
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

        self.tabs = QTabWidget()
        self.tabs.addTab(
            self._build_research_tab(),
            "Исследование",
        )
        self.tabs.addTab(
            self._build_results_tab(),
            "Результаты",
        )
        self.tabs.addTab(
            self._build_sessions_tab(),
            "История",
        )
        self.tabs.addTab(
            self._build_diagnostics_tab(),
            "Диагностика",
        )
        self.tabs.addTab(
            self._build_settings_tab(),
            "Настройки",
        )
        root.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

    def _build_research_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        left = QWidget()
        left.setMaximumWidth(420)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(
            0,
            0,
            8,
            0,
        )

        apk_group = QGroupBox(
            "1. Исследуемое приложение"
        )
        apk_layout = QVBoxLayout(apk_group)
        self.apk_path = QLineEdit()
        self.apk_path.setReadOnly(True)
        self.apk_path.setPlaceholderText(
            "APK ещё не выбран"
        )
        self.choose_apk_button = QPushButton(
            "Выбрать APK…"
        )
        self.choose_apk_button.setMinimumHeight(
            38
        )
        self.package_label = QLabel(
            "Package: —"
        )
        self.package_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        apk_layout.addWidget(self.apk_path)
        apk_layout.addWidget(
            self.choose_apk_button
        )
        apk_layout.addWidget(
            self.package_label
        )
        left_layout.addWidget(apk_group)

        status_group = QGroupBox(
            "2. Готовность среды"
        )
        status_layout = QGridLayout(
            status_group
        )
        self.status_android = QLabel(
            "○ Android"
        )
        self.status_adb = QLabel("○ ADB")
        self.status_root = QLabel("○ Root")
        self.status_network = QLabel("○ PCAP")
        self.status_package = QLabel("○ APK")
        statuses = [
            self.status_android,
            self.status_adb,
            self.status_root,
            self.status_network,
            self.status_package,
        ]
        for row, widget in enumerate(statuses):
            status_layout.addWidget(
                widget,
                row,
                0,
            )
        self.prepare_button = QPushButton(
            "Подготовить Android"
        )
        status_layout.addWidget(
            self.prepare_button,
            5,
            0,
        )
        left_layout.addWidget(status_group)

        progress_group = QGroupBox(
            "Текущая операция"
        )
        progress_layout = QVBoxLayout(
            progress_group
        )
        self.progress_label = QLabel("Готово")
        self.progress_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        progress_layout.addWidget(
            self.progress_label
        )
        progress_layout.addWidget(
            self.progress_bar
        )
        left_layout.addWidget(progress_group)

        run_group = QGroupBox(
            "3. Исследование"
        )
        run_layout = QVBoxLayout(run_group)
        launch_label = QLabel("Запуск приложения")
        self.launch_mode = QComboBox()
        self.launch_mode.addItem(
            "Чистый запуск (рекомендуется)",
            "clean",
        )
        self.launch_mode.addItem(
            "Продолжить текущее состояние",
            "continue",
        )
        saved_launch_mode = self.settings.value(
            "research/launch_mode",
            "clean",
        )
        launch_index = self.launch_mode.findData(
            saved_launch_mode
        )
        if launch_index >= 0:
            self.launch_mode.setCurrentIndex(
                launch_index
            )
        run_layout.addWidget(launch_label)
        run_layout.addWidget(self.launch_mode)

        self.start_button = QPushButton(
            "НАЧАТЬ ИССЛЕДОВАНИЕ"
        )
        self.start_button.setMinimumHeight(54)
        self.start_button.setEnabled(False)
        self.start_button.setStyleSheet(
            "font-size: 15px; font-weight: 700;"
        )
        self.stop_button = QPushButton(
            "ЗАВЕРШИТЬ И СОХРАНИТЬ"
        )
        self.stop_button.setMinimumHeight(46)
        self.stop_button.setEnabled(False)
        self.session_label = QLabel(
            "Сессия не запущена"
        )
        self.session_label.setWordWrap(True)
        run_layout.addWidget(
            self.start_button
        )
        run_layout.addWidget(
            self.stop_button
        )
        run_layout.addWidget(
            self.session_label
        )
        left_layout.addWidget(run_group)
        left_layout.addStretch(1)

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
        toolbar.addWidget(android_title)
        toolbar.addStretch(1)
        self.android_hint = QLabel(
            "Мышь = touch • колесо = swipe • "
            "клавиатура = ввод"
        )
        self.android_hint.setStyleSheet(
            "color: #7b838c;"
        )
        toolbar.addWidget(self.android_hint)
        android_layout.addLayout(toolbar)
        self.android_view = AndroidView()
        android_layout.addWidget(
            self.android_view,
            1,
        )

        splitter.addWidget(left)
        splitter.addWidget(android_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)
        return page

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
            QLabel("Журнал Mobile Research")
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
                "хранятся только внутри Mobile Research:"
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

        note = QLabel(
            "Python, Android Studio и отдельный ADB "
            "пользователю не требуются. При первом "
            "запуске Mobile Research сама загружает "
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
        self.prepare_button.clicked.connect(
            self._prepare_environment
        )
        self.start_button.clicked.connect(
            self._start_research
        )
        self.stop_button.clicked.connect(
            c.stop_research
        )
        self.android_view.tapRequested.connect(
            c.tap
        )
        self.android_view.swipeRequested.connect(
            c.swipe
        )
        self.android_view.touchDownRequested.connect(
            c.touch_down
        )
        self.android_view.touchMoveRequested.connect(
            c.touch_move
        )
        self.android_view.touchUpRequested.connect(
            c.touch_up
        )
        self.android_view.keyRequested.connect(
            c.keyevent
        )
        self.android_view.textRequested.connect(
            c.text_input
        )
        self.android_view.nativeAttached.connect(
            self._on_native_display_attached
        )
        self.android_view.nativeAttachFailed.connect(
            self._on_native_display_failed
        )
        c.progress.connect(
            self._on_progress
        )
        c.log.connect(self._append_log)
        c.error.connect(self._on_error)
        c.environmentReady.connect(
            self._on_environment_ready
        )
        c.apkReady.connect(
            self._on_apk_ready
        )
        c.researchStarted.connect(
            self._on_research_started
        )
        c.researchHealth.connect(
            self._on_research_health
        )
        c.researchFinished.connect(
            self._on_research_finished
        )
        c.screenFrame.connect(
            self.android_view.set_frame
        )
        c.operationBusy.connect(
            self._on_busy
        )
        c.archiveInspection.connect(
            self._on_archive_inspection
        )
        c.diagnosticsReady.connect(
            self._on_diagnostics
        )
        c.nativeDisplayAvailable.connect(
            self._on_native_display_available
        )
        self.tabs.currentChanged.connect(
            self._on_tab_changed
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

    def _start_research(self) -> None:
        launch_mode = str(
            self.launch_mode.currentData()
            or "clean"
        )
        self.settings.setValue(
            "research/launch_mode",
            launch_mode,
        )
        self.controller.start_research(
            clean_launch=(
                launch_mode == "clean"
            )
        )

    def _choose_apk(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите APK",
            "",
            "Android APK (*.apk)",
        )
        if not path:
            return
        if not self._ensure_android_license_consent():
            return
        self.apk_path.setText(path)
        self.package_label.setText(
            "Package: определение…"
        )
        self.start_button.setEnabled(False)
        self.status_package.setText("◌ APK")
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
            "Mobile Research загрузит Android SDK, "
            "Emulator и системный образ автоматически."
        )
        message.setInformativeText(
            "Компоненты загружаются напрямую с "
            "dl.google.com и используются только внутри "
            "Mobile Research. Продолжая, вы подтверждаете "
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
        self.choose_apk_button.setEnabled(
            not busy
            and not self._research_active
        )
        self.prepare_button.setEnabled(
            not busy
            and not self._research_active
        )
        self.start_button.setEnabled(
            not busy
            and not self._research_active
            and bool(
                self.controller.package_name
            )
        )
        self.stop_button.setEnabled(
            self._research_active
        )
        settings_enabled = (
            not busy
            and not self._research_active
        )
        self.reset_android_button.setEnabled(
            settings_enabled
        )
        self.repair_components_button.setEnabled(
            settings_enabled
        )

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
            self._last_gpu_mode = str(
                gpu_mode or ""
            )
            suffix = ""
            if self.android_view.native_active:
                suffix += " • DWM live"
            elif transport_name:
                suffix += f" • {transport_name}"
            if gpu_mode:
                suffix += f" • GPU {gpu_mode}"
            if (
                transport_name
                and str(transport_name).startswith("grpc")
                and not self.android_view.native_active
            ):
                self.android_hint.setText(
                    "Embedded gRPC/MMAP • мышь = touch • "
                    "колесо = swipe • клавиатура = ввод"
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

    def _on_tab_changed(
        self,
        index: int,
    ) -> None:
        self.android_view.set_native_visible(
            index == 0
        )

    def _on_native_display_available(
        self,
        details: dict,
    ) -> None:
        if (
            str(details.get("display_mode", ""))
            != "dwm-live"
        ):
            return
        self.android_hint.setText(
            "Подключение DWM live Android Emulator…"
        )
        attached = self.android_view.attach_native(
            int(details.get("process_id", 0) or 0),
            str(details.get("avd_name", "") or ""),
        )
        if not attached:
            self.controller.set_native_display_attached(
                False
            )

    def _on_native_display_attached(
        self,
        details: dict,
    ) -> None:
        self.controller.set_native_display_attached(
            True
        )
        suffix = " • DWM live"
        if self._last_gpu_mode:
            suffix += (
                f" • GPU {self._last_gpu_mode}"
            )
        self.status_android.setText(
            "● Android готов" + suffix
        )
        self.android_hint.setText(
            "DWM live Android Emulator • "
            "управление через gRPC"
        )
        self.android_view.set_native_visible(
            self.tabs.currentIndex() == 0
        )
        self._append_log(
            "DWM live Android Emulator подключён "
            "без SetParent"
        )

    def _on_native_display_failed(
        self,
        message: str,
    ) -> None:
        self.controller.set_native_display_attached(
            False
        )
        suffix = " • framebuffer fallback"
        if self._last_gpu_mode:
            suffix += (
                f" • GPU {self._last_gpu_mode}"
            )
        self.status_android.setText(
            "● Android готов" + suffix
        )
        self.android_hint.setText(
            "Framebuffer fallback • мышь = touch • "
            "колесо = swipe • клавиатура = ввод"
        )
        self._append_log(message)

    def _on_apk_ready(
        self,
        path: str,
        package: str,
    ) -> None:
        self.apk_path.setText(path)
        self.package_label.setText(
            f"Package: {package}"
        )
        self.status_package.setText(
            "● APK установлен"
        )
        self.status_package.setStyleSheet(
            "color: #238636;"
        )
        self.start_button.setEnabled(
            not self._busy
        )
        self.global_status.setText(
            "Готово к исследованию"
        )

    def _on_research_started(
        self,
        data: dict,
    ) -> None:
        self._research_active = True
        self.session_label.setText(
            "ACTIVE\n"
            f"{data.get('session_id', '')}\n"
            f"{data.get('package', '')}"
        )
        self.global_status.setText(
            "● ИДЁТ ИССЛЕДОВАНИЕ"
        )
        self.global_status.setStyleSheet(
            "color: #d29922; font-weight: 700;"
        )
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.choose_apk_button.setEnabled(False)
        self.status_network.setText(
            "● PCAP записывается"
        )
        self.status_network.setStyleSheet(
            "color: #238636;"
        )

    def _on_research_health(
        self,
        data: dict,
    ) -> None:
        healthy = bool(
            data.get("healthy")
        )
        base = self.session_label.text().split(
            "\nCollectors:"
        )[0]
        self.session_label.setText(
            base
            + "\nCollectors: "
            + (
                "OK"
                if healthy
                else "DEGRADED"
            )
        )

    def _on_research_finished(
        self,
        data: dict,
    ) -> None:
        self._research_active = False
        self._last_archive = str(
            data.get("archive")
            or ""
        )
        status = str(
            data.get("session_status")
            or "unknown"
        )
        issues = data.get(
            "validation_issues"
        )
        self.session_label.setText(
            f"Завершено: {status}\n"
            f"Validation issues: {issues}\n"
            f"{self._last_archive}"
        )
        self.global_status.setText(
            "Исследование завершено: "
            f"{status}"
        )
        self.global_status.setStyleSheet(
            "font-weight: 600;"
        )
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(
            bool(
                self.controller.package_name
            )
        )
        self.choose_apk_button.setEnabled(True)
        self.status_network.setText(
            "● PCAP сохранён"
        )
        self._refresh_results()
        self._refresh_sessions()
        self.tabs.setCurrentIndex(1)
        self.result_details.setPlainText(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )
        )

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
        self.tabs.setCurrentIndex(1)

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
        QMessageBox.critical(
            self,
            "Mobile Research",
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
        self.status_network.setText("○ PCAP")
        self.status_network.setStyleSheet("")

        if self.controller.package_name:
            self.status_package.setText(
                "● APK установлен"
            )
            self.status_package.setStyleSheet(
                "color: #238636;"
            )
        else:
            self.status_package.setText("○ APK")
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
                "Mobile Research",
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
                "Mobile Research",
                "Нельзя переустановить Android-компоненты "
                "во время другой операции.",
            )
            return

        response = QMessageBox.question(
            self,
            "Переустановка Android-компонентов",
            "Удалить управляемые Mobile Research Android SDK, "
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
