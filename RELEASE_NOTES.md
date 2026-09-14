# Mobile Research v0.2.1

Stable Windows desktop hardening release.

## Main fix from real application testing

Testing against `com.evrasia` exposed a failure before collectors started: a full `dumpsys package` call could stall until the host ADB timeout and abort the entire research session.

v0.2.1 changes that behavior:

- Mobile Research best-effort waits for Package Manager main/background handlers before collecting package metadata.
- The primary package dump is bounded with Android-side timeout semantics.
- A second bounded Package Manager dump path is used as fallback.
- If both full-dump methods fail, the failure is recorded as degraded metadata rather than destroying the research run.
- Logcat, screen recording and raw PCAP are still allowed to start.
- Such a session ends as `partial`, not falsely `complete`, while preserving all successfully captured evidence.

This prevents the 1–2 KB failed Research ZIP observed in the real `com.evrasia` test from being the only surviving evidence when extended package metadata stalls.

## Windows runtime hardening

- Windows desktop runtime requires Windows Hypervisor Platform (WHPX) for the supported hardware-accelerated path.
- Hypervisor diagnostics distinguish WHPX from AEHD/GVM, KVM and other providers.
- Runtime acceptance can require the packaged/frozen installed executable, the exact installed executable path and a clean managed component root.

## Exact-SHA Windows WHPX acceptance

v0.2.1 adds a dedicated `Windows WHPX Acceptance` release gate for a hardware-capable Windows x64 runner.

The gate:

1. waits for the exact-SHA Desktop Build;
2. downloads that exact `MobileResearchSetup.exe`;
3. verifies its SHA-256;
4. removes previous Mobile Research user state;
5. installs the application as a normal user installation;
6. launches acceptance through the installed frozen `MobileResearch.exe`;
7. provisions the managed Android runtime from a clean component directory;
8. requires WHPX from Android Emulator acceleration diagnostics;
9. boots the private Android 15 / API 35 AVD;
10. proves root ADB, tcpdump and framebuffer access;
11. downloads the pinned Appium ApiDemos v6.0.17 APK and verifies its SHA-256;
12. makes Mobile Research itself identify, install and launch `io.appium.android.apis`;
13. records logcat, screen and raw PCAP;
14. exports, verifies and semantically audits the Research ZIP.

The stable release workflow requires this gate for the same release commit SHA in addition to Windows CI, Desktop Build and the real Ubuntu/KVM AVD Research Acceptance.

## Distribution

Release assets:

- `MobileResearchSetup.exe`
- `SHA256SUMS.txt`

Python, Android Studio and a separately installed ADB are not user dependencies.

## Runtime requirements

- Windows desktop x64
- hardware virtualization enabled
- Windows Hypervisor Platform usable by Android Emulator
- internet access during first Android provisioning
- approximately 1.3 GB of Android component downloads on first setup

## Evidence contract

v0.2.1 preserves the existing RAW-first guarantees:

- immutable raw evidence
- device/package metadata
- continuous logcat
- chunked screen recording
- mandatory raw PCAP for AVD-RESEARCH
- complete / partial / failed session semantics
- SHA-256 Research ZIP
- post-export integrity verification
- semantic lifecycle/timeline/evidence audit
