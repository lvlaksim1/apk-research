# Mobile Research v0.5.2

This hotfix corrects the blank Android panel found during the real-PC test of v0.5.1.

## Root cause

v0.5.0/v0.5.1 treated the hidden Qt window created by Android Emulator `-qt-hide-window` as if it were a normal standalone video HWND that could be embedded with Win32 `SetParent`.

That assumption was wrong.

`-qt-hide-window` is the Android Studio embedded-emulator launch mode. The hidden Qt window is not a supported native video surface for third-party HWND reparenting. Mobile Research could therefore find an HWND, call `SetParent`, and report a successful native attach while no Android pixels were visible.

## Stable Windows display path

v0.5.2 uses the supported embedded architecture:

`Android Emulator → -qt-hide-window → gRPC/MMAP framebuffer → Mobile Research AndroidView`

The existing low-latency framebuffer implementation is again the stable Windows display path.

Input continues through the persistent Emulator gRPC input stream, with ADB fallback.

## Startup fallback

On hardware-accelerated Windows the managed runtime now tries:

1. host GPU + embedded gRPC/MMAP;
2. GPU auto + embedded gRPC/MMAP;
3. SwiftShader + headless framebuffer compatibility mode.

The Android research core remains independent of display transport.

## Native HWND

The Win32 native-HWND experiment is disabled in stable runtime behavior. It is not used merely because an Emulator Qt HWND exists, so it can no longer suppress the working framebuffer stream or produce a false successful attach.

## Research evidence

No evidence collector changed:

- ADB target management;
- root;
- logcat;
- screen recording;
- raw PCAP/tcpdump;
- package metadata;
- Research ZIP;
- semantic audit.

## Distribution

Release assets:

- `MobileResearchSetup.exe`
- `SHA256SUMS.txt`

No separately installed Python, Android Studio or ADB is required.
