# Current Project State

Last reconciled: 2026-10-07.

## Product

- Product: `apk-research`.
- Product authority: `main`.
- Current release/main commit: `176dc1f1302c729456fc0d5711d0e5879e36837e`.
- Latest published release: `v0.24.0`.
- Installer: `apk-research-setup_v0.24.0.exe`.
- Installer SHA-256: `f1ee0ec8e60345b17a21d00c8a5f4b4f616c8ed6c1aca24714f92eb912cb2c3c`.
- Installer size: 36,355,696 bytes.
- Release published: 2026-10-07T01:43:15Z.

## v0.24.0 — Unified Session Evidence

v0.24.0 is complete and published.

Delivered:
- `Session Evidence` chronological cross-navigation view;
- screen ↔ action ↔ normalized flow ↔ packet ↔ process/socket ↔ raw evidence navigation;
- reverse Process/Socket → all related flows index;
- Packet → Evidence and Packet → screen navigation;
- Timeline/Evidence → screen/session navigation;
- Continuous Screen device-PTS → target-UTC locator using archived screenrecord realtime↔elapsed timing;
- explicit relation type/strength and `causal_claim=false` boundaries;
- Continuous Screen metadata promoted to stable continuous/timeline role while Android screenrecord remains high-resolution companion evidence.

## Verified release state

Main pipeline #133 (`37558075676`) completed SUCCESS for exact SHA `176dc1f1302c729456fc0d5711d0e5879e36837e`:
- CI/compile/tests passed;
- real AVD Research ZIP acceptance passed;
- Windows standalone build, self-test and GUI smoke passed;
- v0.24.0 installer build/install/smoke passed;
- clean-Windows managed Android provisioning passed;
- release documentation and installer checksum passed;
- GitHub Release v0.24.0 was published;
- temporary installer artifacts were cleaned up.

## Protected evidence/runtime baseline

- Raw PCAP remains authoritative network evidence.
- Action ↔ Flow and Packet ↔ Action remain temporal-only, `causal_claim=false`.
- Screen navigation is time-aligned, not causal.
- Process/socket reverse indexing does not upgrade attribution confidence.
- Hidden Emulator → gRPC/MMAP → AndroidView remains the live display path.
- v0.10.5 clean-launch/startup sequencing remains protected.
- Continuous Screen is stable continuous/timeline evidence; Android screenrecord remains high-resolution evidence.
- Audio Evidence and user-facing Virtual Display remain out of scope.

## Development status

No v0.25 implementation is active at this release checkpoint. v0.25 remains the next agreed roadmap stage.
