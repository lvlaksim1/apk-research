from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build" / "app-icon"


def _scale(value: float, size: int) -> int:
    return round(value * size / 512)


def build_icon(size: int = 512) -> Image.Image:
    image = Image.new("RGBA", (size, size), (8, 25, 44, 255))
    draw = ImageDraw.Draw(image)

    # Deep blue rounded tile, matching the accepted image-generation concept.
    margin = _scale(18, size)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=_scale(78, size),
        fill=(4, 62, 105, 255),
        outline=(14, 104, 166, 255),
        width=max(1, _scale(4, size)),
    )

    # Phone body.
    phone = (
        _scale(92, size),
        _scale(54, size),
        _scale(332, size),
        _scale(450, size),
    )
    draw.rounded_rectangle(
        phone,
        radius=_scale(40, size),
        fill=(10, 35, 54, 255),
        outline=(91, 220, 255, 255),
        width=max(2, _scale(20, size)),
    )
    draw.rounded_rectangle(
        (
            _scale(140, size),
            _scale(80, size),
            _scale(284, size),
            _scale(96, size),
        ),
        radius=_scale(8, size),
        fill=(184, 244, 255, 255),
    )
    draw.rounded_rectangle(
        (
            _scale(177, size),
            _scale(414, size),
            _scale(247, size),
            _scale(426, size),
        ),
        radius=_scale(6, size),
        fill=(25, 140, 190, 255),
    )

    # Android robot.
    green = (125, 207, 44, 255)
    dark_green = (82, 156, 25, 255)
    draw.pieslice(
        (
            _scale(132, size),
            _scale(142, size),
            _scale(291, size),
            _scale(292, size),
        ),
        180,
        360,
        fill=green,
    )
    draw.rounded_rectangle(
        (
            _scale(132, size),
            _scale(211, size),
            _scale(291, size),
            _scale(349, size),
        ),
        radius=_scale(16, size),
        fill=green,
    )
    for x in (155, 248):
        draw.rounded_rectangle(
            (
                _scale(x, size),
                _scale(326, size),
                _scale(x + 28, size),
                _scale(382, size),
            ),
            radius=_scale(12, size),
            fill=green,
        )
    for x in (106, 291):
        draw.rounded_rectangle(
            (
                _scale(x, size),
                _scale(220, size),
                _scale(x + 27, size),
                _scale(319, size),
            ),
            radius=_scale(12, size),
            fill=green,
        )
    draw.line(
        (
            _scale(165, size),
            _scale(154, size),
            _scale(143, size),
            _scale(118, size),
        ),
        fill=green,
        width=max(2, _scale(8, size)),
    )
    draw.line(
        (
            _scale(258, size),
            _scale(154, size),
            _scale(280, size),
            _scale(118, size),
        ),
        fill=green,
        width=max(2, _scale(8, size)),
    )
    eye_r = _scale(7, size)
    for x in (174, 249):
        cx, cy = _scale(x, size), _scale(190, size)
        draw.ellipse(
            (cx - eye_r, cy - eye_r, cx + eye_r, cy + eye_r),
            fill=(18, 66, 38, 255),
        )

    # Magnifying glass above the robot/phone.
    lens_center = (_scale(330, size), _scale(300, size))
    lens_r = _scale(92, size)
    cx, cy = lens_center
    draw.ellipse(
        (cx - lens_r, cy - lens_r, cx + lens_r, cy + lens_r),
        fill=(230, 242, 247, 255),
        outline=(244, 251, 255, 255),
        width=max(2, _scale(8, size)),
    )
    inner_r = _scale(64, size)
    draw.ellipse(
        (cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r),
        fill=(7, 73, 111, 255),
        outline=(36, 163, 221, 255),
        width=max(2, _scale(10, size)),
    )
    draw.arc(
        (
            cx - _scale(45, size),
            cy - _scale(45, size),
            cx + _scale(45, size),
            cy + _scale(45, size),
        ),
        205,
        305,
        fill=(132, 225, 255, 255),
        width=max(2, _scale(10, size)),
    )
    draw.line(
        (
            _scale(392, size),
            _scale(366, size),
            _scale(456, size),
            _scale(430, size),
        ),
        fill=(224, 239, 247, 255),
        width=max(4, _scale(34, size)),
    )
    draw.line(
        (
            _scale(402, size),
            _scale(376, size),
            _scale(456, size),
            _scale(430, size),
        ),
        fill=(40, 184, 235, 255),
        width=max(3, _scale(20, size)),
    )

    # Small blue accent under the phone.
    draw.rounded_rectangle(
        (
            _scale(185, size),
            _scale(445, size),
            _scale(241, size),
            _scale(456, size),
        ),
        radius=_scale(5, size),
        fill=(25, 181, 229, 255),
    )

    return image


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image = build_icon()
    png = OUTPUT / "apk-research-icon.png"
    ico = OUTPUT / "apk-research.ico"
    image.save(png, optimize=True)
    image.save(
        ico,
        format="ICO",
        sizes=[
            (16, 16),
            (24, 24),
            (32, 32),
            (48, 48),
            (64, 64),
            (128, 128),
            (256, 256),
        ],
    )
    print(png)
    print(ico)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
