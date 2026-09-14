# Changelog

All notable Mobile Research changes are recorded here.

## Unreleased — 0.2.1.dev0

### Changed

- Windows desktop runtime now requires the Microsoft Windows Hypervisor Platform (WHPX) instead of accepting AEHD/GVM as an equivalent Windows hypervisor.
- Runtime acceptance can require a packaged/frozen executable, exact installed executable path, a clean managed-component root and verified WHPX.

### CI / Acceptance

- Added a dedicated Windows WHPX end-to-end gate for a hardware-capable self-hosted Windows x64 runner.
- The gate downloads the exact-SHA `Desktop Build` installer, performs a clean per-user installation, provisions Android through the installed `MobileResearch.exe`, boots the private AVD with WHPX, validates root/tcpdump/framebuffer, records a real research session, and verifies plus semantically audits the resulting Research ZIP.
- Future stable releases must pass `Windows WHPX Acceptance` for the exact release SHA in addition to CI, Linux/KVM AVD acceptance and Desktop Build.

## [0.2.0] - 2026-09-14

### Added

- Native Windows desktop GUI as the primary product interface.
- Self-contained PyInstaller/Inno Setup distribution; no user-installed Python.
- Managed private Android SDK/component store under `%LOCALAPPDATA%\MobileResearch\components`.
- Automatic provisioning of ADB, Android Emulator, aapt2 and Android 15 API 35 AOSP image.
- Private AVD lifecycle without Android Studio.
- Best-effort Windows Hypervisor Platform enablement via UAC.
- APK package detection and automatic installation.
- Headless Android with integrated GUI framebuffer and touch/swipe/keyboard input.
- GUI START/STOP using ResearchOrchestrator directly.
- GUI session history, Research ZIP verify/audit and diagnostics.
- Desktop Build workflow producing `MobileResearchSetup.exe` plus SHA-256.
- Stable release gate extended to exact-SHA CI + AVD acceptance + Desktop Build.
- Stable-only Android repository selection (`channel-0`), preventing beta/dev/canary Emulator packages from entering the managed runtime.
- Clean Windows Android provisioning acceptance: download, checksum verification, extraction, private AVD creation and executable/version checks.
- User-visible first-run download progress in MiB and percent.
- Runtime diagnostics for installed ADB, Emulator and aapt2 versions plus normalized acceleration availability.
- GUI repair action that removes only managed Android components and preserves all research sessions.
- Best-effort GUI recovery that stops active collectors and preserves partial/failed Research ZIP after runtime exceptions.

### Preserved

- v0.1.0 raw evidence contract and complete/partial/failed semantics are unchanged.

## [0.1.0] - 2026-09-13

First stable Research Session Core release.

### Added

- ADB Target Manager with emulator/physical classification and package checks.
- Research Session state machine with complete/partial/failed semantics.
- Device/System Metadata Collector with large package-dump streaming through target files.
- Full-buffer Logcat Collector with non-destructive pre-roll.
- Chunked Screen Recording Collector with Winscope-v2 absolute frame timing extraction.
- Mandatory raw packet capture for AVD-RESEARCH through rooted adb + tcpdump.
- Separation of tcpdump diagnostics from the binary PCAP stream.
- End-to-end Session Orchestrator.
- Self-verifying Research ZIP with CRC, complete SHA-256 coverage and atomic export.
- Semantic Research ZIP audit for lifecycle ordering, clock skew and evidence timestamp coverage.
- Real Android Emulator acceptance workflow on Ubuntu/KVM.
- Commit-triggered release workflow that waits for exact-SHA Windows CI and AVD acceptance.

### Validated

Two consecutive pre-release real AVD-RESEARCH runs completed successfully. The stricter second run recorded 12 PCAP packets, 914 logcat entries and 139 screen frames, with a maximum measured host/target clock skew of 0.942 s.

The final release commit is revalidated again before GitHub Release publication.

### Known v0.1.0 boundaries

- CLI only; no GUI.
- AVD-RESEARCH is the accepted runtime target.
- Raw network backend requires root ADB and tcpdump.
- AVD-PLAY and Physical Device backends are not release-accepted yet.
- No MITM/TLS decryption.
- No Android Research Agent/runtime instrumentation.
- No static APK analyzer or automatic protocol interpretation.
