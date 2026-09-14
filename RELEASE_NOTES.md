# Mobile Research v0.3.1

Hotfix for two issues discovered during real Windows testing of v0.3.0: the embedded Android home screen could initially appear upside-down/reversed, and interactive latency remained too high.

## Orientation fix

The Emulator screenshot protocol exposes coarse device rotation metadata. v0.3.0 discarded that field and only corrected the bottom-up raw pixel layout.

v0.3.1 now:

- parses the official Emulator `ImageFormat.rotation` field;
- distinguishes normal and reverse portrait/landscape orientations;
- normalizes reverse orientation before display;
- transforms touch coordinates consistently with the normalized image;
- fixes the input Y-coordinate clamp to use Android input-space height.

This directly addresses the startup state where Android appeared reversed before selecting an APK.

## Rendering and latency improvements

The v0.3.0 path still performed several expensive operations for every frame:

`gRPC bytes → QImage copy → mirror copy → QPixmap upload → scaled QPixmap allocation`

v0.3.1 changes that path substantially:

- live stream target reduced from **540×960 RGB** to **360×640 RGBA**, which is close to the actual embedded-view resolution and substantially reduces transport/copy volume;
- QImage now owns the frame only through the retained frame object rather than making an immediate deep copy;
- vertical bottom-up correction and reverse-orientation normalization are performed by QPainter transforms during paint;
- QPixmap conversion and per-frame scaled-pixmap allocation are removed;
- the GUI still keeps only the newest frame, so stale frames cannot accumulate latency;
- input events now use one ordered worker instead of creating a new Python thread for each click/swipe/key event;
- an isolated gRPC input failure falls back for that input without destroying the live framebuffer stream and forcing the whole UI back to slow ADB screenshots.

## Windows GPU acceleration

For hardware-accelerated Windows systems:

1. Mobile Research first starts Android Emulator with **`-gpu host`**;
2. if that backend cannot boot, Mobile Research automatically stops it and retries with **`-gpu auto`**;
3. software-only Emulator mode continues to use SwiftShader.

The currently active framebuffer transport and GPU mode are shown in the Android readiness status/diagnostics.

## Preserved functionality

v0.3.1 retains:

- Emulator gRPC framebuffer/input transport with ADB fallback;
- clean launch / continue-current-state research modes;
- fixed package-dump fallback;
- AEHD compatibility fallback and preferred WHPX path;
- logcat, screen recording and raw PCAP collection;
- complete / partial / failed evidence semantics;
- verified Research ZIP export and semantic audit.

## Validation

The development SHA passed:

- Windows CI;
- standalone EXE build and self-test;
- GUI smoke test;
- Inno Setup build;
- installed-application smoke test;
- clean Windows managed-Android provisioning;
- real Android 15 / API 35 KVM boot;
- live Emulator gRPC transport acceptance;
- full real AVD Research Acceptance and Research ZIP verification.

The exact v0.3.1 release commit is revalidated by CI, Desktop Build and real AVD Research Acceptance before GitHub publication.

## Distribution

Release assets:

- `MobileResearchSetup.exe`
- `SHA256SUMS.txt`

No separately installed Python, Android Studio or ADB is required.
