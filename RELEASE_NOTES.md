# Mobile Research v0.5.1

This is a Windows Emulator startup reliability hotfix based on the first real-PC test of v0.5.0.

The v0.5.0 test showed that the managed Android Emulator process itself could terminate during boot while using the new native Qt/GPU display path. Mobile Research remained alive, but the internal Emulator crash reporter appeared over the application and the user could not reach a usable Android target.

## Automatic compatibility ladder

Windows startup now tries three isolated profiles in order:

1. native Emulator HWND with host GPU;
2. headless Emulator with host GPU;
3. headless Emulator with SwiftShader.

A failure of the native display path therefore no longer prevents research. If the native path is unstable on a particular GPU/driver combination, Mobile Research automatically falls back to the existing framebuffer transport while keeping WHPX/AEHD CPU virtualization and the research collectors independent.

## Managed crash handling

Managed Emulator launches now use `-crash-report-mode disabled`.

An internal QEMU/Emulator failure is handled by Mobile Research itself instead of leaving the Android Emulator crash-report dialog over the GUI. The failure is preserved in Mobile Research diagnostics and the next compatibility profile is attempted automatically.

## Display selection

Native HWND embedding is attempted only when the profile that actually booted Android created a native Qt window.

When a headless compatibility profile succeeds, Mobile Research immediately uses:

1. gRPC MMAP framebuffer;
2. gRPC byte framebuffer;
3. ADB screenshot/input fallback.

The evidence pipeline is unchanged: ADB, root, logcat, screen recording, raw PCAP, metadata and Research ZIP do not depend on the display mode.

## Diagnostics

Each startup attempt records:

- display profile;
- GPU mode;
- duration;
- process exit code when available;
- captured startup error;
- exact Emulator command line.

This makes future driver/GPU-specific failures diagnosable from the Mobile Research diagnostics rather than from a manually copied crash report.

## Distribution

Release assets:

- `MobileResearchSetup.exe`
- `SHA256SUMS.txt`

No separately installed Python, Android Studio or ADB is required.
