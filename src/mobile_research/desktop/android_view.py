from __future__ import annotations

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
    is_reverse_rotation,
    map_display_ratio_to_input,
)
from mobile_research.desktop.native_emulator import (
    NativeEmulatorEmbedder,
    windows_native_embedding_available,
)


class AndroidView(QLabel):
    """Embedded Android framebuffer optimized for continuous 60 Hz painting."""

    tapRequested = Signal(int, int)
    swipeRequested = Signal(
        int,
        int,
        int,
        int,
        int,
    )
    keyRequested = Signal(int)
    textRequested = Signal(str)
    nativeAttached = Signal(dict)
    nativeAttachFailed = Signal(str)

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
        self.setAttribute(
            Qt.WidgetAttribute.WA_NativeWindow,
            True,
        )
        self._native_embedder = (
            NativeEmulatorEmbedder(self)
            if windows_native_embedding_available()
            else None
        )
        if self._native_embedder is not None:
            self._native_embedder.attached.connect(
                self._on_native_attached
            )
            self._native_embedder.failed.connect(
                self._on_native_failed
            )
        self._source_image: QImage | None = None
        self._frame_owner = None
        self._display_rect = QRect()
        self._press_pos: QPoint | None = None
        self._source_width = 0
        self._source_height = 0
        self._input_width = 0
        self._input_height = 0
        self._rotation = 0
        self._bottom_up = False

    @property
    def native_active(self) -> bool:
        return bool(
            self._native_embedder is not None
            and self._native_embedder.active
        )

    def attach_native(
        self,
        process_id: int,
        avd_name: str,
    ) -> bool:
        if self._native_embedder is None:
            return False
        self._source_image = None
        self._frame_owner = None
        self.setText(
            "Подключение DWM live Android Emulator…"
        )
        self.update()
        self._native_embedder.attach(
            process_id,
            avd_name,
        )
        return True

    def detach_native(self) -> None:
        if self._native_embedder is not None:
            self._native_embedder.detach()

    def set_frame(self, frame) -> None:
        if self.native_active:
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
            self._bottom_up = True
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
        if self._native_embedder is not None:
            self._native_embedder.resize_embedded()

    def moveEvent(self, event) -> None:  # noqa: N802
        super().moveEvent(event)
        if self._native_embedder is not None:
            self._native_embedder.resize_embedded()

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:  # noqa: N802
        if (
            event.button()
            == Qt.MouseButton.LeftButton
        ):
            self._press_pos = (
                event.position().toPoint()
            )
            self.setFocus(
                Qt.FocusReason.MouseFocusReason
            )
        super().mousePressEvent(event)

    def mouseReleaseEvent(
        self,
        event: QMouseEvent,
    ) -> None:  # noqa: N802
        if (
            event.button()
            != Qt.MouseButton.LeftButton
            or self._press_pos is None
        ):
            super().mouseReleaseEvent(event)
            return

        start = self._map_to_android(
            self._press_pos
        )
        end = self._map_to_android(
            event.position().toPoint()
        )
        self._press_pos = None
        if start is None or end is None:
            return

        dx = abs(end[0] - start[0])
        dy = abs(end[1] - start[1])
        if dx < 12 and dy < 12:
            self.tapRequested.emit(
                end[0],
                end[1],
            )
        else:
            self.swipeRequested.emit(
                start[0],
                start[1],
                end[0],
                end[1],
                250,
            )

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

    def _on_native_attached(
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
        self.nativeAttached.emit(details)

    def _on_native_failed(
        self,
        message: str,
    ) -> None:
        self.nativeAttachFailed.emit(message)
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
        x_ratio = (
            point.x() - self._display_rect.x()
        ) / self._display_rect.width()
        y_ratio = (
            point.y() - self._display_rect.y()
        ) / self._display_rect.height()
        return map_display_ratio_to_input(
            x_ratio,
            y_ratio,
            self._input_width,
            self._input_height,
            self._rotation,
        )
