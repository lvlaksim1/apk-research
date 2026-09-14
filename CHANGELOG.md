# Changelog

All notable Mobile Research changes are recorded here.

## [0.7.6] - 2026-09-15

### DWM source-window identity fix

- Reverted the v0.7.5 STARTUPINFO/SW_HIDE process-launch experiment. The real-PC test showed that hidden startup allowed Mobile Research to bind to a hidden Qt helper top-level HWND from the Emulator process while the real Emulator window appeared separately.
- DWM source discovery now strongly prefers a top-level window whose title identifies the actual Android Emulator or managed AVD; PID ancestry alone is no longer sufficient when an identified Emulator window exists.
- The real Emulator window is discovered while visible, immediately hidden only after positive identity, positioned behind Mobile Research, shown without activation, and then registered with DWM.
- Added a Windows discovery test proving that a larger same-process Qt helper window cannot outrank the correctly titled Emulator window.
- The real-time gRPC touch DOWN/MOVE/UP path from v0.7.5 is retained unchanged.

## [0.7.5] - 2026-09-15

### Real-time touch drag

- Mouse interaction in the Android panel now maps directly to the Emulator touch lifecycle: mouse press → touch DOWN, mouse movement → streamed touch MOVE, mouse release → touch UP.
- MOVE events are emitted continuously while dragging, throttled to approximately 80 Hz to avoid input-queue backlog while preserving native-feeling motion.
- The final drag position is always sent before UP, so scrolling tracks the cursor instead of executing only after mouse release.
- Drag coordinates are clamped to the Android display rectangle, allowing a gesture to finish correctly even when the pointer reaches or slightly crosses an edge.
- The existing wheel swipe path and ADB fallback remain available.

### Startup flash suppression

- The Windows DWM-live Emulator process is now launched with STARTUPINFO/SW_HIDE where supported.
- DWM source discovery accepts the initially hidden top-level Emulator window, positions it behind Mobile Research, and only then shows it without activation.
- Initial HWND polling was reduced from 15 ms to 5 ms as an additional guard for Emulator builds that partially ignore the Windows startup show state.

## [0.7.4] - 2026-09-15

### Covered DWM source window

- Reverted the v0.7.3 off-screen source-window strategy after the real-PC test showed that moving the Emulator completely outside the virtual desktop makes its DWM thumbnail black.
- The real standalone Emulator GPU window now remains on the active desktop but is continuously positioned and, if necessary, scaled entirely inside the Mobile Research top-level bounds.
- The source window is kept immediately behind Mobile Research in top-level z-order, remains visible/non-minimized for GPU/DWM rendering, and stays excluded from taskbar/Alt+Tab.
- When Mobile Research is minimized, the source Emulator window is temporarily hidden; it is positioned behind Mobile Research before being shown again on restore.
- DWM source geometry and z-order are maintained every 100 ms so later Qt geometry changes cannot expose the standalone Emulator window.

### Tabs

- DWM thumbnail visibility now follows the selected application tab. The live Android image is visible only on the Исследование tab and is explicitly disabled on Results, History, Diagnostics and Settings.
- Returning to Исследование re-enables the same DWM thumbnail and recalculates its destination rectangle.

## [0.7.3] - 2026-09-15

### Single-window DWM UX

- The standalone Android Emulator source window is now continuously kept outside the entire Windows virtual desktop instead of being moved only once. This prevents the Emulator from reappearing when Qt changes/restores its geometry later in the boot sequence.
- The source top-level window is marked as a tool window and has APPWINDOW removed, keeping it out of Alt+Tab/taskbar while preserving the visible/non-minimized state required by DWM composition.
- DWM destination geometry and source-window suppression are maintained every 100 ms while live mode is active.
- Initial source-window discovery now polls every 15 ms to minimize any startup flash before the window is moved off-screen.
- Shutdown order is reversed: Mobile Research stops the Emulator process while the DWM thumbnail is still registered, and only then unregisters DWM. This removes the second-window flash observed when closing v0.7.2.
- No SetParent, hiding, minimizing, or framebuffer copy is used in DWM live mode.

## [0.7.2] - 2026-09-15

### Release workflow

- Fixed release-candidate detection for the ephemeral Windows installer artifact. Desktop Build now uploads the one-day installer artifact only for commits whose message starts with `Release Mobile Research v`, matching the project's commit-driven release contract.
- This avoids both false negatives on real releases and unnecessary installer artifacts on ordinary commits.

## [0.7.1] - 2026-09-15

### Fixed

- Corrected conversion of the Win32 DWM thumbnail handle returned through ctypes before storing it in the live-display controller.

## [0.7.0] - 2026-09-15

### DWM live display

- Removed cross-process Win32 `SetParent` from the active display path after the real v0.6.0 test proved that re-parenting the Emulator Qt window leaves its GPU surface black.
- Windows now keeps the real Android Emulator as an independent top-level GPU window and registers it as a live Desktop Window Manager thumbnail in the Mobile Research top-level window.
- The source Emulator window is moved outside the virtual desktop only after DWM registration succeeds; it remains visible/non-minimized for composition and is never restored during shutdown, eliminating the second-window flash.
- DWM renders directly into the Android panel region; Mobile Research does not copy the Emulator GPU frame through Python or QPainter.
- Emulator side-toolbar pixels are cropped from the DWM source region when the normal phone aspect can be inferred.
- Mouse, swipe, keyboard and text input continue through Emulator gRPC, independent of the DWM presentation path.
- gRPC/MMAP remains the automatic fallback if DWM composition, thumbnail registration, or source-window discovery fails.

### Validation

- Added pure geometry tests for DWM destination fitting and Emulator toolbar cropping.
- Native-window tests now validate only discovery of a real visible top-level source; no test or runtime code re-parents the Emulator window.

## [0.6.0] - 2026-09-15

### Native display

- Primary Windows mode now launches the real visible standalone Android Emulator Qt/GPU window and embeds that top-level HWND instead of trying to reuse a hidden `-qt-hide-window` HWND.
- Window discovery begins immediately after Emulator process creation, while Android is still booting.
- Native attach verifies Win32 `SetParent`, actual parent HWND, non-empty client area and visibility before success.
- Framebuffer remains available until native attach is confirmed; failed native attach automatically continues through gRPC/MMAP.
- Windows fallback order: standalone/native host → standalone/native auto → hidden gRPC/MMAP host → hidden gRPC/MMAP auto → headless SwiftShader.

### Orientation

- Reverse framebuffer rotation normalization is restored for rotation 2/3, including matching touch-coordinate transformation.
- Fixes the upside-down first framebuffer frame reproduced on the real Windows test of v0.5.2.

## [0.5.2] - 2026-09-14

### Fixed

- Removed the false-positive native HWND display path that could report "Нативное окно Android Emulator встроено" while the Android panel remained blank.
- Windows stable display now uses the Android Emulator embedded mode for its intended purpose: `-qt-hide-window` keeps the Emulator UI hidden while Mobile Research consumes the live framebuffer through gRPC/MMAP.
- The screen stream is no longer stopped merely because a hidden Qt HWND exists.
- Windows boot fallback now tries host GPU → GPU auto through the same embedded gRPC/MMAP path, then falls back to headless SwiftShader if required.

### Architecture

- Native Win32 `SetParent` embedding is no longer part of the stable runtime contract. The code remains isolated for future experiments, but stable releases do not activate it.
- This corrects the v0.5.0 assumption that Android Studio's `-qt-hide-window` mode exposes a reusable native video HWND. Android Studio's embedded path is based on the Emulator control/framebuffer transport instead.

## [0.5.1] - 2026-09-14

### Fixed

- Real-Windows startup no longer treats a crash of the native Qt/GPU Emulator path as a fatal application failure.
- Windows managed boot now uses an ordered compatibility ladder: native HWND + host GPU → headless + host GPU → headless + SwiftShader.
- Native HWND attachment is attempted only when the successful boot actually uses the native-window profile; compatibility boots immediately use the existing MMAP/gRPC framebuffer path.
- Android Emulator crash-report UI is disabled for managed launches so an internal QEMU failure cannot leave a Google crash dialog over the Mobile Research interface.

### Diagnostics

- Every Emulator startup attempt now records its display mode, GPU mode, duration, exit code, error and exact command line in Mobile Research diagnostics.
- Compatibility fallback is reported explicitly in the progress log instead of looking like a stalled second boot.

## [0.5.0] - 2026-09-14

### Architecture

- Windows interactive display now embeds the **real Android Emulator native Qt window (HWND)** into the Mobile Research GUI instead of redrawing a screenshot/framebuffer stream.
- The Emulator keeps its own native GPU rendering and receives mouse/keyboard input directly from Windows.
- The existing MMAP/gRPC framebuffer pipeline remains only as an automatic compatibility fallback if native-window attachment fails.

### Performance

- Normal Windows interaction no longer performs screenshot capture, MMAP frame polling, QImage/QPainter video rendering, frame scheduling, coordinate remapping or gRPC touch forwarding.
- Native Emulator rendering therefore runs at the same frame production/presentation path as the standalone Emulator window.

## [0.4.0] - 2026-09-14

### Changed

- Embedded Android framebuffer now uses Emulator gRPC MMAP/shared-memory transport first, with byte-stream gRPC as compatibility fallback.
- GUI presentation cadence increased to a precise ~60 Hz instead of 30 Hz.
- Touch/key input uses one persistent `streamInputEvent` gRPC stream instead of a unary RPC per event when supported.
- Hardware-accelerated Windows Emulator uses the Android-Studio-style `-qt-hide-window` mode rather than `-no-window`.

### Fixed

- Removed the incorrect second rotation transform: Emulator screenshots are already logically rotated by the server; only the documented bottom-up raw-memory correction is applied.
- Android boot is normalized to portrait with WindowManager/user rotation lock before the embedded display is shown.


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
