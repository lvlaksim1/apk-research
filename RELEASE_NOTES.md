# Mobile Research v0.8.5

v0.8.5 is the release-ready form of the second technical cleanup.

The v0.8.4 release candidate was intentionally not published: its exact-SHA Desktop Build reached the standalone GUI smoke test and exposed one stale method name in the shutdown path after the DWM refactor.

## Fixed

- `MainWindow.closeEvent` now calls `AndroidView.detach_dwm()` instead of the removed `detach_native()`.
- The last two legacy native-HWND test names are renamed to current framebuffer/DWM terminology.
- The DWM connection log now describes the actual thumbnail path rather than referring to the rejected SetParent experiment.

## Preserved

Everything else from the v0.8.4 cleanup is unchanged:

- primary hidden Emulator → gRPC/MMAP → AndroidView path;
- top-down framebuffer orientation;
- persistent DOWN/MOVE/UP input and smooth swipe;
- DWM as last compatibility fallback;
- one-shot `-wipe-data` guest boot recovery;
- evidence collectors and Research ZIP pipeline;
- removal of legacy native-HWND naming and dead GUI tap path.

The packaged GUI open/close smoke test remains part of Desktop Build and is the acceptance gate for this correction.
