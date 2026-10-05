# Current Project State

Last reconciled: 2026-10-06.

## Product

- Product: `apk-research`.
- Product authority branch: `main`.
- Product code baseline before Context Capsule discovery bootstrap: `202d42fcfcccf03e0a9189a1a97f6e57be3578b8`.
- Latest published release: `v0.17.0`, targeting the same commit.
- Release installer: `apk-research-setup_v0.17.0.exe`.
- Installer SHA-256: `cdf5b5697f2c5af4d64d6d47f5c81326115b898929c4708e55082d68dce65b67`.

The paired discovery bootstrap commit added by the Project Manager installation changes repository context discovery only; it is not a product-code release.

## Verified release state

Main pipeline #118 completed successfully:
- CI/tests passed;
- real AVD research and generated Research ZIP verification passed;
- Windows standalone build/self-test/GUI smoke passed;
- installer build/install/smoke passed;
- clean-Windows managed Android provisioning passed;
- GitHub Release publication passed.

The dev suite for v0.17.0 contained 178 passing tests. Context-bootstrap pipeline #119 also completed successfully; product-specific release jobs were correctly skipped for the context-only main change.

## Real-world validation lineage

- v0.16.1 is owner-accepted from a real Research ZIP after the v0.16.0 DNS→QUIC false-positive regression was fixed.
- v0.17.0 was release-gate validated, but no later owner-provided real Research ZIP acceptance is recorded yet.

## Current development direction

A scrcpy v5.0 engineering review was completed against the current apk-research architecture. The owner excluded Audio Evidence and Virtual Display from the roadmap and accepted the remaining useful directions.

The next product focus is evidence depth, not replacement of the stable Emulator runtime:
1. in-app RAW/Packet inspection;
2. project-owned Android-side sidecar foundation;
3. continuous device-PTS screen evidence with A/B validation against current screenrecord;
4. multi-touch and stale-geometry input protection;
5. later evidence intelligence improvements.

No product-code implementation of these stages has started yet.

## Infrastructure note

Separate WHPX acceptance run #112 (`35174782512`) finished `cancelled`. It was not a publication gate and does not invalidate v0.17.0.
