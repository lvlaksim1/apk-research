# Current Project State

Last reconciled: 2026-10-07.

## Product

- Product: `apk-research`.
- Product authority: `main`.
- Current release/main commit: `81a565dbc3b4c41712b8a6e3c3ba8020060ff5a2`.
- Latest published release: `v0.29.0`.
- Installer: `apk-research-setup_v0.29.0.exe`.
- Installer SHA-256: `a6277849cc9ced994cb439698f84d3376cadf373fa3358d1e0e8e16b69f216c5`.
- Installer size: 36,475,884 bytes.
- Release published: 2026-10-07T14:02:55Z.

## v0.29.0

Complete and published.

Delivered:
- new apk-research icon across the window, EXE, installer and shortcuts;
- ABI-aware XAPK installation based on emulator ABI properties and APK native-code metadata;
- exclusion of incompatible ABI splits before install-multiple;
- clear diagnostics when no compatible ABI exists;
- explicit «Установить в эмулятор», «Запустить приложение» and «Открыть главный экран Android» controls;
- explicit in-place update mode preserving previous installation directory/tasks under the same AppId without uninstall-first behavior.

## Verified release state

Main pipeline #139 passed all mandatory gates on exact SHA `81a565dbc3b4c41712b8a6e3c3ba8020060ff5a2`:
- CI/compile/tests;
- real XAPK installation acceptance;
- real AVD Research ZIP acceptance;
- Windows standalone/self-test/GUI;
- installer build/install/smoke;
- clean-Windows managed Android provisioning;
- release publication and temporary-artifact cleanup.

WHPX remains separate/advisory and is not a publication gate.

## Protected baseline

Research capture, evidence semantics, Research ZIP, RAW PCAP authority, hidden Emulator → gRPC/MMAP → AndroidView, v0.10.5 clean-launch sequencing and dual-source screen evidence are unchanged.

## Development status

v0.29.0 is the current verified baseline. No subsequent feature stage is active.
