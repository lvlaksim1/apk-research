from __future__ import annotations

import pytest

from mobile_research.desktop.emulator_grpc import (
    FRAME_ROWS_TOP_DOWN,
    EmulatorGrpcClient,
    EmulatorGrpcError,
    Image,
    ImageFormat,
    ImageTransport,
    InputEvent,
    KeyboardEvent,
    Rotation,
    Touch,
    TouchEvent,
    is_reverse_rotation,
    map_display_ratio_to_input,
)


def test_minimal_emulator_proto_round_trip() -> None:
    request = ImageFormat(
        format=1,
        width=405,
        height=720,
        display=0,
    )
    request.rotation.CopyFrom(
        Rotation(rotation=2)
    )
    restored = ImageFormat.FromString(
        request.SerializeToString()
    )
    assert restored.format == 1
    assert restored.width == 405
    assert restored.height == 720
    assert restored.rotation.rotation == 2
    assert restored.display == 0

    reply = Image(
        format=request,
        image=b"abc",
        seq=7,
        timestampUs=123,
    )
    restored_reply = Image.FromString(
        reply.SerializeToString()
    )
    assert restored_reply.format.width == 405
    assert restored_reply.image == b"abc"
    assert restored_reply.seq == 7


def test_touch_and_keyboard_wire_messages() -> None:
    event = TouchEvent(display=0)
    event.touches.append(
        Touch(
            x=100,
            y=200,
            identifier=0,
            pressure=1,
        )
    )
    restored = TouchEvent.FromString(
        event.SerializeToString()
    )
    assert restored.touches[0].x == 100
    assert restored.touches[0].pressure == 1

    key = KeyboardEvent(
        eventType=2,
        key="GoBack",
    )
    restored_key = KeyboardEvent.FromString(
        key.SerializeToString()
    )
    assert restored_key.key == "GoBack"
    assert restored_key.eventType == 2


def test_mmap_transport_wire_format() -> None:
    request = ImageFormat(
        format=1,
        width=405,
        height=720,
        display=0,
    )
    request.transport.CopyFrom(
        ImageTransport(
            channel=1,
            handle="file:///tmp/frame.rgba",
        )
    )
    restored = ImageFormat.FromString(
        request.SerializeToString()
    )
    assert restored.transport.channel == 1
    assert restored.transport.handle.endswith(
        "frame.rgba"
    )


def test_stream_input_event_wire_format() -> None:
    touch = TouchEvent(display=0)
    touch.touches.append(
        Touch(
            x=12,
            y=34,
            identifier=0,
            pressure=1,
        )
    )
    wrapped = InputEvent()
    wrapped.touch_event.CopyFrom(touch)
    restored = InputEvent.FromString(
        wrapped.SerializeToString()
    )
    assert restored.touch_event.touches[0].x == 12
    assert restored.touch_event.touches[0].y == 34


def test_reverse_rotation_mapping_is_normalized() -> None:
    assert is_reverse_rotation(2)
    assert is_reverse_rotation(3)
    assert not is_reverse_rotation(0)
    assert not is_reverse_rotation(1)
    assert map_display_ratio_to_input(
        0.25, 0.20, 1000, 2000, 0
    ) == (250, 400)
    assert map_display_ratio_to_input(
        0.25, 0.20, 1000, 2000, 2
    ) == (750, 1600)


def test_stream_screenshot_rows_are_top_down() -> None:
    client = EmulatorGrpcClient(8554)
    request = ImageFormat(
        format=1,
        width=2,
        height=3,
        display=0,
    )
    reply = Image(
        format=request,
        image=bytes(range(24)),
        seq=9,
        timestampUs=456,
    )
    frame = client._frame_from_reply(
        reply,
        data=reply.image,
        transport="grpc-mmap",
    )
    assert frame is not None
    assert frame.row_order == FRAME_ROWS_TOP_DOWN
    assert frame.transport == "grpc-mmap"
    client.close()


def test_continuous_touch_states_use_stream_queue(
    monkeypatch,
) -> None:
    client = EmulatorGrpcClient(8554)
    queued = []

    monkeypatch.setattr(
        client,
        "_queue_input_event",
        lambda event: queued.append(event),
    )

    client.touch_down(10, 20)
    client.touch_move(30, 40)
    client.touch_up(50, 60)

    pressures = [
        item.touch_event.touches[0].pressure
        for item in queued
    ]
    coords = [
        (
            item.touch_event.touches[0].x,
            item.touch_event.touches[0].y,
        )
        for item in queued
    ]
    assert pressures == [1, 1, 0]
    assert coords == [
        (10, 20),
        (30, 40),
        (50, 60),
    ]
    client.close()


def test_frame_stream_fails_when_mmap_fails(
    monkeypatch,
) -> None:
    client = EmulatorGrpcClient(8554)

    def fail_mmap(**kwargs):
        raise RuntimeError("mmap unavailable")
        yield  # pragma: no cover

    monkeypatch.setattr(
        client,
        "_stream_frames_mmap",
        fail_mmap,
    )

    with pytest.raises(
        EmulatorGrpcError,
        match="gRPC/MMAP framebuffer failed",
    ):
        next(client.stream_frames())

    assert client.frame_transport == "grpc-mmap"
    assert "mmap unavailable" in client.frame_transport_error
    client.close()


def test_input_fails_when_stream_input_event_is_unavailable(
    monkeypatch,
) -> None:
    client = EmulatorGrpcClient(8554)
    client._input_stream_error = "UNAVAILABLE"
    monkeypatch.setattr(
        client,
        "_input_stream_available",
        lambda: False,
    )

    with pytest.raises(
        EmulatorGrpcError,
        match="streamInputEvent",
    ):
        client.touch_down(10, 20)

    client.close()
