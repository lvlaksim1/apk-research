# Manager beliefs

## Product baseline and latest release

The product authority is `main`. The current verified product baseline and latest published release are **apk-research v0.29.1** at `ae4450ba662299c30199742ba4b1d2bbcdb27601`.

Release asset `apk-research-setup_v0.29.1.exe` has SHA-256 `f853d8672dd4f0c5e80ed39c4b538d38d25b52ea6be8a1cbee3ba03f3e194e49` and size 36,474,197 bytes. GitHub Release v0.29.1 was published on 2026-10-07 after main pipeline #140 passed all mandatory release gates for the exact release SHA.

- source: GitHub main, PR #21, main pipeline #140 and GitHub Release v0.29.1, reconciled 2026-10-07
- authority: owner-directive + verified-repository + verified-ci

## Completed roadmap through v0.29.1

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
- v0.29.0: icon, ABI-aware XAPK install, explicit emulator controls, in-place update mode.
- v0.29.1: reliable self-update process handoff.

## v0.29.1 updater correction

Owner-side validation showed that v0.28/v0.29 could discover, download and verify a release, announce restart, exit, and then fail silently before installer execution. Root cause was architectural: post-exit work was delegated to a hidden PowerShell relay, so relay failure became invisible after the GUI closed.

v0.29.1 removes that relay. The verified Inno Setup executable is launched directly before the GUI exits. Inno Setup owns the successful relaunch of apk-research after updating the same installation directory. Persistent handoff and installer logs are written under local application data.

Windows CI now reproduces the owner failure boundary by installing published v0.29.0, invoking the production updater from a short-lived Python process, allowing that process to exit, and then checking no faster than every five seconds that the installed executable reports v0.29.1. This acceptance passed.

The first release-pipeline AVD attempt had one unrelated Continuous Screen `failed-experimental` result while the session itself completed, ZIP validation passed, XAPK acceptance passed and Packet Inspector passed. The exact AVD job was rerun and passed. Treat the first result as a transient/non-reproduced screen-collector failure, not as evidence of a v0.29.1 updater defect.

## Protected semantics/runtime

Research capture, Research ZIP schemas, RAW PCAP authority, evidence semantics, hidden Emulator → gRPC/MMAP → AndroidView, v0.10.5 startup sequencing and the accepted dual-source screen model are unchanged. Audio Evidence and user-facing Virtual Display remain out of scope. WHPX remains advisory/non-publication-gating.
