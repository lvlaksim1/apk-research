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

## v0.38.2 release documentation gate — verified rule

Before the next release, synchronize the version in `README.md`, `REFACTORING.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `pyproject.toml`, and `src/apk_research/__init__.py`. The Publish Release job checks the document strings and refuses publication if any required version entry is missing. This blocked the first v0.38.2 release attempt #38602120990. The corrected final complete pipeline #38604038134 succeeded.

A transient Android ADB 255 failure requires examining the job log and bounded retest, not bypassing a required acceptance gate; v0.38.2 passed on a repeated AVD check.

- provenance: verified GitHub Actions logs and final published v0.38.2, 2026-10-14
- authority: verified repository procedure

- source: legacy-v2-state
