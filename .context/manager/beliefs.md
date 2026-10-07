# Manager beliefs

## Product baseline and latest release

The product authority is `main`. The current verified product baseline and latest published release are **apk-research v0.27.0** at commit `f6a39f21583273f91b192d14fa258bc1e7613a93`.

Release asset `apk-research-setup_v0.27.0.exe` has SHA-256 `19d5ca4fe75ed24bd65d1f89e70c56c0e89e91b9ee9894b44722ea0535834e34` and size 36,414,204 bytes. GitHub Release v0.27.0 was published on 2026-10-07 for the exact release SHA after main pipeline #137 passed CI, real AVD Research ZIP acceptance, real XAPK install acceptance, Windows standalone/self-test/GUI/installer checks and clean-Windows managed Android provisioning.

The first post-merge publication attempt at `a89a11db586ae2254e2dfffdd5744fca3ce5d912` failed only at the release-documentation gate. Product/AVD/Windows gates were already green. Commit `f6a39f21583273f91b192d14fa258bc1e7613a93` corrected the release contract (REFACTORING documentation and package version declaration), after which pipeline #137 passed and published v0.27.0.

- source: GitHub main, PR #18, main pipelines and GitHub Release v0.27.0, reconciled 2026-10-07
- authority: verified-repository + verified-ci

## Completed roadmap through v0.27

- v0.18.0: Raw / Packet Inspector.
- v0.19.0: Android sidecar foundation.
- v0.20.0: Continuous Screen foundation.
- v0.21.0: interaction completeness.
- v0.22.0: Packet ↔ Action temporal evidence.
- v0.23.0: Transport Session Evidence.
- v0.23.1: Sidecar infrastructure isolation + idle stability.
- v0.24.0: Unified Session Evidence.
- v0.25.0: Transport and Protocol Analysis.
- v0.26.0: Investigator Workspace.
- v0.27.0: first-class APK/XAPK package intake.

## v0.27 APK/XAPK intake

The owner authorized XAPK support as the next product stage. v0.27.0 accepts both APK and XAPK from the desktop UI.

XAPK is treated as an untrusted ZIP container:
- only APK/OBB payloads are materialized;
- unsafe traversal paths and encrypted members are rejected;
- all APK parts are inspected with aapt2;
- exactly one base APK is required;
- split APKs must share package name and versionCode;
- duplicate split names and mixed-package bundles are rejected;
- multi-part packages install with `adb install-multiple`;
- OBB files are copied only after successful APK installation to `/sdcard/Android/obb/<package>`;
- ordinary single APK retains the established single-`adb install` path.

Main pipeline #137 includes an explicit real-AVD XAPK installation acceptance step and it passed.

## Evidence semantics and protected runtime

Raw PCAP remains authoritative. Action ↔ Flow and Packet ↔ Action remain temporal-only with `causal_claim=false`. Screen links remain time-aligned and non-causal. Protocol analysis remains captured-packets-only. Investigator organization metadata is not evidence.

The accepted dual-source screen model remains active. Hidden Emulator → gRPC/MMAP → AndroidView and v0.10.5 startup/clean-launch sequencing remain protected. Audio Evidence and user-facing Virtual Display remain out of scope. WHPX remains advisory/non-publication-gating.
