# Current Project State

Last reconciled: 2026-10-06.

## Product

- Product: `apk-research`.
- Product authority: `main`.
- Current release/main commit: `250c507ca3302558ba11d5df57d3129a38ad6fbe`.
- Latest published release: `v0.21.0`.
- Installer: `apk-research-setup_v0.21.0.exe`.
- Installer SHA-256: `2d655d007b67f5d1c6f866505b9865d300caa6f951e5c90f53af83d7c862d648`.
- Published: 2026-10-06T02:29:31Z.

## Verified progression since previous manager checkpoint

- v0.19.0: Android sidecar foundation released.
- v0.20.0: experimental continuous screen evidence released; canonical screenrecord retained.
- v0.21.0: interaction completeness released.
- Main pipeline #124 for v0.21.0 completed SUCCESS and published the release.

## Current runtime/evidence baseline

The proven hidden Emulator → gRPC/MMAP → AndroidView display path and v0.10.5 startup/clean-launch sequencing remain unchanged. Persistent gRPC input now supports geometry-safe two-pointer gestures.

Research evidence includes canonical screenrecord, raw PCAP, logcat, socket/process attribution, Timeline, normalized flows, QUIC/HTTP3 evidence, Unified Evidence Explorer and Raw/Packet Inspector. Experimental continuous-screen H.264/device-PTS evidence is additive and non-canonical.

## Active development stage

Stage E — deeper evidence intelligence.

Immediate target: v0.22 Packet ↔ Action temporal evidence and direct Packet → Timeline navigation using the existing canonical Timeline action windows. This is presentation/derived analysis only; it must preserve `temporal-only` and `causal_claim=false`.

No v0.22 product code has been committed yet at this checkpoint.

## Scope exclusions

Audio Evidence and Virtual Display remain out of scope.
