# DEC-20261007 — Continuous Screen dual-source product role

Status: accepted.

## Decision

Following successful owner-side idle and >170 s rollover validation, Continuous Screen is promoted out of purely experimental reliability status and becomes the stable continuous/timeline screen-evidence source.

Canonical Android `screenrecord` remains the high-resolution screen-evidence source for now.

The two sources therefore have distinct roles:
- Continuous Screen: uninterrupted temporal coverage, including canonical chunk-rollover gaps;
- canonical screenrecord: higher spatial detail at 1080×1920.

Continuous Screen does not replace the proven hidden Emulator → gRPC/MMAP → AndroidView live display path.

## Rationale

Owner-side v0.23.1 evidence proves Continuous Screen survives long static intervals, crosses canonical screenrecord chunk rotation without a gap, captures interaction inside the canonical rollover blind interval, shuts down cleanly, and keeps Sidecar network traffic isolated from ordinary derived app evidence.

However the current Sidecar capture profile is 540×960 / 2 Mbit/s versus canonical screenrecord at 1080×1920. Sole-source replacement would therefore reduce spatial evidence detail.

Future sole-source replacement remains possible only after raising Continuous Screen capture quality and revalidating performance, archive size, stability and forensic detail.

## Authority

Explicit owner acceptance on 2026-10-07 following presentation of the two owner-side v0.23.1 archive results.
