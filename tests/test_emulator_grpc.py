from __future__ import annotations

from mobile_research.desktop.emulator_grpc import (
    Image,
    ImageFormat,
    KeyboardEvent,
    Touch,
    TouchEvent,
)


def test_minimal_emulator_proto_round_trip() -> None:
    request = ImageFormat(
        format=2,
        width=540,
        height=960,
        display=0,
    )
    restored = ImageFormat.FromString(
        request.SerializeToString()
    )
    assert restored.format == 2
    assert restored.width == 540
    assert restored.height == 960

    reply = Image(
        format=request,
        image=b"abc",
        seq=7,
        timestampUs=123,
    )
    restored_reply = Image.FromString(
        reply.SerializeToString()
    )
    assert restored_reply.format.width == 540
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
