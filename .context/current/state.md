# Current Project State

Last reconciled: 2026-10-07.

## Product

- Product: `apk-research`.
- Product authority: `main`.
- Current release/main commit: `df2faf74a707cf99afa366433c34dc89cec37dcc`.
- Latest published release: `v0.28.0`.
- Installer: `apk-research-setup_v0.28.0.exe`.
- Installer SHA-256: `9c5444503b6306497ebe5acac87040830d0eefa2fbdb16c06cd521b50f8bd61e`.
- Installer size: 36,436,053 bytes.
- Release published: 2026-10-07T12:31:51Z.

## v0.28.0 — Direct GitHub Self-Update

Complete and published.

Settings now expose manual update discovery. A newer stable release reveals a separate update button. Download is direct from the public project GitHub Release and requires both the exact versioned installer and `SHA256SUMS.txt`. Local SHA-256 and release-size verification occur before installer launch.

A detached Windows process waits for the running application to close, updates the same installation directory with the verified Inno Setup installer, and restarts apk-research.

No background update polling is performed.

## Verified release state

Main pipeline #138 executed for exact SHA `df2faf74a707cf99afa366433c34dc89cec37dcc` and passed:
- CI/compile/tests;
- real XAPK install acceptance;
- real AVD Research ZIP acceptance;
- Windows standalone/self-test/GUI;
- installer build/install/smoke;
- clean-Windows managed Android provisioning;
- checksum verification;
- GitHub Release publication and temporary-artifact cleanup.

`releases/latest` resolves to v0.28.0 and exposes the expected installer and checksum file.

## Protected baseline

v0.27 APK/XAPK intake and all evidence/runtime semantics are unchanged. Hidden Emulator → gRPC/MMAP → AndroidView, v0.10.5 clean-launch sequencing, RAW PCAP authority and dual-source screen evidence remain protected.

## Development status

v0.28.0 is the current verified baseline. No subsequent feature stage is active.
