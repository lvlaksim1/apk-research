# Current Project State

Last reconciled: 2026-10-06.

## Product

- Product: `apk-research`.
- Product authority: `main`.
- Current release/main commit: `39e483ee03d5337e4e928b4b85cce85c40f4fe35`.
- Latest published release: `v0.23.1`.
- Installer: `apk-research-setup_v0.23.1.exe`.
- Installer SHA-256: `b5bf2d31da1c47ef59d351988a09f5c0dad72a8117aab0c4849ae30bb54eb540`.
- Installer size: 36,323,501 bytes.
- Release published: 2026-10-06T12:05:53Z.

## v0.23.1 — Sidecar Evidence Isolation & Idle Stability

The owner-proven v0.23.0 defects are corrected:
- exact Sidecar control/media loopback packets remain in raw PCAP but are excluded from ordinary app flow inventory, Timeline network markers and Packet/Action correlations;
- derived evidence reports explicit infrastructure packet/byte accounting;
- the established media stream is long-lived/blocking instead of inheriting the generic 8 s handshake timeout.

Real-AVD acceptance deliberately keeps the screen idle for 10 seconds, then requires Continuous Screen to complete cleanly and requires no Sidecar loopback flow in normalized app evidence.

## Verified release state

Main pipeline #127 (`37460233667`) completed SUCCESS for exact SHA `39e483ee03d5337e4e928b4b85cce85c40f4fe35`:
- CI/compile/tests passed;
- real AVD Research ZIP acceptance passed including 10 s idle regression and infrastructure-flow isolation;
- Windows standalone build/self-test/GUI smoke passed;
- v0.23.1 installer build/install/smoke passed;
- clean-Windows managed Android provisioning passed;
- release documentation and installer checksum passed;
- GitHub Release v0.23.1 was published.

## Runtime/evidence baseline

Hidden Emulator → gRPC/MMAP → AndroidView and v0.10.5 clean-launch sequencing remain unchanged. Canonical screenrecord remains authoritative. Continuous Screen remains experimental/non-canonical despite the corrective release.

## Development status

v0.23.1 is complete and published. No v0.24 implementation is active at this checkpoint.

Audio Evidence and Virtual Display remain out of scope.
