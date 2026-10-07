# Current Project State

Last reconciled: 2026-10-07.

## Product

- Product: `apk-research`.
- Product authority: `main`.
- Current release/main commit: `cbf6d177e67cd56e980319ab654da2f27a73176a`.
- Latest published release: `v0.26.0`.
- Installer: `apk-research-setup_v0.26.0.exe`.
- Installer SHA-256: `f5ce59d8c51263fd61d425422ee4e3f5a471592c35d1a19f9a1317161e8affb6`.
- Installer size: 36,409,960 bytes.
- Release published: 2026-10-07T03:32:51Z.

## v0.26.0 — Investigator Workspace

v0.26.0 is complete and published.

Delivered:
- dedicated Investigator workspace over v0.24/v0.25 evidence;
- global search and intersecting filters by time/event/protocol/process/endpoint/action/evidence class;
- stable `EV-...` navigation references;
- bookmarks and named evidence sets stored outside Research ZIP;
- reverse navigation to Session Evidence, Timeline, Evidence Explorer, Packet Inspector and screen context;
- Markdown/JSON report export retaining EV/source navigation identifiers;
- explicit preservation of relation type/strength and `causal_claim`.

## Verified release state

Main pipeline #135 executed for exact SHA `cbf6d177e67cd56e980319ab654da2f27a73176a`:
- CI/compile/tests passed;
- real AVD Research ZIP acceptance passed;
- Windows standalone build, self-test and GUI smoke passed;
- v0.26.0 installer build/install/smoke passed;
- clean-Windows managed Android provisioning passed;
- release publication produced GitHub Release v0.26.0.

## Protected evidence/runtime baseline

- Raw PCAP remains authoritative network evidence.
- Action ↔ Flow and Packet ↔ Action remain temporal-only, `causal_claim=false`.
- Screen navigation remains time-aligned, not causal.
- v0.25 protocol analysis remains captured-packets-only.
- Investigator EV references and reports are navigation/analyst-organization metadata, not new evidence.
- Hidden Emulator → gRPC/MMAP → AndroidView remains the live display/input path.
- v0.10.5 clean-launch/startup sequencing remains protected.
- Continuous Screen is stable continuous/timeline evidence; Android screenrecord remains high-resolution evidence.
- Audio Evidence and user-facing Virtual Display remain out of scope.

## Development status

The agreed `v0.24 → v0.25 → v0.26` roadmap is complete. No v0.27 implementation or other new roadmap stage is active.
