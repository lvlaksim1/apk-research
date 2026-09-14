from __future__ import annotations

from mobile_research.desktop.emulator_grpc import (
    is_reverse_rotation,
    map_display_ratio_to_input,
)


def test_reverse_rotations_are_normalized() -> None:
    assert is_reverse_rotation(0) is False
    assert is_reverse_rotation(1) is False
    assert is_reverse_rotation(2) is True
    assert is_reverse_rotation(3) is True


def test_reverse_rotation_inverts_touch_coordinates() -> None:
    x, y = map_display_ratio_to_input(
        0.25,
        0.75,
        1080,
        1920,
        2,
    )
    assert x == 810
    assert y == 480


def test_normal_rotation_keeps_touch_coordinates() -> None:
    x, y = map_display_ratio_to_input(
        0.25,
        0.75,
        1080,
        1920,
        0,
    )
    assert x == 270
    assert y == 1440
