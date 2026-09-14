# Mobile Research v0.5.0

This release changes the Windows Android display architecture fundamentally.

The previous v0.3/v0.4 generations mirrored Android into the Mobile Research GUI through screenshot/framebuffer transports. Even with gRPC MMAP and a 60 Hz presentation timer, that remained a second presentation pipeline and could not reliably match the smoothness of the native Android Emulator window.

v0.5.0 therefore stops mirroring the display on the normal Windows path.

## Native Android Emulator window

The primary Windows display path is now:

`Android / SurfaceFlinger → Emulator GPU renderer → native Emulator Qt window → Win32 HWND child of Mobile Research`

Mobile Research:

- starts its managed Android Emulator with the Qt window created but initially hidden;
- finds the Emulator top-level HWND after Android has booted;
- tracks the launcher process and its descendants so the actual Emulator/QEMU window can be identified;
- removes top-level window chrome;
- reparents the real Emulator window into the Android panel with Win32 `SetParent`;
- resizes the child HWND with the Mobile Research panel;
- shows and focuses the embedded native window.

Mouse and keyboard input then go directly to the Emulator native window. There is no Mobile Research coordinate remapping in the normal Windows path.

## Why this is faster

Normal Windows interaction no longer performs:

- screenshot capture;
- gRPC/MMAP frame polling;
- framebuffer copies;
- QImage/QPainter video presentation;
- application-side frame scheduling;
- dropped-frame/latest-frame arbitration;
- gRPC touch forwarding.

The same Emulator GPU-rendered window that would normally be displayed standalone is now displayed inside Mobile Research.

## Compatibility fallback

The v0.4 display stack is retained as an automatic fallback.

If the native Emulator window cannot be located or attached, Mobile Research switches back to:

1. gRPC MMAP framebuffer;
2. gRPC byte framebuffer;
3. ADB screenshot/input as the final fallback.

A native-window attach failure does **not** stop an active research session or collectors.

## Research architecture unchanged

Native display embedding does not change the evidence contract or collectors:

- APK installation and target management remain ADB-based;
- root ADB remains available;
- logcat collection is unchanged;
- screen recording is unchanged;
- raw PCAP/tcpdump is unchanged;
- package metadata collection is unchanged;
- clean launch / continue-current-state modes are unchanged;
- Research ZIP complete/partial/failed semantics and semantic audit are unchanged.

Display transport and research transport are deliberately independent.

## Validation

The development implementation passed:

- Windows CI;
- Windows desktop unit tests;
- a Win32 native-window test that creates a real Qt top-level HWND, discovers it through the same process/window enumeration path and reparents it into another native Qt host;
- standalone EXE build;
- GUI smoke test;
- Inno Setup installer build;
- installed-application smoke test;
- clean Windows managed-Android provisioning;
- real Android 15 / API 35 KVM boot;
- real AVD Research Acceptance;
- Research ZIP integrity verification and semantic audit.

The exact v0.5.0 release commit is revalidated by CI, Desktop Build and real AVD Research Acceptance before publication.

## Distribution

Release assets:

- `MobileResearchSetup.exe`
- `SHA256SUMS.txt`

Normal use requires no separately installed Python, Android Studio or ADB.
