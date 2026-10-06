# Manager beliefs

## Product baseline and latest release

The product authority is `main`. The current verified product baseline and latest published release are `apk-research v0.23.0` at commit `cde0b56b5332f0b601221c9157efbd90da18fc33`.

Release asset `apk-research-setup_v0.23.0.exe` has SHA-256 `c714270e3d3045d1166afa900d3a4916f7a33b11cf1d2922bb0d59c621bb34b4` and size 36,312,015 bytes. Main pipeline #126 (`37412349775`) completed SUCCESS for the exact release SHA, including CI, real AVD Research ZIP acceptance, Windows standalone/GUI/installer smoke, clean-Windows managed Android provisioning, checksum verification and GitHub Release publication.

- source: GitHub repository main, pipeline #126 and GitHub Release v0.23.0, reconciled 2026-10-06
- authority: verified-repository + verified-ci

## Stage A-D baseline

- v0.18.0: Raw / Packet Inspector.
- v0.19.0: project-owned temporary Android app_process sidecar foundation.
- v0.20.0: experimental continuous-screen MediaCodec/device-PTS evidence; canonical screenrecord retained.
- v0.21.0: geometry-safe two-pointer interaction completeness over existing Emulator gRPC input.

- source: verified repository/release lineage
- authority: verified-repository + verified-ci

## Stage E evidence intelligence

### v0.22.0 Packet ↔ Action Evidence

Packet Inspector resolves concrete PCAP packets back to existing archived Research Timeline action windows only when the action already references the same canonical `flow_id` and the packet target timestamp lies inside that action's exported target-time window. Relations remain `temporal-only` and `causal_claim=false`.

### v0.23.0 Transport Session Evidence

Packet Inspector now derives per-packet TCP sequence/acknowledgment numbers, flags, header length, receive window and payload length directly from observed TCP headers. A flow-level transport summary reports a complete three-way handshake only when SYN → SYN/ACK → ACK are actually present in capture order, and reports FIN/RST termination only when observed.

Missing lifecycle packets are represented as `partial-or-not-observed-in-capture` or `not-observed-in-capture`; absence from PCAP is not evidence that the event did not occur. No TCP application-stream reconstruction or plaintext inference was introduced.

- source: release commit `cde0b56b5332f0b601221c9157efbd90da18fc33` and pipeline #126
- authority: verified-repository + verified-ci

## Proven Android runtime baseline

The validated runtime remains hidden Android Emulator (`-qt-hide-window`) → Emulator gRPC → MMAP framebuffer → AndroidView, with persistent geometry-safe gRPC input. v0.10.5 remains the proven startup/clean-launch sequencing baseline.

- source: verified release lineage
- authority: verified-repository

## Evidence semantics

Raw PCAP remains the primary network source of truth. Package/socket ownership, normalized flows, Timeline correlation, QUIC/HTTP3 metadata, Evidence Explorer, Packet Inspector, packet/action links and transport-session summaries are derived/presentation evidence. Temporal adjacency and unobserved packets must never be promoted into stronger claims.

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

WHPX acceptance remains advisory/non-publication-gating. v0.23 WHPX run #119 was queued independently of the successful release pipeline; its queue/result does not affect the verified v0.23 publication state.

- source: repository workflow and GitHub Actions
- authority: verified-repository + verified-ci
