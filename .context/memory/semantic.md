# Semantic Memory

## Proven runtime architecture

The reliable Windows runtime is hidden Emulator → gRPC/MMAP framebuffer → AndroidView with gRPC input; v0.10.5 is the startup/clean-launch sequencing baseline.

- source: apk-research release history and repository documentation through v0.17.0
- authority: verified-repository

## QUIC false-positive lesson

v0.16.0 showed that arbitrary DNS UDP payload bytes can resemble QUIC long headers. v0.16.1 changed the classifier so a supported QUIC v1/v2 flow is established only from authenticated/decrypted Initial evidence, and the observed real DNS prefixes became regressions.

- source: owner-provided real Research ZIP plus v0.16.1 repository fix/tests
- authority: verified-project-evidence

## Unified Evidence Explorer boundary

v0.17.0 Unified Evidence Explorer is presentation-only. It navigates existing Timeline, normalized flows, socket attribution and raw locators; it does not create a new forensic source of truth or upgrade temporal correlation into causality.

- source: v0.17.0 repository implementation and release notes
- authority: verified-repository
