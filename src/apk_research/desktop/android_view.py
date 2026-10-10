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

from apk_research.desktop.emulator_grpc import (
    FRAME_ROWS_TOP_DOWN,
    DisplayGeometryTracker,
    map_display_ratio_to_input,
    secondary_touch_point,
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
    touchStateRequested = Signal(
        str,
        str,
        object,
        int,
    )
    keyRequested = Signal(int)
    textRequested = Signal(str)

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
        self._source_image: QImage | None = None
        self._frame_owner = None
        self._display_rect = QRect()
        self._drag_active = False
        self._last_drag_point: tuple[int, int] | None = None
        self._last_touch_points: tuple[
            tuple[int, int],
            ...,
        ] = ()
        self._last_drag_emit_ns = 0
        self._drag_geometry_generation = 0
        self._gesture_mode = "single"
        self._geometry_tracker = DisplayGeometryTracker()
        self._geometry_generation = 0
        self._source_width = 0
        self._source_height = 0
        self._input_width = 0
        self._input_height = 0
        self._rotation = 0

    def save_screenshot(self, path: str) -> bool:
        """Save the original Android frame, not a scaled desktop screenshot."""
        if self._source_image is None or self._source_image.isNull():
            return False
        return bool(self._source_image.copy().save(str(path), "PNG"))

    def set_frame(self, frame) -> None:
        encoding = getattr(frame, "encoding", "")
        row_order = getattr(
            frame,
            "row_order",
            FRAME_ROWS_TOP_DOWN,
        )
        if (
            encoding != "rgba8888"
            or row_order != FRAME_ROWS_TOP_DOWN
        ):
            return

        data = getattr(frame, "data", b"")
        width = int(getattr(frame, "width", 0))
        height = int(getattr(frame, "height", 0))
        expected = width * height * 4
        if (
            width <= 0
            or height <= 0
            or len(data) < expected
        ):
            return

        image = QImage(
            data,
            width,
            height,
            width * 4,
            QImage.Format.Format_RGBA8888,
        )
        rotation = int(
            getattr(frame, "rotation", 0)
            or 0
        )
        input_width = int(
            getattr(frame, "input_width", width)
            or width
        )
        input_height = int(
            getattr(frame, "input_height", height)
            or height
        )
        generation, geometry_changed = (
            self._geometry_tracker.update(
                frame_width=width,
                frame_height=height,
                input_width=input_width,
                input_height=input_height,
                rotation=rotation,
            )
        )
        if geometry_changed and self._drag_active:
            self._cancel_active_gesture()
        self._geometry_generation = generation
        self._frame_owner = frame
        self._rotation = rotation
        self._input_width = input_width
        self._input_height = input_height
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

        painter.drawImage(
            0,
            0,
            image,
        )
        painter.end()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_display_rect()

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
                self._drag_active = True
                self._drag_geometry_generation = (
                    self._geometry_generation
                )
                self._gesture_mode = (
                    self._gesture_mode_for_modifiers(
                        event.modifiers()
                    )
                )
                points = self._touch_points_for(
                    android,
                    self._gesture_mode,
                )
                self._last_drag_point = android
                self._last_touch_points = points
                self._last_drag_emit_ns = (
                    time.monotonic_ns()
                )
                self.setFocus(
                    Qt.FocusReason.MouseFocusReason
                )
                self.touchStateRequested.emit(
                    "down",
                    self._gesture_mode,
                    points,
                    self._drag_geometry_generation,
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

        if (
            self._drag_geometry_generation
            != self._geometry_generation
        ):
            self._cancel_active_gesture()
            event.accept()
            return

        android = self._map_to_android_clamped(
            event.position().toPoint()
        )
        if android is None:
            return

        points = self._touch_points_for(
            android,
            self._gesture_mode,
        )
        now_ns = time.monotonic_ns()
        changed = points != self._last_touch_points
        elapsed_ns = now_ns - self._last_drag_emit_ns
        if (
            changed
            and elapsed_ns >= 12_000_000
        ):
            self._last_drag_point = android
            self._last_touch_points = points
            self._last_drag_emit_ns = now_ns
            self.touchStateRequested.emit(
                "move",
                self._gesture_mode,
                points,
                self._drag_geometry_generation,
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

        if (
            self._drag_geometry_generation
            != self._geometry_generation
        ):
            self._cancel_active_gesture()
            event.accept()
            return

        android = self._map_to_android_clamped(
            event.position().toPoint()
        )
        if android is None:
            android = self._last_drag_point
        if android is not None:
            points = self._touch_points_for(
                android,
                self._gesture_mode,
            )
            if points != self._last_touch_points:
                self.touchStateRequested.emit(
                    "move",
                    self._gesture_mode,
                    points,
                    self._drag_geometry_generation,
                )
            self.touchStateRequested.emit(
                "up",
                self._gesture_mode,
                points,
                self._drag_geometry_generation,
            )
        self._reset_active_gesture()
        event.accept()

    @staticmethod
    def _gesture_mode_for_modifiers(
        modifiers,
    ) -> str:
        ctrl = bool(
            modifiers
            & Qt.KeyboardModifier.ControlModifier
        )
        shift = bool(
            modifiers
            & Qt.KeyboardModifier.ShiftModifier
        )
        if ctrl and shift:
            return "horizontal_tilt"
        if ctrl:
            return "pinch_rotate"
        if shift:
            return "vertical_tilt"
        return "single"

    def _touch_points_for(
        self,
        primary: tuple[int, int],
        mode: str,
    ) -> tuple[tuple[int, int], ...]:
        if mode == "single":
            return (primary,)
        secondary = secondary_touch_point(
            primary[0],
            primary[1],
            self._input_width,
            self._input_height,
            mode,
        )
        return primary, secondary

    def _cancel_active_gesture(self) -> None:
        if (
            self._drag_active
            and self._last_touch_points
        ):
            self.touchStateRequested.emit(
                "cancel",
                self._gesture_mode,
                self._last_touch_points,
                self._drag_geometry_generation,
            )
        self._reset_active_gesture()

    def _reset_active_gesture(self) -> None:
        self._drag_active = False
        self._last_drag_point = None
        self._last_touch_points = ()
        self._drag_geometry_generation = 0
        self._gesture_mode = "single"

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
