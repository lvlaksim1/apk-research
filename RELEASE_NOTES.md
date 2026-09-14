# Mobile Research v0.4.0

This release replaces the remaining screenshot-style bottlenecks in the embedded Android UI with the Android Emulator's shared-memory display path.

## Shared-memory framebuffer

The primary interactive display path is now:

`Android Emulator → gRPC frame notification → ImageTransport.MMAP → shared RGBA buffer → QPainter`

The full framebuffer is no longer carried inside a protobuf message for every frame when MMAP is available.

- Emulator writes RGBA pixels directly into a client-owned memory-mapped file.
- gRPC carries frame metadata and notifications.
- The GUI paints directly from the mapped buffer.
- `grpc-bytes` remains an automatic compatibility fallback.
- ADB screenshot polling remains the final fallback and is not the normal interactive path.

The real Android/KVM acceptance now explicitly requires a successful **`grpc-mmap`** frame before the normal research-session acceptance continues.

## 60 Hz presentation

The embedded Android view now uses a precise approximately **60 Hz** GUI presentation timer instead of the previous ~30 Hz cadence.

The latest-frame policy remains in place, so stale frames are discarded rather than accumulating visible latency.

## Persistent input stream

Touch and keyboard events now use one long-lived Emulator `streamInputEvent` gRPC stream when available.

This removes repeated unary RPC setup from the normal interactive input path. Unary `sendTouch` / `sendKey` remain compatibility fallbacks.

## Windows rendering path

On hardware-accelerated Windows systems Mobile Research now starts the managed Emulator using:

`-qt-hide-window`

instead of `-no-window`.

This preserves the Emulator Qt graphics path while keeping the separate Emulator window hidden. GPU policy remains:

1. `-gpu host` first;
2. automatic retry with `-gpu auto` if host rendering cannot boot;
3. SwiftShader only for the software-only fallback.

## Orientation fix

The v0.3.1 reverse-orientation correction was based on an incorrect interpretation of the Emulator screenshot metadata.

The Emulator already returns the logical screenshot in the requested device orientation. Raw RGB/RGBA memory is bottom-up, so v0.4.0 applies exactly one vertical memory-order correction and no additional reverse-rotation transform.

Before the live display starts, Mobile Research also normalizes the managed Android instance to portrait orientation with the WindowManager/user rotation lock. This addresses the upside-down/mirrored initial boot screen reported on the real Windows test machine.

## Research functionality preserved

The release retains:

- clean launch / continue-current-state modes;
- package-dump fallback hardening;
- WHPX preferred path with usable AEHD compatibility fallback;
- logcat;
- screen recording;
- raw PCAP;
- complete / partial / failed session semantics;
- verified Research ZIP export;
- semantic audit.

## Validation

The development implementation passed:

- Windows CI;
- standalone Windows executable build;
- self-test and GUI smoke test;
- Inno Setup installer build;
- installed-application smoke test;
- clean Windows managed-Android provisioning;
- real Android 15 / API 35 KVM boot;
- **MMAP framebuffer acceptance (`grpc-mmap` required)**;
- live Emulator input validation;
- full real AVD Research Acceptance;
- Research ZIP integrity verification and semantic audit.

The exact v0.4.0 release commit is revalidated again by CI, Desktop Build and real AVD Research Acceptance before publication.

## Distribution

Release assets:

- `MobileResearchSetup.exe`
- `SHA256SUMS.txt`

Normal use requires no separately installed Python, Android Studio or ADB.
