# Current Project State

Last reconciled: 2026-10-07.

## Product

- Product: `apk-research`.
- Product authority: `main`.
- Current release/main commit: `f6a39f21583273f91b192d14fa258bc1e7613a93`.
- Latest published release: `v0.27.0`.
- Installer: `apk-research-setup_v0.27.0.exe`.
- Installer SHA-256: `19d5ca4fe75ed24bd65d1f89e70c56c0e89e91b9ee9894b44722ea0535834e34`.
- Installer size: 36,414,204 bytes.
- Release published: 2026-10-07T04:27:24Z.

## v0.27.0 — APK/XAPK Package Intake

v0.27.0 is complete and published.

Delivered:
- APK/XAPK selection in the desktop UI;
- safe XAPK extraction;
- exact package/version/split validation through aapt2;
- one-base requirement and duplicate/mixed-package rejection;
- split installation through `adb install-multiple`;
- OBB deployment to the installed package directory;
- regression-preserved single-APK installation.

## Verified release state

PR #18 final SHA `72b713496e46fb3f5b1c1c30fafa46eee9fb5051` passed CI, repository storage policy, real AVD acceptance and Windows desktop checks.

The first main publication attempt at `a89a11db586ae2254e2dfffdd5744fca3ce5d912` failed only at `Verify release documentation`. The corrective commit `f6a39f21583273f91b192d14fa258bc1e7613a93` updated the missing release contract. Main pipeline #137 then passed:
- CI/compile/tests;
- real XAPK installation on AVD;
- real Research ZIP AVD acceptance;
- Windows standalone/self-test/GUI;
- installer build/install/smoke;
- clean-Windows Android provisioning;
- checksum verification and GitHub Release publication.

## Protected evidence/runtime baseline

All v0.24-v0.26 evidence semantics remain unchanged. Hidden Emulator → gRPC/MMAP → AndroidView, v0.10.5 clean-launch sequencing and the accepted dual-source screen model remain protected.

## Development status

v0.27.0 is the current verified baseline. No subsequent feature stage is active.
