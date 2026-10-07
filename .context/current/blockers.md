# Current Blockers and Unknowns

Last reconciled: 2026-10-07.

## Product blockers

No known release-blocking defect is active. v0.27.0 is published and all release gates passed on exact SHA `f6a39f21583273f91b192d14fa258bc1e7613a93`.

## XAPK scope boundary

Current XAPK support covers ordinary XAPK containers carrying one base APK, compatible split APKs and optional OBB files. Ambiguous, malformed, mixed-package, encrypted, traversal-bearing or structurally unsafe bundles are intentionally rejected rather than guessed.

Other bundle formats such as APKS/APKM are not implied by XAPK support and are not currently in scope unless explicitly authorized.

## Continuous Screen

No current stability blocker. Dual-source screen role remains accepted.

## WHPX

WHPX remains advisory/non-publication-gating.
