# Changelog

All notable Mobile Research changes are recorded here.

## [0.3.1] - 2026-09-14

### Fixed

- Reverse portrait/landscape startup frames are normalized before display and touch coordinates are transformed consistently.
- Corrected the Android input Y clamp to use input-space height rather than framebuffer height.
- gRPC input failures no longer tear down the framebuffer stream and force the whole UI back to ADB screenshot polling.

### Performance

- Reduced the live stream target from 540×960 RGB to 360×640 RGBA, cutting transferred framebuffer volume substantially while closely matching the embedded view size.
- Replaced per-frame QImage copy + mirror + QPixmap conversion + scaled-pixmap allocation with zero-copy QImage ownership and direct QPainter scaling/flip at paint time.
- Replaced one new Python thread per input event with a single ordered input worker.
- Windows hardware-accelerated Emulator now tries `-gpu host` first and automatically retries with `-gpu auto` if the host backend cannot boot.

## [0.3.0] - 2026-09-14

### Added

- Low-latency Android Emulator gRPC framebuffer/input transport for the embedded Android view.
- Latest-frame GUI delivery at approximately 30 fps; stale frames are dropped instead of accumulating latency.
- Explicit research launch modes: clean launch and continue-current-state.

### Changed

- Hardware-accelerated Emulator runs use `-gpu auto` instead of forced SwiftShader; software-only fallback retains SwiftShader.
- ADB screenshot/input remains an automatic compatibility fallback but is no longer the primary interactive transport.
- Package dump fallback invokes `cmd package dump-package` directly under the existing host-side timeout.


## [0.2.2] - 2026-09-14

### Fixed

- Restored compatibility with an already-installed and usable Android Emulator Hypervisor Driver (AEHD/GVM) on Windows. WHPX remains the preferred and release-accepted Windows path, but usable AEHD no longer blocks the user or triggers elevation.
- Fixed duplicate UAC prompts during Windows virtualization setup: Mobile Research now performs the entire WHPX configuration through one elevated PowerShell process.
- Removed unnecessary automatic enablement of VirtualMachinePlatform; Android Emulator WHPX needs HypervisorPlatform, not a second unrelated Windows feature.
- WHPX setup now also ensures `hypervisorlaunchtype=Auto` and explicitly reports when a reboot is required instead of immediately treating the still-running AEHD provider as a fatal error.


## [0.2.1] - 2026-09-14

### Changed

- Package metadata preflight no longer destroys an otherwise viable research session when a full Package Manager dump stalls. Mobile Research now waits for Package Manager handlers, uses bounded primary/fallback dump commands, and continues with degraded metadata so logcat/screen/PCAP can still be captured; the final session is `partial` rather than falsely `complete`.
- Windows desktop runtime now requires the Microsoft Windows Hypervisor Platform (WHPX) instead of accepting AEHD/GVM as an equivalent Windows hypervisor.
- Runtime acceptance can require a packaged/frozen executable, exact installed executable path, a clean managed-component root and verified WHPX.

### CI / Acceptance

- Added a dedicated Windows WHPX end-to-end gate for a hardware-capable self-hosted Windows x64 runner.
- The gate downloads the exact-SHA `Desktop Build` installer, performs a clean per-user installation, provisions Android through the installed `MobileResearch.exe`, boots the private AVD with WHPX, validates root/tcpdump/framebuffer, downloads the pinned Appium ApiDemos v6.0.17 fixture with SHA-256 verification, makes Mobile Research detect/install/launch that APK, records a real research session, and verifies plus semantically audits the resulting Research ZIP.
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
