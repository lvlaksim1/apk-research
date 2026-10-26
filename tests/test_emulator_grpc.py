from __future__ import annotations

import pytest

from apk_research.desktop.emulator_grpc import (
    FRAME_ROWS_TOP_DOWN,
    DisplayGeometryTracker,
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
    secondary_touch_point,
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


def test_multi_touch_state_uses_one_wire_event(
    monkeypatch,
) -> None:
    client = EmulatorGrpcClient(8554)
    queued = []
    monkeypatch.setattr(
        client,
        "_queue_input_event",
        lambda event: queued.append(event),
    )

    client.touch_points(
        (
            (0, 100, 200, 1),
            (1, 900, 1600, 1),
        )
    )

    touches = queued[0].touch_event.touches
    assert [item.identifier for item in touches] == [0, 1]
    assert [(item.x, item.y) for item in touches] == [
        (100, 200),
        (900, 1600),
    ]
    assert [item.pressure for item in touches] == [1, 1]
    client.close()


def test_display_geometry_generation_changes_only_on_geometry() -> None:
    tracker = DisplayGeometryTracker()

    generation, changed = tracker.update(
        frame_width=405,
        frame_height=720,
        input_width=1080,
        input_height=1920,
        rotation=0,
    )
    assert (generation, changed) == (1, False)

    generation, changed = tracker.update(
        frame_width=405,
        frame_height=720,
        input_width=1080,
        input_height=1920,
        rotation=0,
    )
    assert (generation, changed) == (1, False)

    generation, changed = tracker.update(
        frame_width=720,
        frame_height=405,
        input_width=1920,
        input_height=1080,
        rotation=1,
    )
    assert (generation, changed) == (2, True)


def test_secondary_touch_modes_are_geometry_bounded() -> None:
    assert secondary_touch_point(
        100,
        200,
        1000,
        2000,
        "pinch_rotate",
    ) == (899, 1799)
    assert secondary_touch_point(
        100,
        200,
        1000,
        2000,
        "vertical_tilt",
    ) == (899, 200)
    assert secondary_touch_point(
        100,
        200,
        1000,
        2000,
        "horizontal_tilt",
    ) == (100, 1799)
