# Manager intentions and commitments

## Completed — Continuous Screen stabilization and role selection

Status: completed.

Owner-side v0.23.1 archives proved idle survival, long-session rollover continuity, clean completion and Sidecar network isolation. The owner accepted the dual-source role: Continuous Screen is stable continuous/timeline evidence while Android screenrecord remains high-resolution evidence.

## Completed — v0.24 Unified Session Evidence

Status: completed and released as v0.24.0.

Unified Session Evidence provides chronological cross-navigation across screen, actions, flows, packets, process/socket attribution and RAW evidence while preserving temporal-only and confidence boundaries.

## Completed — v0.25 Transport and Protocol Analysis

Status: completed and released as v0.25.0.

Delivered:
- capture-bounded TCP lifecycle/sequence/ACK/window observations;
- explicit missing-start/missing-end/gap semantics without loss/retransmission overclaim;
- structured DNS messages and conservative ordered transaction pairing;
- observed TLS ClientHello/ServerHello metadata;
- QUIC Initial/SNI/ALPN aggregation and HTTP/3 only when observed;
- cleartext HTTP/1.x and h2c recognition only from directly captured bytes;
- Packet Inspector integration and end-to-end PCAP → analysis verification.

Completion evidence: PR #16 gates passed and GitHub Release v0.25.0 is published for exact SHA `3717210a9db3074569602afc336380fd26598dd7`.

## Active — v0.26 Investigator Workspace

Status: owner-directed execution active.

Build the agreed investigation workspace on top of the verified v0.24/v0.25 evidence model: coherent behavior/session overview, global search and filters, bookmarks/evidence sets, report generation and reverse navigation from report items to evidence. Do not introduce new causal semantics or alter RAW authority.

## Active — continuity and release integrity

Status: active.

Reconcile live `main`, releases and CI before consequential changes; preserve RAW authority, v0.10.5 startup sequencing, gRPC/MMAP display/input and commit-triggered release gates.
