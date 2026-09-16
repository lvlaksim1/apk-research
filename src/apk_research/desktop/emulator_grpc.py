from __future__ import annotations

import mmap
import queue
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import grpc
from google.protobuf import (
    descriptor_pb2,
    descriptor_pool,
    empty_pb2,
    message_factory,
)


_SERVICE = "android.emulation.control.EmulatorController"


class EmulatorGrpcError(RuntimeError):
    """Raised when the low-latency Emulator control plane is unavailable."""


FRAME_ROWS_TOP_DOWN = "top-down"
def is_reverse_rotation(rotation: int) -> bool:
    return int(rotation) in {2, 3}


def map_display_ratio_to_input(
    x_ratio: float,
    y_ratio: float,
    input_width: int,
    input_height: int,
    rotation: int,
) -> tuple[int, int]:
    x_ratio = min(1.0, max(0.0, x_ratio))
    y_ratio = min(1.0, max(0.0, y_ratio))
    if is_reverse_rotation(rotation):
        x_ratio = 1.0 - x_ratio
        y_ratio = 1.0 - y_ratio
    x = min(
        input_width - 1,
        max(0, int(x_ratio * input_width)),
    )
    y = min(
        input_height - 1,
        max(0, int(y_ratio * input_height)),
    )
    return x, y


@dataclass(frozen=True)
class LiveFrame:
    encoding: str
    data: object
    width: int
    height: int
    input_width: int
    input_height: int
    rotation: int = 0
    row_order: str = FRAME_ROWS_TOP_DOWN
    seq: int = 0
    timestamp_us: int = 0
    transport: str = "grpc-mmap"
    owner: object | None = None


@dataclass
class _MappedFrameBuffer:
    path: Path
    mapping: mmap.mmap

    def close(self) -> None:
        try:
            self.mapping.close()
        except (BufferError, ValueError):
            return
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


def _build_messages():
    file_proto = descriptor_pb2.FileDescriptorProto()
    file_proto.name = "apk_research_emulator_control.proto"
    file_proto.package = "android.emulation.control"
    file_proto.syntax = "proto3"

    def add_field(
        message,
        name: str,
        number: int,
        field_type: int,
        *,
        type_name: str = "",
        repeated: bool = False,
    ) -> None:
        field = message.field.add()
        field.name = name
        field.number = number
        field.type = field_type
        field.label = (
            descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
            if repeated
            else descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
        )
        if type_name:
            field.type_name = type_name

    rotation = file_proto.message_type.add()
    rotation.name = "Rotation"
    add_field(rotation, "rotation", 1, descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
    add_field(rotation, "xAxis", 2, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE)
    add_field(rotation, "yAxis", 3, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE)
    add_field(rotation, "zAxis", 4, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE)

    transport = file_proto.message_type.add()
    transport.name = "ImageTransport"
    add_field(transport, "channel", 1, descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
    add_field(transport, "handle", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)

    image_format = file_proto.message_type.add()
    image_format.name = "ImageFormat"
    add_field(image_format, "format", 1, descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
    add_field(
        image_format,
        "rotation",
        2,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".android.emulation.control.Rotation",
    )
    add_field(image_format, "width", 3, descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
    add_field(image_format, "height", 4, descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
    add_field(image_format, "display", 5, descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
    add_field(
        image_format,
        "transport",
        6,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".android.emulation.control.ImageTransport",
    )

    image = file_proto.message_type.add()
    image.name = "Image"
    add_field(
        image,
        "format",
        1,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".android.emulation.control.ImageFormat",
    )
    add_field(image, "width", 2, descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
    add_field(image, "height", 3, descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
    add_field(image, "image", 4, descriptor_pb2.FieldDescriptorProto.TYPE_BYTES)
    add_field(image, "seq", 5, descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
    add_field(image, "timestampUs", 6, descriptor_pb2.FieldDescriptorProto.TYPE_UINT64)

    touch = file_proto.message_type.add()
    touch.name = "Touch"
    for name, number in (
        ("x", 1),
        ("y", 2),
        ("identifier", 3),
        ("pressure", 4),
        ("touch_major", 5),
        ("touch_minor", 6),
        ("expiration", 7),
        ("orientation", 8),
    ):
        add_field(touch, name, number, descriptor_pb2.FieldDescriptorProto.TYPE_INT32)

    touch_event = file_proto.message_type.add()
    touch_event.name = "TouchEvent"
    add_field(
        touch_event,
        "touches",
        1,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".android.emulation.control.Touch",
        repeated=True,
    )
    add_field(touch_event, "display", 2, descriptor_pb2.FieldDescriptorProto.TYPE_INT32)

    keyboard = file_proto.message_type.add()
    keyboard.name = "KeyboardEvent"
    add_field(keyboard, "codeType", 1, descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
    add_field(keyboard, "eventType", 2, descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
    add_field(keyboard, "keyCode", 3, descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
    add_field(keyboard, "key", 4, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    add_field(keyboard, "text", 5, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)

    input_event = file_proto.message_type.add()
    input_event.name = "InputEvent"
    add_field(
        input_event,
        "key_event",
        1,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".android.emulation.control.KeyboardEvent",
    )
    add_field(
        input_event,
        "touch_event",
        2,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".android.emulation.control.TouchEvent",
    )

    pool = descriptor_pool.DescriptorPool()
    pool.Add(file_proto)

    def message(name: str):
        descriptor = pool.FindMessageTypeByName(
            "android.emulation.control." + name
        )
        return message_factory.GetMessageClass(descriptor)

    return (
        message("Rotation"),
        message("ImageTransport"),
        message("ImageFormat"),
        message("Image"),
        message("Touch"),
        message("TouchEvent"),
        message("KeyboardEvent"),
        message("InputEvent"),
    )


(
    Rotation,
    ImageTransport,
    ImageFormat,
    Image,
    Touch,
    TouchEvent,
    KeyboardEvent,
    InputEvent,
) = _build_messages()


class EmulatorGrpcClient:
    """Local low-latency display/input client for Android Emulator."""

    RGBA8888 = 1
    MMAP = 1
    KEYPRESS = 2

    def __init__(
        self,
        port: int,
        *,
        device_width: int = 1080,
        device_height: int = 1920,
    ) -> None:
        self.port = int(port)
        self.device_width = int(device_width)
        self.device_height = int(device_height)
        if self.port <= 0:
            raise ValueError("gRPC port must be positive")

        self.channel = grpc.insecure_channel(
            f"127.0.0.1:{self.port}",
            options=(
                ("grpc.max_receive_message_length", 32 * 1024 * 1024),
                ("grpc.max_send_message_length", 4 * 1024 * 1024),
            ),
        )
        prefix = f"/{_SERVICE}/"
        self._stream_screenshot = self.channel.unary_stream(
            prefix + "streamScreenshot",
            request_serializer=lambda message: message.SerializeToString(),
            response_deserializer=Image.FromString,
        )
        self._stream_input = self.channel.stream_unary(
            prefix + "streamInputEvent",
            request_serializer=lambda message: message.SerializeToString(),
            response_deserializer=empty_pb2.Empty.FromString,
        )
        self._input_queue: queue.Queue[object | None] = queue.Queue()
        self._input_thread: threading.Thread | None = None
        self._input_stream_error = ""
        self._mapped_buffers: list[_MappedFrameBuffer] = []
        self.frame_transport = "grpc-mmap"
        self.frame_transport_error = ""

    def wait_ready(self, timeout: float = 8.0) -> None:
        try:
            grpc.channel_ready_future(self.channel).result(timeout=timeout)
        except Exception as exc:
            raise EmulatorGrpcError(
                f"Emulator gRPC did not become ready on port {self.port}"
            ) from exc
        self._start_input_stream()

    def stream_frames(
        self,
        *,
        width: int = 405,
        height: int = 720,
        timeout: float | None = None,
    ) -> Iterator[LiveFrame]:
        """Yield frames only through the required gRPC/MMAP transport."""

        try:
            yield from self._stream_frames_mmap(
                width=width,
                height=height,
                timeout=timeout,
            )
        except Exception as exc:
            detail = str(exc) or exc.__class__.__name__
            self.frame_transport_error = detail
            raise EmulatorGrpcError(
                "Emulator gRPC/MMAP framebuffer failed: "
                + detail
            ) from exc

    def touch_down(self, x: int, y: int) -> None:
        self._send_touch_state(
            x,
            y,
            pressure=1,
        )

    def touch_move(self, x: int, y: int) -> None:
        self._send_touch_state(
            x,
            y,
            pressure=1,
        )

    def touch_up(self, x: int, y: int) -> None:
        self._send_touch_state(
            x,
            y,
            pressure=0,
        )

    def _send_touch_state(
        self,
        x: int,
        y: int,
        *,
        pressure: int,
    ) -> None:
        event = self._touch_event(
            x,
            y,
            pressure=pressure,
        )
        self._queue_input_event(
            self._wrap_touch(event)
        )

    def tap(self, x: int, y: int) -> None:
        down = self._touch_event(x, y, pressure=1)
        up = self._touch_event(x, y, pressure=0)
        self._queue_input_event(
            self._wrap_touch(down)
        )
        self._queue_input_event(
            self._wrap_touch(up)
        )

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 250,
    ) -> None:
        duration = max(1, int(duration_ms)) / 1000.0
        steps = max(4, min(32, int(duration / 0.012)))
        started = time.perf_counter()
        for index in range(steps + 1):
            ratio = index / steps
            x = round(x1 + ((x2 - x1) * ratio))
            y = round(y1 + ((y2 - y1) * ratio))
            event = self._touch_event(
                x,
                y,
                pressure=1,
            )
            self._queue_input_event(
                self._wrap_touch(event)
            )
            target = started + (duration * ratio)
            remaining = target - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
        up = self._touch_event(
            x2,
            y2,
            pressure=0,
        )
        self._queue_input_event(
            self._wrap_touch(up)
        )

    def send_key(self, key: str) -> None:
        key_event = KeyboardEvent(
            eventType=self.KEYPRESS,
            key=str(key),
        )
        self._queue_input_event(
            self._wrap_key(key_event)
        )

    def send_text(self, value: str) -> None:
        if not value:
            return
        key_event = KeyboardEvent(text=str(value))
        self._queue_input_event(
            self._wrap_key(key_event)
        )

    def close(self) -> None:
        try:
            self._input_queue.put_nowait(None)
        except Exception:
            pass
        self.channel.close()
        if self._input_thread is not None:
            self._input_thread.join(timeout=0.5)
        for mapped in self._mapped_buffers:
            mapped.close()
        self._mapped_buffers.clear()

    def _stream_frames_mmap(
        self,
        *,
        width: int,
        height: int,
        timeout: float | None,
    ) -> Iterator[LiveFrame]:
        max_size = max(1, int(width)) * max(1, int(height)) * 4 + 4096
        temp = tempfile.NamedTemporaryFile(
            prefix="apk-research-frame-",
            suffix=".rgba",
            delete=False,
        )
        path = Path(temp.name)
        try:
            temp.truncate(max_size)
            temp.flush()
        finally:
            temp.close()

        request = ImageFormat(
            format=self.RGBA8888,
            width=max(1, int(width)),
            height=max(1, int(height)),
            display=0,
        )
        request.transport.CopyFrom(
            ImageTransport(
                channel=self.MMAP,
                handle=path.resolve().as_uri(),
            )
        )
        call = self._stream_screenshot(
            request,
            timeout=timeout,
        )

        handle = path.open("r+b")
        try:
            mapping = mmap.mmap(
                handle.fileno(),
                0,
                access=mmap.ACCESS_READ,
            )
        finally:
            handle.close()

        owner = _MappedFrameBuffer(
            path=path,
            mapping=mapping,
        )
        self._mapped_buffers.append(owner)

        for reply in call:
            frame = self._frame_from_reply(
                reply,
                data=memoryview(mapping),
                transport="grpc-mmap",
                owner=owner,
            )
            if frame is None:
                continue
            self.frame_transport = "grpc-mmap"
            yield frame

    def _frame_from_reply(
        self,
        reply,
        *,
        data: object,
        transport: str,
        owner: object | None = None,
    ) -> LiveFrame | None:
        frame_width = int(
            getattr(reply.format, "width", 0)
            or getattr(reply, "width", 0)
        )
        frame_height = int(
            getattr(reply.format, "height", 0)
            or getattr(reply, "height", 0)
        )
        frame_size = frame_width * frame_height * 4
        if (
            frame_width <= 0
            or frame_height <= 0
            or len(data) < frame_size
        ):
            return None

        if isinstance(data, memoryview):
            frame_data = data[:frame_size]
        else:
            frame_data = data

        if frame_width <= frame_height:
            input_width = self.device_width
            input_height = self.device_height
        else:
            input_width = self.device_height
            input_height = self.device_width

        rotation = int(
            getattr(
                getattr(
                    reply.format,
                    "rotation",
                    None,
                ),
                "rotation",
                0,
            )
        )
        return LiveFrame(
            encoding="rgba8888",
            data=frame_data,
            width=frame_width,
            height=frame_height,
            input_width=input_width,
            input_height=input_height,
            rotation=rotation,
            row_order=FRAME_ROWS_TOP_DOWN,
            seq=int(reply.seq),
            timestamp_us=int(reply.timestampUs),
            transport=transport,
            owner=owner,
        )

    def _start_input_stream(self) -> None:
        if (
            self._input_thread is not None
            and self._input_thread.is_alive()
        ):
            return
        self._input_stream_error = ""
        self._input_thread = threading.Thread(
            target=self._input_stream_worker,
            daemon=True,
            name="apk-research-emulator-input",
        )
        self._input_thread.start()

    def _input_stream_worker(self) -> None:
        def requests():
            while True:
                item = self._input_queue.get()
                if item is None:
                    return
                yield item

        try:
            self._stream_input(requests())
        except grpc.RpcError as exc:
            self._input_stream_error = exc.code().name
        except Exception as exc:
            self._input_stream_error = (
                str(exc) or exc.__class__.__name__
            )

    def _input_stream_available(self) -> bool:
        return bool(
            self._input_thread is not None
            and self._input_thread.is_alive()
            and not self._input_stream_error
        )

    @property
    def input_stream_error(self) -> str:
        return self._input_stream_error

    def _require_input_stream(self) -> None:
        if self._input_stream_available():
            return
        detail = (
            self._input_stream_error
            or "streamInputEvent is not active"
        )
        raise EmulatorGrpcError(
            "Required Emulator gRPC streamInputEvent failed: "
            + detail
        )

    def _queue_input_event(self, event) -> None:
        self._require_input_stream()
        self._input_queue.put(event)

    @staticmethod
    def _wrap_touch(event):
        wrapped = InputEvent()
        wrapped.touch_event.CopyFrom(event)
        return wrapped

    @staticmethod
    def _wrap_key(event):
        wrapped = InputEvent()
        wrapped.key_event.CopyFrom(event)
        return wrapped

    @staticmethod
    def _touch_event(
        x: int,
        y: int,
        *,
        pressure: int,
    ):
        touch = Touch(
            x=max(0, int(x)),
            y=max(0, int(y)),
            identifier=0,
            pressure=max(0, int(pressure)),
            touch_major=1 if pressure else 0,
            touch_minor=1 if pressure else 0,
        )
        event = TouchEvent(display=0)
        event.touches.append(touch)
        return event
