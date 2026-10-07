# Manager intentions and commitments

## Completed — Continuous Screen stabilization and role selection

Status: completed.

Owner-side v0.23.1 archives proved idle survival, long-session rollover continuity, clean completion and Sidecar network isolation. The owner accepted the dual-source role: Continuous Screen is stable continuous/timeline evidence while Android screenrecord remains high-resolution evidence.

## Completed — v0.24 Unified Session Evidence

Status: completed and released as v0.24.0.

The manager accepted and completed the owner-directed v0.24 work:
- Session Evidence chronological investigation view;
- screen/action/flow/packet/process-socket/raw cross-navigation;
- reverse process/socket attribution index;
- bounded Continuous Screen target-time navigation;
- explicit relation strength and no causal upgrade;
- release packaging and exact-SHA verification.

Completion evidence: PR #15 gates passed; main pipeline #133 (`37558075676`) completed SUCCESS; GitHub Release v0.24.0 is published for exact SHA `176dc1f1302c729456fc0d5711d0e5879e36837e`.

## Proposed — v0.25 Transport and Protocol Analysis

Status: proposed as the next agreed roadmap stage; no v0.25 implementation is active at this checkpoint.

Planned scope includes deeper capture-bounded TCP session analysis and protocol intelligence (DNS/TLS/QUIC/HTTP3 and observable HTTP) without inventing missing packets, plaintext or causality.

## Active — continuity and release integrity

Status: active.

Reconcile live `main`, releases and CI before consequential changes; preserve RAW authority, v0.10.5 startup sequencing, gRPC/MMAP display/input and commit-triggered release gates.
