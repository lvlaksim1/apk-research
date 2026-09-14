from __future__ import annotations

import time
from dataclasses import dataclass
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


@dataclass(frozen=True)
class LiveFrame:
    encoding: str
    data: bytes
    width: int
    height: int
    input_width: int
    input_height: int
    seq: int = 0
    timestamp_us: int = 0
    transport: str = "grpc"


def _build_messages():
    file_proto = descriptor_pb2.FileDescriptorProto()
    file_proto.name = "mobile_research_emulator_control.proto"
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

    image_format = file_proto.message_type.add()
    image_format.name = "ImageFormat"
    add_field(image_format, "format", 1, descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
    add_field(image_format, "width", 3, descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
    add_field(image_format, "height", 4, descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
    add_field(image_format, "display", 5, descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)

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

    pool = descriptor_pool.DescriptorPool()
    pool.Add(file_proto)

    def message(name: str):
        descriptor = pool.FindMessageTypeByName(
            "android.emulation.control." + name
        )
        return message_factory.GetMessageClass(descriptor)

    return (
        message("ImageFormat"),
        message("Image"),
        message("Touch"),
        message("TouchEvent"),
        message("KeyboardEvent"),
    )


ImageFormat, Image, Touch, TouchEvent, KeyboardEvent = _build_messages()


class EmulatorGrpcClient:
    """Small local gRPC client for live Emulator video and input."""

    RGB888 = 2
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
        self._send_touch = self.channel.unary_unary(
            prefix + "sendTouch",
            request_serializer=lambda message: message.SerializeToString(),
            response_deserializer=empty_pb2.Empty.FromString,
        )
        self._send_key = self.channel.unary_unary(
            prefix + "sendKey",
            request_serializer=lambda message: message.SerializeToString(),
            response_deserializer=empty_pb2.Empty.FromString,
        )

    def wait_ready(self, timeout: float = 8.0) -> None:
        try:
            grpc.channel_ready_future(self.channel).result(timeout=timeout)
        except Exception as exc:
            raise EmulatorGrpcError(
                f"Emulator gRPC did not become ready on port {self.port}"
            ) from exc

    def stream_frames(
        self,
        *,
        width: int = 540,
        height: int = 960,
        timeout: float | None = None,
    ) -> Iterator[LiveFrame]:
        request = ImageFormat(
            format=self.RGB888,
            width=max(1, int(width)),
            height=max(1, int(height)),
            display=0,
        )
        try:
            call = self._stream_screenshot(request, timeout=timeout)
            for reply in call:
                frame_width = int(
                    getattr(reply.format, "width", 0)
                    or getattr(reply, "width", 0)
                )
                frame_height = int(
                    getattr(reply.format, "height", 0)
                    or getattr(reply, "height", 0)
                )
                data = bytes(reply.image)
                if (
                    frame_width <= 0
                    or frame_height <= 0
                    or len(data) != frame_width * frame_height * 3
                ):
                    continue

                if frame_width <= frame_height:
                    input_width = self.device_width
                    input_height = self.device_height
                else:
                    input_width = self.device_height
                    input_height = self.device_width

                yield LiveFrame(
                    encoding="rgb888",
                    data=data,
                    width=frame_width,
                    height=frame_height,
                    input_width=input_width,
                    input_height=input_height,
                    seq=int(reply.seq),
                    timestamp_us=int(reply.timestampUs),
                    transport="grpc",
                )
        except grpc.RpcError as exc:
            raise EmulatorGrpcError(
                f"Emulator screenshot stream failed: {exc.code().name}"
            ) from exc

    def tap(self, x: int, y: int) -> None:
        self._touch(x, y, pressure=1)
        self._touch(x, y, pressure=0)

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 250,
    ) -> None:
        duration = max(1, int(duration_ms)) / 1000.0
        steps = max(4, min(24, int(duration / 0.016)))
        started = time.monotonic()
        for index in range(steps + 1):
            ratio = index / steps
            x = round(x1 + ((x2 - x1) * ratio))
            y = round(y1 + ((y2 - y1) * ratio))
            self._touch(x, y, pressure=1)
            target = started + (duration * ratio)
            remaining = target - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
        self._touch(x2, y2, pressure=0)

    def send_key(self, key: str) -> None:
        request = KeyboardEvent(eventType=self.KEYPRESS, key=str(key))
        try:
            self._send_key(request, timeout=2.0)
        except grpc.RpcError as exc:
            raise EmulatorGrpcError(
                f"Emulator key input failed: {exc.code().name}"
            ) from exc

    def send_text(self, value: str) -> None:
        if not value:
            return
        request = KeyboardEvent(text=str(value))
        try:
            self._send_key(request, timeout=2.0)
        except grpc.RpcError as exc:
            raise EmulatorGrpcError(
                f"Emulator text input failed: {exc.code().name}"
            ) from exc

    def close(self) -> None:
        self.channel.close()

    def _touch(self, x: int, y: int, *, pressure: int) -> None:
        touch = Touch(
            x=max(0, int(x)),
            y=max(0, int(y)),
            identifier=0,
            pressure=max(0, int(pressure)),
            touch_major=1 if pressure else 0,
            touch_minor=1 if pressure else 0,
        )
        request = TouchEvent(display=0)
        request.touches.append(touch)
        try:
            self._send_touch(request, timeout=2.0)
        except grpc.RpcError as exc:
            raise EmulatorGrpcError(
                f"Emulator touch input failed: {exc.code().name}"
            ) from exc
