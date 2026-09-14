# Changelog

All notable Mobile Research changes are recorded here.

## [0.2.0rc1] - 2026-09-14 — v0.2 Desktop Application Release Candidate

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
- Android SDK repository resolution now follows stable `channel-0` and rejects newer beta/dev/canary emulator packages.
- Clean-Windows provisioning acceptance downloads, verifies and extracts the managed Android stack and validates ADB, aapt2, Emulator and the private AVD without relying on unsupported software boot inside GitHub-hosted Windows VMs.

### Validated

- Windows installer build, silent installation, standalone self-test and GUI smoke-test.
- Clean Windows provisioning selected Android Emulator 37.1.11 build 15917651, ADB 37.0.1 and Android 15 API 35 AOSP system image.
- Real Linux/KVM AVD acceptance completed boot, root, raw PCAP, logcat, screen evidence and verified Research ZIP on the exact main commit.
- Remaining RC validation: first-run accelerated Android boot on a real Windows/WHPX machine.

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
