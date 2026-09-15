from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QWheelEvent,
)
from PySide6.QtWidgets import QLabel

from mobile_research.desktop.emulator_grpc import (
    FRAME_ROWS_TOP_DOWN,
    frame_rows_are_bottom_up,
    is_reverse_rotation,
    map_display_ratio_to_input,
)
from mobile_research.desktop.dwm_emulator import (
    DwmEmulatorPresenter,
    windows_dwm_available,
)


class AndroidView(QLabel):
    """Embedded Android framebuffer optimized for continuous 60 Hz painting."""

    swipeRequested = Signal(
        int,
        int,
        int,
        int,
        int,
    )
    touchDownRequested = Signal(int, int)
    touchMoveRequested = Signal(int, int)
    touchUpRequested = Signal(int, int)
    keyRequested = Signal(int)
    textRequested = Signal(str)
    dwmAttached = Signal(dict)
    dwmAttachFailed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.setMinimumSize(360, 640)
        self.setStyleSheet(
            "QLabel { background: #111315; "
            "color: #8a9096; border: 1px solid #2c3136; "
            "border-radius: 8px; }"
        )
        self.setText(
            "Android\n\n"
            "Выберите APK — среда запустится автоматически"
        )
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )
        self._dwm_presenter = (
            DwmEmulatorPresenter(self)
            if windows_dwm_available()
            else None
        )
        if self._dwm_presenter is not None:
            self._dwm_presenter.attached.connect(
                self._on_dwm_attached
            )
            self._dwm_presenter.failed.connect(
                self._on_dwm_failed
            )
        self._source_image: QImage | None = None
        self._frame_owner = None
        self._display_rect = QRect()
        self._press_pos: QPoint | None = None
        self._drag_active = False
        self._last_drag_point: tuple[int, int] | None = None
        self._last_drag_emit_ns = 0
        self._source_width = 0
        self._source_height = 0
        self._input_width = 0
        self._input_height = 0
        self._rotation = 0
        self._bottom_up = False

    @property
    def dwm_active(self) -> bool:
        return bool(
            self._dwm_presenter is not None
            and self._dwm_presenter.active
        )

    def attach_dwm(
        self,
        process_id: int,
        avd_name: str,
    ) -> bool:
        if self._dwm_presenter is None:
            return False
        self._source_image = None
        self._frame_owner = None
        self.setText(
            "Подключение DWM live Android Emulator…"
        )
        self.update()
        self._dwm_presenter.attach(
            process_id,
            avd_name,
        )
        return True

    def detach_dwm(self) -> None:
        if self._dwm_presenter is not None:
            self._dwm_presenter.detach()

    def set_dwm_visible(
        self,
        visible: bool,
    ) -> None:
        if self._dwm_presenter is not None:
            self._dwm_presenter.set_presentation_visible(
                visible
            )

    def set_frame(self, frame) -> None:
        if self.dwm_active:
            return
        encoding = getattr(
            frame,
            "encoding",
            "png",
        )
        data = getattr(
            frame,
            "data",
            frame if isinstance(frame, bytes) else b"",
        )

        if encoding in {"rgba8888", "rgb888"}:
            width = int(getattr(frame, "width", 0))
            height = int(getattr(frame, "height", 0))
            bytes_per_pixel = (
                4
                if encoding == "rgba8888"
                else 3
            )
            expected = width * height * bytes_per_pixel
            if (
                width <= 0
                or height <= 0
                or len(data) < expected
            ):
                return
            image_format = (
                QImage.Format.Format_RGBA8888
                if encoding == "rgba8888"
                else QImage.Format.Format_RGB888
            )
            image = QImage(
                data,
                width,
                height,
                width * bytes_per_pixel,
                image_format,
            )
            self._frame_owner = frame
            self._bottom_up = frame_rows_are_bottom_up(
                getattr(
                    frame,
                    "row_order",
                    FRAME_ROWS_TOP_DOWN,
                )
            )
            self._rotation = int(
                getattr(frame, "rotation", 0)
                or 0
            )
            self._input_width = int(
                getattr(frame, "input_width", width)
                or width
            )
            self._input_height = int(
                getattr(frame, "input_height", height)
                or height
            )
        else:
            image = QImage()
            if (
                not data
                or not image.loadFromData(
                    data,
                    "PNG",
                )
            ):
                return
            self._frame_owner = frame
            self._bottom_up = False
            self._rotation = 0
            self._input_width = image.width()
            self._input_height = image.height()

        self._source_image = image
        self._source_width = image.width()
        self._source_height = image.height()
        self.setText("")
        self._update_display_rect()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        image = self._source_image
        if image is None:
            return
        self._update_display_rect()
        target = self._display_rect
        if (
            target.width() <= 0
            or target.height() <= 0
        ):
            return

        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform,
            False,
        )
        painter.setClipRect(target)
        painter.translate(
            target.x(),
            target.y(),
        )
        painter.scale(
            target.width() / self._source_width,
            target.height() / self._source_height,
        )

        if self._bottom_up:
            if is_reverse_rotation(
                self._rotation
            ):
                painter.translate(
                    self._source_width,
                    0,
                )
                painter.scale(-1.0, 1.0)
            else:
                painter.translate(
                    0,
                    self._source_height,
                )
                painter.scale(1.0, -1.0)

        painter.drawImage(
            0,
            0,
            image,
        )
        painter.end()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_display_rect()
        if self._dwm_presenter is not None:
            self._dwm_presenter.refresh_presentation()

    def moveEvent(self, event) -> None:  # noqa: N802
        super().moveEvent(event)
        if self._dwm_presenter is not None:
            self._dwm_presenter.refresh_presentation()

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:  # noqa: N802
        if (
            event.button()
            == Qt.MouseButton.LeftButton
        ):
            point = event.position().toPoint()
            android = self._map_to_android(point)
            if android is not None:
                self._press_pos = point
                self._drag_active = True
                self._last_drag_point = android
                self._last_drag_emit_ns = (
                    time.monotonic_ns()
                )
                self.setFocus(
                    Qt.FocusReason.MouseFocusReason
                )
                self.touchDownRequested.emit(
                    android[0],
                    android[1],
                )
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(
        self,
        event: QMouseEvent,
    ) -> None:  # noqa: N802
        if not self._drag_active:
            super().mouseMoveEvent(event)
            return

        android = self._map_to_android_clamped(
            event.position().toPoint()
        )
        if android is None:
            return

        now_ns = time.monotonic_ns()
        changed = android != self._last_drag_point
        elapsed_ns = now_ns - self._last_drag_emit_ns
        if (
            changed
            and elapsed_ns >= 12_000_000
        ):
            self._last_drag_point = android
            self._last_drag_emit_ns = now_ns
            self.touchMoveRequested.emit(
                android[0],
                android[1],
            )
        event.accept()

    def mouseReleaseEvent(
        self,
        event: QMouseEvent,
    ) -> None:  # noqa: N802
        if (
            event.button()
            != Qt.MouseButton.LeftButton
            or not self._drag_active
        ):
            super().mouseReleaseEvent(event)
            return

        android = self._map_to_android_clamped(
            event.position().toPoint()
        )
        self._press_pos = None
        self._drag_active = False
        if android is None:
            android = self._last_drag_point
        if android is not None:
            if android != self._last_drag_point:
                self.touchMoveRequested.emit(
                    android[0],
                    android[1],
                )
            self.touchUpRequested.emit(
                android[0],
                android[1],
            )
        self._last_drag_point = None
        event.accept()

    def wheelEvent(
        self,
        event: QWheelEvent,
    ) -> None:  # noqa: N802
        center = self._map_to_android(
            event.position().toPoint()
        )
        if center is None:
            return
        direction = (
            -1
            if event.angleDelta().y() > 0
            else 1
        )
        distance = max(
            180,
            self._input_height // 4,
        )
        y2 = max(
            0,
            min(
                self._input_height - 1,
                center[1] + direction * distance,
            ),
        )
        self.swipeRequested.emit(
            center[0],
            center[1],
            center[0],
            y2,
            220,
        )

    def keyPressEvent(
        self,
        event: QKeyEvent,
    ) -> None:  # noqa: N802
        key_map = {
            Qt.Key.Key_Back: 4,
            Qt.Key.Key_Escape: 4,
            Qt.Key.Key_Home: 3,
            Qt.Key.Key_Return: 66,
            Qt.Key.Key_Enter: 66,
            Qt.Key.Key_Backspace: 67,
            Qt.Key.Key_Delete: 67,
            Qt.Key.Key_Tab: 61,
            Qt.Key.Key_Up: 19,
            Qt.Key.Key_Down: 20,
            Qt.Key.Key_Left: 21,
            Qt.Key.Key_Right: 22,
        }
        if event.key() in key_map:
            self.keyRequested.emit(
                key_map[event.key()]
            )
            event.accept()
            return
        text = event.text()
        if text and text.isprintable():
            self.textRequested.emit(text)
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_dwm_attached(
        self,
        details: dict,
    ) -> None:
        self._source_image = None
        self._frame_owner = None
        self._source_width = int(
            details.get("source_width", 9) or 9
        )
        self._source_height = int(
            details.get("source_height", 16) or 16
        )
        self._input_width = int(
            details.get("input_width", 1080) or 1080
        )
        self._input_height = int(
            details.get("input_height", 1920) or 1920
        )
        self._rotation = 0
        self._bottom_up = False
        self._update_display_rect()
        self.setText("")
        self.dwmAttached.emit(details)

    def _on_dwm_failed(
        self,
        message: str,
    ) -> None:
        self.dwmAttachFailed.emit(message)
        if self._source_image is None:
            self.setText(
                "DWM live недоступен\n"
                "Переход на framebuffer fallback…"
            )

    def _update_display_rect(self) -> None:
        if (
            self._source_width <= 0
            or self._source_height <= 0
        ):
            self._display_rect = QRect()
            return
        available = self.contentsRect()
        scale = min(
            available.width()
            / self._source_width,
            available.height()
            / self._source_height,
        )
        width = max(
            1,
            int(self._source_width * scale),
        )
        height = max(
            1,
            int(self._source_height * scale),
        )
        x = (
            available.x()
            + (available.width() - width) // 2
        )
        y = (
            available.y()
            + (available.height() - height) // 2
        )
        self._display_rect = QRect(
            x,
            y,
            width,
            height,
        )

    def _map_to_android(
        self,
        point: QPoint,
    ) -> tuple[int, int] | None:
        if (
            self._input_width <= 0
            or self._input_height <= 0
            or not self._display_rect.contains(point)
        ):
            return None
        return self._map_to_android_clamped(
            point
        )

    def _map_to_android_clamped(
        self,
        point: QPoint,
    ) -> tuple[int, int] | None:
        if (
            self._input_width <= 0
            or self._input_height <= 0
            or self._display_rect.width() <= 0
            or self._display_rect.height() <= 0
        ):
            return None
        x = min(
            self._display_rect.right(),
            max(
                self._display_rect.left(),
                point.x(),
            ),
        )
        y = min(
            self._display_rect.bottom(),
            max(
                self._display_rect.top(),
                point.y(),
            ),
        )
        x_ratio = (
            x - self._display_rect.x()
        ) / self._display_rect.width()
        y_ratio = (
            y - self._display_rect.y()
        ) / self._display_rect.height()
        return map_display_ratio_to_input(
            x_ratio,
            y_ratio,
            self._input_width,
            self._input_height,
            self._rotation,
        )
