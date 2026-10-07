# Current Project State

Last reconciled: 2026-10-07.

## Product

- Product: `apk-research`.
- Product authority: `main`.
- Current release/main commit: `ae4450ba662299c30199742ba4b1d2bbcdb27601`.
- Latest published release: `v0.29.1`.
- Installer: `apk-research-setup_v0.29.1.exe`.
- Installer SHA-256: `f853d8672dd4f0c5e80ed39c4b538d38d25b52ea6be8a1cbee3ba03f3e194e49`.
- Installer size: 36,474,197 bytes.
- Release published: 2026-10-07T14:37:24Z.

## v0.29.1

Complete and published.

Fixes the owner-reported automatic-update handoff failure. The updater no longer depends on a hidden PowerShell process after GUI exit. It starts the already verified Inno Setup package directly, then exits; Inno Setup updates the existing installation and relaunches apk-research itself.

Persistent logs:
- `%LOCALAPPDATA%\apk-research\updates\handoff.log`;
- `%LOCALAPPDATA%\apk-research\updates\installer.log`.

## Verified release state

PR #21 passed CI, updater unit/contract tests, real Windows upgrade acceptance and clean-Windows provisioning.

Main pipeline #140 passed for exact SHA `ae4450ba662299c30199742ba4b1d2bbcdb27601` after one AVD job rerun. The first AVD attempt had an unrelated/non-reproduced Continuous Screen `failed-experimental` status; the session itself completed and validated. The exact AVD rerun passed.

The release includes checksum verification and GitHub Release publication.

## Protected baseline

v0.29 icon/XAPK/emulator-control behavior and all evidence/runtime semantics remain unchanged.

## Development status

v0.29.1 is the current verified baseline. No subsequent feature stage is active.
