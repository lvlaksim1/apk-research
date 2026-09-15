# Mobile Research v0.8.2

v0.8.2 fixes the display-only inversion found during the real-PC validation of v0.8.1.

## Real-PC result carried forward

The v0.8.1 test confirmed that the new primary architecture is correct:

- no standalone Android Emulator window flash;
- hidden `-qt-hide-window` startup works;
- gRPC/MMAP framebuffer is responsive;
- continuous DOWN/MOVE/UP swipe is smooth and low-latency.

Those parts are unchanged in v0.8.2.

## Fixed

`AndroidView` previously assumed every raw RGBA/RGB framebuffer was bottom-up and always applied a vertical flip. The current Android Emulator `streamScreenshot` transport already supplies the frame in logical top-down row order, so that second flip inverted the picture while Android input coordinates remained correct.

v0.8.2 makes row order explicit:

1. `LiveFrame` carries `row_order`.
2. gRPC/MMAP and gRPC byte `streamScreenshot` frames are marked `top-down`.
3. `AndroidView` paints top-down frames without any vertical transformation.
4. A vertical flip is retained only for a source explicitly marked `bottom-up`.

## Deliberately unchanged

- touch coordinate mapping;
- persistent gRPC `streamInputEvent`;
- mouse DOWN/MOVE/UP swipe cadence;
- hidden Emulator startup;
- DWM last-resort fallback;
- ADB/root preparation;
- evidence collection and Research ZIP pipeline.

## Regression protection

The transport test suite now verifies that Emulator `streamScreenshot` frames carry the top-down row-order contract and that bottom-up compatibility remains explicit rather than implicit.
