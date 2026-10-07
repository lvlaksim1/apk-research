# Manager beliefs

## Product baseline and latest release

The product authority is `main`. The current verified product baseline and latest published release are **apk-research v0.29.0** at `81a565dbc3b4c41712b8a6e3c3ba8020060ff5a2`.

Release asset `apk-research-setup_v0.29.0.exe` has SHA-256 `a6277849cc9ced994cb439698f84d3376cadf373fa3358d1e0e8e16b69f216c5` and size 36,475,884 bytes. GitHub Release v0.29.0 was published on 2026-10-07 after main pipeline #139 passed all mandatory release gates for the exact release SHA.

- source: GitHub main, PR #20, main pipeline #139 and GitHub Release v0.29.0, reconciled 2026-10-07
- authority: owner-directive + verified-repository + verified-ci

## Completed roadmap through v0.29

- v0.18.0: Raw / Packet Inspector.
- v0.19.0: Android sidecar foundation.
- v0.20.0: Continuous Screen foundation.
- v0.21.0: interaction completeness.
- v0.22.0: Packet ↔ Action temporal evidence.
- v0.23.0: Transport Session Evidence.
- v0.23.1: Sidecar isolation + idle stability.
- v0.24.0: Unified Session Evidence.
- v0.25.0: Transport and Protocol Analysis.
- v0.26.0: Investigator Workspace.
- v0.27.0: APK/XAPK package intake.
- v0.28.0: verified direct GitHub self-update.
- v0.29.0: application icon, ABI-aware XAPK install, explicit emulator app controls, and in-place update mode.

## v0.29 corrective behavior

The desktop UI separates file selection from installation and exposes explicit controls to install into the emulator, launch the installed app, and open the Android home screen.

XAPK installation is ABI-aware: emulator ABI properties are read before installation; APK native-code metadata is parsed with aapt2; incompatible ABI splits are excluded; genuinely incompatible packages are rejected with explicit package/emulator ABI diagnostics instead of surfacing raw INSTALL_FAILED_NO_MATCHING_ABIS.

The Windows package now uses a project-owned icon across the Qt window, executable, installer and resulting shortcuts.

Self-update remains SHA-256 verified, but the installer is now explicitly invoked in update mode and reuses the existing installation location/tasks under the same AppId rather than uninstalling first.

## Protected semantics/runtime

Research capture, Research ZIP schemas, RAW PCAP authority, evidence semantics, hidden Emulator → gRPC/MMAP → AndroidView, v0.10.5 startup sequencing and the accepted dual-source screen model are unchanged. Audio Evidence and user-facing Virtual Display remain out of scope. WHPX remains advisory/non-publication-gating.
