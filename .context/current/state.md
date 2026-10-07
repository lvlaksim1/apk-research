# Current Project State

Last reconciled: 2026-10-07.

## Product

- Product: `apk-research`.
- Product authority: `main`.
- Current release/main commit: `3717210a9db3074569602afc336380fd26598dd7`.
- Latest published release: `v0.25.0`.
- Installer: `apk-research-setup_v0.25.0.exe`.
- Installer SHA-256: `f9a2a92e02b5a1da9f6b8be39d3967a54292d8c04ad20926cba2361f3d560bb7`.
- Installer size: 36,384,738 bytes.
- Release published: 2026-10-07T02:37:51Z.

## v0.25.0 — Transport and Protocol Analysis

v0.25.0 is complete and published.

Delivered:
- TCP capture lifecycle/sequence/ACK/window evidence;
- explicit capture-gap and missing-boundary semantics;
- DNS messages and conservative ordered transaction grouping;
- TLS hello metadata from observed bytes;
- QUIC Initial/SNI/ALPN aggregation and observed HTTP/3 indication;
- cleartext HTTP recognition only where directly captured;
- Packet Inspector protocol-analysis presentation and search integration;
- focused parser tests and PCAP → Packet Inspector → v0.25 end-to-end coverage.

## Protected evidence/runtime baseline

- Raw PCAP remains authoritative network evidence.
- Action ↔ Flow and Packet ↔ Action remain temporal-only, `causal_claim=false`.
- Screen navigation is time-aligned, not causal.
- Process/socket reverse indexing does not upgrade attribution confidence.
- Protocol analysis is `captured-packets-only`; absence is not non-occurrence.
- Sequence gaps/repeated ranges are observations, not automatic loss/retransmission claims.
- Encrypted application payload is never synthesized as plaintext.
- Hidden Emulator → gRPC/MMAP → AndroidView remains the live display path.
- v0.10.5 clean-launch/startup sequencing remains protected.
- Continuous Screen is stable continuous/timeline evidence; Android screenrecord remains high-resolution evidence.
- Audio Evidence and user-facing Virtual Display remain out of scope.

## Development status

v0.26 Investigator Workspace is now the active owner-directed roadmap stage. No capture/runtime redesign is authorized or required.
