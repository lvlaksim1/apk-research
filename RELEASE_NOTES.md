# Mobile Research v0.3.0

This release replaces the slow ADB/PNG interactive Android path with a low-latency embedded Emulator transport and incorporates the two follow-up fixes confirmed after the first real `com.evrasia` research session.

## Low-latency embedded Android

- The primary framebuffer path is now Android Emulator gRPC `streamScreenshot`.
- Frames are transported as RGB instead of repeatedly encoding/decoding full-screen PNG screenshots through ADB.
- The GUI publishes the newest available frame at approximately 30 fps and drops stale frames instead of allowing latency to accumulate.
- Touch, swipe and supported keyboard input are sent directly through the Emulator gRPC control plane.
- ADB screenshot/input remains an automatic compatibility fallback.
- Hardware-accelerated Emulator runs use `-gpu auto`, allowing Emulator to use host GPU acceleration when available. The software-only fallback retains SwiftShader.

The real Android/KVM acceptance workflow explicitly boots Android and validates the live gRPC framebuffer/input transport before running the normal research-session acceptance.

## Research launch modes

The GUI now exposes two explicit modes:

- **Clean launch (recommended):** `am force-stop <package>` before preflight, then collectors start, capture becomes ACTIVE, and only then is the target application launched.
- **Continue current state:** preserves the existing application state and continues from an already-running instance.

The selected mode is recorded in the session event log.

## Package metadata fix

The package dump fallback no longer invokes the incompatible Android `timeout 30s ...` wrapper that produced `timeout: Need 2 arguments` on the real Evrasia test.

The fallback now calls:

`cmd package dump-package <package>`

directly while Mobile Research itself enforces the bounded host-side timeout. This is intended to turn the previously partial package-metadata case into a complete session when the fallback succeeds.

## Windows hypervisor behavior

- WHPX remains the preferred Windows hypervisor.
- A usable AEHD/GVM remains an accepted compatibility fallback.
- Windows automatic WHPX setup still uses one UAC prompt and explicitly handles reboot-required state.
- Dedicated Windows WHPX acceptance remains available as additional hardware evidence, but an unavailable self-hosted WHPX runner no longer blocks normal stable publication.

## Validation

The v0.3 development candidate passed:

- Windows CI and unit tests;
- standalone Windows EXE build;
- GUI smoke test;
- Inno Setup build;
- installed-application smoke test;
- clean Windows managed-Android provisioning;
- real Android 15 / API 35 KVM boot;
- **live Emulator gRPC transport acceptance**;
- full real AVD Research Acceptance;
- Research ZIP verification.

The release commit is revalidated on its exact SHA before publication.

## Distribution

Release assets:

- `MobileResearchSetup.exe`
- `SHA256SUMS.txt`

Normal use requires no separately installed Python, Android Studio or ADB.
