"""Compact, keyboard-accessible emulator controls.

Buttons invoke actual Android or desktop operations. User-visible panel
contains no recorders or technical diagnostics, and introduces no new tabs.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QToolButton, QVBoxLayout, QWidget, QFrame


PRIMARY_ACTIONS = (
    ("back", "◀", "Назад (Alt+←)"),
    ("home", "⌂", "Домой"),
    ("recent", "▣", "Недавние приложения"),
    ("volume_up", "＋", "Увеличить громкость"),
    ("volume_down", "－", "Уменьшить громкость"),
    ("rotate", "⟳", "Повернуть экран"),
    ("screenshot", "▧", "Сохранить снимок Android"),
    ("fullscreen", "⛶", "Полноэкранный режим (F11)"),
    ("restart", "↻", "Перезапустить Android"),
    ("install", "↓", "Установить APK/XAPK"),
)
SECONDARY_ACTIONS = (
    ("send_file", "⇢", "Передать файл в Android"),
    ("get_file", "⇠", "Получить файл из Android"),
    ("location", "◎", "Задать геолокацию"),
    ("stop_app", "■", "Остановить приложение"),
    ("app_settings", "⚙", "Настройки приложения"),
    ("clear_data", "⌫", "Очистить данные приложения"),
)


class EmulatorToolPanel(QWidget):
    invoked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("EmulatorTools")
        self.setFixedWidth(54)
        self.buttons: dict[str, QToolButton] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 4, 3, 4)
        layout.setSpacing(5)
        for action, glyph, label in PRIMARY_ACTIONS:
            self._add_button(layout, action, glyph, label)
        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)
        for action, glyph, label in SECONDARY_ACTIONS:
            self._add_button(layout, action, glyph, label)
        layout.addStretch(1)

    def _add_button(self, layout, action, glyph, label):
        button = QToolButton(self)
        button.setText(glyph)
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.setFixedSize(43, 36)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.clicked.connect(
            lambda _checked=False, key=action: self.invoked.emit(key)
        )
        button.setStyleSheet(
            "QToolButton {font-size: 19px; border-radius: 6px; "
            "background: #30333a; color: #e3e8ee;}"
            "QToolButton:hover {background: #464d59;}"
            "QToolButton:pressed {background: #54617a;}"
            "QToolButton:disabled {color: #65686e;}"
        )
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.buttons[action] = button

    def set_ready(self, ready: bool, *, recording: bool, busy: bool) -> None:
        for key, button in self.buttons.items():
            # Recording occupies the session worker for its entire lifetime;
            # navigation, screenshot and rotation must remain responsive.
            button.setEnabled(ready and (not busy or recording))
            if key in {"restart", "clear_data", "send_file", "get_file",
                       "location", "stop_app", "app_settings"} and recording:
                button.setEnabled(False)
