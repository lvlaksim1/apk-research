# Procedural Memory

## Real Research ZIP acceptance procedure

For a real user archive, verify ZIP/checksums, session completion/degraded/errors, collector status, app launch, PCAP captured/drop accounting, normalized flow packet/byte accounting, Timeline↔flow forward/reverse links, socket attribution, protocol-specific evidence (including QUIC/HTTP3 when present), and consistency of GUI-derived evidence with raw sources.

- source: repeated apk-research real-archive acceptance workflow through v0.16.1
- authority: verified-project-procedure

## Release procedure

For a release-bound change, develop on a feature/fix branch, run regression tests, clean temporary verification files, create a release commit on `main`, and let the commit-triggered pipeline perform CI, real AVD acceptance, Windows build/smoke, clean-Windows provisioning and Publish Release. Verify the published asset/version/hash before reporting completion.

- source: repository main pipeline and successful releases through v0.17.0
- authority: verified-repository

## Context persistence procedure

Durable manager updates go to the permanent `context` branch, not feature branches. Keep `main` discovery-only for Context Capsule. When coupled BDI/current/handoff files change, recompute and atomically publish the state-integrity seal.

- source: canonical Context Capsule install protocol and owner-approved bootstrap
- authority: verified-core-protocol
