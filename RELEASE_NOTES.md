# Mobile Research v0.2.0

First stable **Desktop Application** release.

## What changed

Mobile Research is now a self-contained Windows application rather than a command-line research core.

Normal use does not require the user to install Python, Android Studio, ADB, SDK Manager or create an AVD manually.

The primary workflow is:

```text
install MobileResearchSetup.exe
→ launch Mobile Research
→ choose APK
→ Mobile Research prepares Android automatically
→ START RESEARCH
→ interact with Android inside the application
→ STOP / SAVE
→ verified Research ZIP
```

## Managed Android runtime

Mobile Research owns a private Android environment under `%LOCALAPPDATA%\MobileResearch\components`.

It automatically provisions:

- Android platform-tools / ADB
- stable Android Emulator from Google repository `channel-0`
- build-tools 35.0.0 / aapt2
- Android 15 / API 35 AOSP default x86_64 system image
- private `mobile_research_api35` AVD

Downloads are checksum-verified before extraction. The GUI shows first-run download progress in MiB and percent.

Android Studio is not required.

## Desktop experience

- Native Qt Windows GUI.
- APK selection and automatic package detection.
- Automatic APK installation.
- Headless Android rendered inside the Mobile Research window.
- Mouse, wheel and keyboard input mapped to Android.
- START / STOP research controls.
- Research ZIP history, integrity verification and semantic audit.
- Diagnostics showing ADB, Emulator and aapt2 versions, acceleration state, root and tcpdump readiness.
- One-click Android userdata reset.
- One-click managed Android component repair without deleting research data.

## Evidence guarantees preserved from v0.1.0

v0.2.0 does not weaken the research core:

- immutable raw evidence
- device/package metadata
- continuous logcat
- chunked screen recording
- mandatory raw PCAP for AVD-RESEARCH
- complete / partial / failed session semantics
- SHA-256 Research ZIP
- post-export integrity verification
- semantic lifecycle/timeline/evidence audit

If an active GUI research run encounters an unexpected runtime error, Mobile Research makes a best-effort attempt to stop active collectors and preserve a partial/failed Research ZIP instead of abandoning captured evidence.

## Release validation

The exact release commit must pass all of the following before publication:

- Windows CI
- Desktop Build
  - unit tests with desktop dependencies
  - live Google Android catalog resolution
  - standalone EXE build
  - standalone self-test
  - GUI smoke-test
  - Inno Setup build
  - installed-application self-test and GUI smoke-test
  - clean Windows managed-Android provisioning acceptance
- Real AVD Research Acceptance on Ubuntu/KVM
  - Android boot
  - root ADB
  - tcpdump/raw PCAP
  - logcat
  - screen recording
  - Research ZIP export and audit

The release workflow publishes only artifacts produced by the successful Desktop Build for the same commit SHA.

## Distribution

Release assets:

- `MobileResearchSetup.exe`
- `SHA256SUMS.txt`

Python is bundled into the application and is not a user dependency.

## Runtime requirements

- Windows desktop
- hardware virtualization enabled
- Windows Hypervisor Platform usable by Android Emulator
- internet access on first provisioning of Android components
- approximately 1.3 GB of Android component downloads on first setup

Mobile Research can best-effort enable required Windows virtualization features. A Windows reboot or BIOS/UEFI virtualization change can still be required by the operating system/hardware.

## Scope boundaries

v0.2.0 does not yet release-accept AVD-PLAY or Physical Device backends. MITM/TLS decryption, static APK analysis, protocol decoding and an Android Research Agent remain future work.
