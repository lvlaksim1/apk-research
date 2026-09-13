# AVD-RESEARCH profile

AVD-RESEARCH is the deep-observability Android target for Mobile Research v0.1.
It prioritizes reproducible diagnostics, root ADB and raw packet capture rather than Play Store equivalence.

## v0.1 reference profile

- Android API 35
- AOSP ATD x86_64 system image
- Android Emulator
- root ADB
- headless software-rendered display
- clean userdata for every automated acceptance run

System image package: system-images;android-35;aosp_atd;x86_64

## Required runtime capabilities

A usable AVD-RESEARCH target must be visible through ADB, fully booted, detected as an emulator, provide uid 0 through adb shell, support screenrecord and logcat, and expose a supported raw-network backend.

The current v0.1 network backend requires a usable tcpdump executable on the target.

## Automated real-device acceptance

The normal CI validates host code on windows-latest. A separate commit-triggered workflow creates a real Android Emulator on Ubuntu/KVM and executes the actual Mobile Research orchestration.

The workflow uses the built-in Android Settings package com.android.settings as a synthetic target. This package is part of the AOSP image and is not stored in the repository.

The acceptance sequence creates a session, captures metadata, starts logcat/screen/raw network collectors, launches Settings, performs a small Android-side network probe, runs health checks, stops collectors, exports a Research ZIP, and verifies the archive from its own contents.

Generated ZIPs and emulator logs are uploaded only as short-lived GitHub Actions artifacts. They are not committed to the repository.

## Release gate

The first v0.1.0 release is not ready until a real AVD-RESEARCH run finishes with session_status=complete and Research ZIP verification=valid.
A failed required collector is diagnostic evidence and must not be hidden or bypassed.