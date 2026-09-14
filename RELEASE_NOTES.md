# Mobile Research v0.2.0rc1

First desktop **Release Candidate**.

This build moves Mobile Research from the v0.1 command-line research core to a self-contained Windows application with a managed Android research runtime.

## User experience

Normal use does not require installing Python, Android Studio, ADB, sdkmanager or a separate Android Emulator.

Expected flow:

```text
install MobileResearchSetup.exe
→ launch Mobile Research
→ accept the Android SDK license once
→ Mobile Research downloads its managed Android components
→ choose an APK
→ START RESEARCH
→ interact with Android inside Mobile Research
→ STOP / SAVE
→ verified Research ZIP
```

Managed Android components live under:

```text
%LOCALAPPDATA%\MobileResearch\components
```

The first Android setup downloads roughly 1.3 GB of official Google packages.

## Included

- Native Windows GUI.
- Self-contained Python/Qt runtime packaged with PyInstaller.
- Per-user Inno Setup installer.
- Managed ADB, Android Emulator, aapt2 and Android 15 / API 35 AOSP system image.
- Private AVD created without Android Studio.
- Integrated Android framebuffer with tap, swipe, wheel, keyboard and text input.
- Automatic APK package-name detection and installation.
- Existing v0.1 ResearchOrchestrator exposed through GUI START/STOP.
- Raw PCAP, logcat, screen recording and device/package metadata.
- Complete / partial / failed session semantics.
- Verified Research ZIP and semantic evidence audit.
- Session history, archive verification and diagnostics UI.

## Android component policy

Mobile Research now follows the Android SDK stable repository channel only.

The exact RC acceptance resolved:

- Android Emulator **37.1.11.0**, build **15917651**
- Android platform-tools / ADB **37.0.1**
- build-tools **35.0.0**
- Android 15 / API 35 default x86_64 AOSP image

Beta, dev and canary Emulator packages are not selected by normal provisioning.

## Automated acceptance

The exact release commit must pass all three release gates before publication:

1. **CI**
   - compile
   - complete pytest suite

2. **Desktop Build**
   - live Google Android repository resolution
   - standalone Windows EXE build
   - standalone self-test
   - offscreen GUI smoke-test
   - Inno Setup build
   - silent installation of the generated Setup.exe
   - installed EXE self-test and GUI smoke-test
   - clean-Windows Android provisioning
   - checksum verification and private AVD validation

3. **AVD Research Acceptance**
   - real hardware-accelerated Android boot on Linux/KVM
   - root ADB
   - tcpdump availability
   - real research session
   - raw PCAP, logcat and screen evidence
   - Research ZIP verification and semantic audit

## Why this is an RC

GitHub-hosted Windows runners do not provide a reliable hardware-accelerated Android environment. Software x86_64 emulation is therefore not used as a release-quality Windows boot gate.

The remaining RC validation is intentionally performed on a real Windows machine with hardware virtualization / Windows Hypervisor Platform:

- managed Android first boot;
- root ADB readiness;
- embedded Android display and input;
- APK installation;
- full START → research → STOP → Research ZIP workflow.

This RC is not the final v0.2.0 until that real Windows/WHPX path is confirmed.

## Distribution

Release assets:

- `MobileResearchSetup.exe`
- `SHA256SUMS.txt`

No Python installation is required on the user's computer.
