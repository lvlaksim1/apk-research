# Manager beliefs

## Product baseline and latest release

The product authority is `main`. The current verified product baseline and latest published release are `apk-research v0.22.0` at commit `d58265584223246974fb641f02e0dd3fb8d3f4f1`.

Release asset `apk-research-setup_v0.22.0.exe` has SHA-256 `d6f7ae647d755455a374189a3731e15057fc74ec88c4b9a846143145ebb0ae8a`. Main pipeline #125 (`37406246024`) completed successfully for the exact release SHA, including CI, real AVD Research ZIP acceptance, Windows standalone/GUI/installer smoke, clean-Windows managed Android provisioning, checksum verification and GitHub Release publication.

- source: GitHub repository main, pipeline #125 and GitHub Release v0.22.0, reconciled 2026-10-06
- authority: verified-repository + verified-ci

## Stage A-D baseline

- v0.18.0: Raw / Packet Inspector.
- v0.19.0: project-owned temporary Android app_process sidecar foundation.
- v0.20.0: experimental continuous-screen MediaCodec/device-PTS evidence; canonical screenrecord retained.
- v0.21.0: geometry-safe two-pointer interaction completeness over existing Emulator gRPC input.

- source: verified repository/release lineage
- authority: verified-repository + verified-ci

## v0.22.0 Packet ↔ Action Evidence

Packet Inspector now resolves concrete packets back to existing archived Research Timeline action windows. A relation is emitted only when the action already references the same canonical `flow_id` and the packet target timestamp lies inside that action's exported target-time window.

The relation reuses the archived window rather than recalculating or widening it. Every packet/action relation remains `temporal-only` and `causal_claim=false`. If the Timeline artifact is missing/invalid, raw packet inspection continues without guessed action links.

Real AVD release acceptance proved the correlation against a genuinely generated Research ZIP and validated that emitted action IDs exist in both the selected flow correlation and archived Timeline.

- source: release commit `d58265584223246974fb641f02e0dd3fb8d3f4f1` and pipeline #125
- authority: verified-repository + verified-ci

## Proven Android runtime baseline

The validated runtime remains hidden Android Emulator (`-qt-hide-window`) → Emulator gRPC → MMAP framebuffer → AndroidView, with persistent geometry-safe gRPC input. v0.10.5 remains the proven startup/clean-launch sequencing baseline.

- source: verified release lineage
- authority: verified-repository

## Evidence semantics

Raw PCAP remains the primary network source of truth. Package/socket ownership, normalized flows, Timeline correlation, QUIC/HTTP3 metadata, Evidence Explorer, Packet Inspector and packet/action links are derived/presentation evidence. Temporal adjacency must never be promoted to proven causality.

- source: verified repository implementation
- authority: verified-repository

## Product UX and release contract

apk-research is a standalone Windows GUI with managed Android runtime; normal use does not require Python or CLI. Stable releases are commit-triggered through the repository pipeline and installers include the version.

- source: explicit owner directives and repository workflows
- authority: owner-directive + verified-repository

## Scope decisions

Audio Evidence and Virtual Display remain explicitly out of scope. scrcpy-style encoded mirroring must not replace the proven gRPC/MMAP live display path.

- source: explicit owner directive 2026-10-06
- authority: owner-directive

## WHPX

WHPX acceptance remains advisory/non-publication-gating. v0.22 WHPX run #118 was queued at the time of the release checkpoint; this does not affect the verified v0.22 publication result.

- source: repository workflow and GitHub Actions
- authority: verified-repository + verified-ci
