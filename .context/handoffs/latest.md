# Latest Handoff

Generation: 16
Date: 2026-10-07

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

Verified product baseline is **apk-research v0.26.0** at `cbf6d177e67cd56e980319ab654da2f27a73176a`.

Installer: `apk-research-setup_v0.26.0.exe`.
SHA-256: `f5ce59d8c51263fd61d425422ee4e3f5a471592c35d1a19f9a1317161e8affb6`.
Size: 36,409,960 bytes.
Release published: 2026-10-07T03:32:51Z.

Main pipeline #135 executed on the exact release SHA. CI, real AVD Research ZIP acceptance, Windows standalone/self-test/GUI smoke, installer build/install/smoke and clean-Windows Android provisioning passed before publication.

v0.26.0 delivers Investigator Workspace:
- global investigation search and intersecting filters;
- stable EV navigation references;
- bookmarks and named evidence sets outside immutable Research ZIP;
- reverse navigation to Session Evidence / Timeline / Evidence / Packets / screen;
- Markdown/JSON report export retaining source-navigation identifiers;
- no evidence-strength or causal upgrade.

The owner-agreed three-stage roadmap `v0.24 → v0.25 → v0.26` is complete.

Protected semantics:
- raw PCAP is authoritative;
- Action ↔ Flow and Packet ↔ Action remain `temporal-only`, `causal_claim=false`;
- screen links are time-aligned navigation, not causality;
- protocol analysis remains `captured-packets-only`;
- EV references/bookmarks/sets/reports are analyst navigation/organization metadata, not new evidence;
- hidden Emulator → gRPC/MMAP → AndroidView remains live display/input;
- v0.10.5 startup/clean-launch sequencing remains protected;
- Continuous Screen is stable continuous/timeline evidence; Android screenrecord remains high-resolution evidence;
- Audio Evidence and user-facing Virtual Display remain out of scope.

No v0.27 implementation or other new roadmap stage is active. Await the owner's next development direction.
