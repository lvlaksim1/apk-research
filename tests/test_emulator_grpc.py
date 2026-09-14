from __future__ import annotations

from mobile_research.desktop.emulator_grpc import (
    Image,
    ImageFormat,
    KeyboardEvent,
    Rotation,
    Touch,
    TouchEvent,
)


def test_minimal_emulator_proto_round_trip() -> None:
    request = ImageFormat(
        format=1,
        width=360,
        height=640,
        display=0,
    )
    request.rotation.CopyFrom(
        Rotation(rotation=2)
    )
    restored = ImageFormat.FromString(
        request.SerializeToString()
    )
    assert restored.format == 1
    assert restored.width == 360
    assert restored.height == 640
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
    assert restored_reply.format.width == 360
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
