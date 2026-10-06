# Current Project State

Last reconciled: 2026-10-07.

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

## Owner-side v0.23.1 revalidation

Archive `20261006T230500.602195Z-1206ec46.research.zip` passed the real owner-side defect revalidation:
- 31/31 checksums valid; session complete and not degraded;
- Continuous Screen completed with 1,613 decoded frames over 131.195188 s and survived a real 59.005490 s no-frame interval before resuming;
- canonical screenrecord shows the same static period as a 60.001711 s frame gap and completed with 925 frames over 132.671076 s;
- 21,787 Sidecar packets are preserved in RAW PCAP but excluded from all 32 normalized app flows and from action correlations;
- post-idle evidence matches the canonical recording.

This closes the two v0.23.0 owner-proven Sidecar defects.

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

Hidden Emulator → gRPC/MMAP → AndroidView and v0.10.5 clean-launch sequencing remain unchanged. Canonical screenrecord remains authoritative. Continuous Screen remains experimental/non-canonical pending one owner-side session that crosses the 170 s screenrecord chunk boundary and an explicit promotion decision.

## Development status

v0.23.1 is complete, published and owner-revalidated for the two corrective defects. No v0.24 implementation is active. The immediate open item is the final Continuous Screen promotion gate across a canonical screenrecord chunk rollover.

Audio Evidence and Virtual Display remain out of scope.
