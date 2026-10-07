# Latest Handoff

Generation: 17
Date: 2026-10-07

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

Verified product baseline is **apk-research v0.27.0** at `f6a39f21583273f91b192d14fa258bc1e7613a93`.

Installer: `apk-research-setup_v0.27.0.exe`.
SHA-256: `19d5ca4fe75ed24bd65d1f89e70c56c0e89e91b9ee9894b44722ea0535834e34`.
Size: 36,414,204 bytes.
Release published: 2026-10-07T04:27:24Z.

v0.27.0 adds first-class APK/XAPK intake:
- unified file selection;
- safe XAPK extraction;
- one base APK + compatible split validation through aapt2;
- `adb install-multiple` for split packages;
- optional OBB deployment after successful APK installation;
- preserved single-APK path;
- rejection of unsafe/ambiguous bundles.

PR #18 final gates passed. The first post-merge release attempt failed only at release-documentation verification. Corrective commit `f6a39f21583273f91b192d14fa258bc1e7613a93` fixed the release contract. Main pipeline #137 then passed CI, explicit real XAPK installation on AVD, normal Research ZIP AVD acceptance, Windows desktop/installer checks, clean-Windows provisioning, checksum verification and publication.

Protected semantics/runtime remain unchanged:
- raw PCAP authority;
- temporal-only/non-causal action/network links;
- captured-packets-only protocol analysis;
- analyst-only EV/report organization;
- hidden Emulator → gRPC/MMAP → AndroidView;
- v0.10.5 startup sequencing;
- dual-source screen model.

No v0.28 or later feature stage is active. Await owner direction.
