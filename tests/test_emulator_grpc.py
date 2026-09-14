from __future__ import annotations

from mobile_research.desktop.emulator_grpc import (
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
