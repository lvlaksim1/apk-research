# Current Project State

Last reconciled: 2026-10-06.

## Product

- Product: `apk-research`.
- Product authority: `main`.
- Current release/main commit: `d58265584223246974fb641f02e0dd3fb8d3f4f1`.
- Latest published release: `v0.22.0`.
- Installer: `apk-research-setup_v0.22.0.exe`.
- Installer SHA-256: `d6f7ae647d755455a374189a3731e15057fc74ec88c4b9a846143145ebb0ae8a`.
- Installer size: 36,311,844 bytes.
- Release published: 2026-10-06T02:57:41Z.

## v0.22.0 — Packet ↔ Action Evidence

Packet Inspector now reads the archived Research Timeline in addition to the raw PCAP. For a selected flow, a packet receives an Action-window relation only when:
1. the archived action correlation references the same `flow_id`; and
2. the packet target timestamp lies inside that archived action target-time window.

The Packets GUI exposes Action-window labels/search/details and direct Packet → Timeline navigation. Relations remain `temporal-only`, `causal_claim=false`; no new evidence artifact/schema was introduced.

## Verified release state

Main pipeline #125 (`37406246024`) completed SUCCESS for exact SHA `d58265584223246974fb641f02e0dd3fb8d3f4f1`:
- CI/compile/tests passed;
- real AVD, gRPC and sidecar checks passed;
- real Research Session and generated Research ZIP acceptance passed;
- packet/action correlation invariants passed against the generated archive;
- Windows standalone build/self-test/GUI smoke passed;
- v0.22 installer build/install/smoke passed;
- clean-Windows managed Android provisioning passed;
- release documentation and installer checksum passed;
- GitHub Release v0.22.0 was published.

## Runtime/evidence baseline

The hidden Emulator → gRPC/MMAP → AndroidView runtime and v0.10.5 clean-launch sequencing are unchanged. Canonical screenrecord remains authoritative; continuous-screen evidence remains experimental/non-canonical.

## Development status

Stage E increment 1 is complete. No v0.23 product implementation is active at this checkpoint.

Audio Evidence and Virtual Display remain out of scope.
