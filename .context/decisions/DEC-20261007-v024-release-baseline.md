# DEC-20261007 — v0.24.0 release baseline

Status: accepted.

## Decision

Adopt `apk-research v0.24.0` at product commit `176dc1f1302c729456fc0d5711d0e5879e36837e` as the verified product baseline.

The release introduces Unified Session Evidence as a presentation/navigation layer over existing evidence:
- Session Evidence chronological cross-navigation;
- screen ↔ action ↔ normalized flow ↔ packet ↔ process/socket ↔ raw navigation;
- reverse process/socket → related flows index;
- Continuous Screen target-time navigation derived from archived device realtime↔elapsed timing;
- owner-approved stable Continuous Screen timeline role with high-resolution Android screenrecord retained.

Evidence semantics remain bounded: RAW PCAP is authoritative; Action↔Flow and Packet↔Action remain temporal-only with `causal_claim=false`; screen links are time-aligned navigation, not causal inference; process/socket reverse indexing does not upgrade attribution confidence.

## Verification

Main pipeline #133 (`37558075676`) completed SUCCESS for the exact release SHA. It passed CI, real AVD Research ZIP acceptance, Windows standalone/self-test/GUI smoke, installer install/smoke, clean-Windows managed Android provisioning, release-document validation, installer checksum verification and GitHub Release publication.

Published installer: `apk-research-setup_v0.24.0.exe`.
SHA-256: `f1ee0ec8e60345b17a21d00c8a5f4b4f616c8ed6c1aca24714f92eb912cb2c3c`.
Size: 36,355,696 bytes.
Release published: 2026-10-07T01:43:15Z.

## Authority

- owner directive to execute/deliver v0.24.0;
- verified repository main;
- verified CI/release pipeline;
- published GitHub Release v0.24.0.
