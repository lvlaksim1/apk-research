# Manager beliefs

## Product baseline and latest release

The product authority is `main`. The current verified product baseline and latest published release are `apk-research v0.24.0` at commit `176dc1f1302c729456fc0d5711d0e5879e36837e`.

Release asset `apk-research-setup_v0.24.0.exe` has SHA-256 `f1ee0ec8e60345b17a21d00c8a5f4b4f616c8ed6c1aca24714f92eb912cb2c3c` and size 36,355,696 bytes. Main pipeline #133 (`37558075676`) completed SUCCESS for the exact release SHA, including CI, real AVD Research ZIP acceptance, Windows standalone/self-test/GUI/installer smoke, clean-Windows managed Android provisioning, documentation validation, checksum verification, release publication and temporary-artifact cleanup.

- source: GitHub repository main, pipeline #133 and GitHub Release v0.24.0, reconciled 2026-10-07
- authority: verified-repository + verified-ci

## Completed product roadmap through v0.24

- v0.18.0: Raw / Packet Inspector.
- v0.19.0: project-owned Android app_process sidecar foundation.
- v0.20.0: Continuous Screen foundation.
- v0.21.0: geometry-safe two-pointer interaction completeness.
- v0.22.0: Packet ↔ Action temporal evidence.
- v0.23.0: Transport Session Evidence.
- v0.23.1: Sidecar infrastructure isolation + idle stability correction.
- v0.24.0: Unified Session Evidence and cross-navigation.

- source: verified release lineage
- authority: verified-repository + verified-ci

## v0.24 Unified Session Evidence

v0.24 adds one cross-navigable investigation model over existing archived evidence. The intended chain is `screen ↔ action ↔ normalized flow ↔ packet ↔ process/socket ↔ raw evidence`.

The new Session Evidence view is chronological and presentation-only. It can navigate to Timeline, Evidence Explorer and Packet Inspector. Evidence Explorer also provides reverse Process/Socket → related flows navigation.

Continuous Screen device MediaCodec PTS is mapped to target UTC for navigation using the realtime↔elapsed transform already archived by high-resolution Android screenrecord timing. Screen links are explicitly `time-aligned-navigation`; they do not assert causality. A high-resolution screenrecord chunk gap is represented as a gap rather than silently interpolated.

Process/socket reverse navigation preserves the attribution confidence already present in normalized flow evidence and never upgrades it.

- source: v0.24.0 implementation, tests and exact-release pipeline #133
- authority: verified-repository + verified-ci

## Screen evidence role

The owner-approved dual-source model remains active:
- Continuous Screen is the stable continuous/timeline screen-evidence source at the current 540×960 / 2 Mbit/s profile;
- Android screenrecord remains the high-resolution 1080×1920 screen-evidence source;
- future sole-source replacement requires a separate quality uplift and revalidation.

The proven live UI transport remains hidden Emulator → gRPC/MMAP → AndroidView and is not replaced by encoded Continuous Screen video.

- source: explicit owner directive 2026-10-07 + owner-side v0.23.1 validation
- authority: owner-directive + owner-evidence

## Evidence semantics

Raw PCAP remains the primary network source of truth. Researcher-induced infrastructure traffic remains preserved in RAW evidence but may be excluded from ordinary derived app-analysis. Action↔Flow and Packet↔Action remain temporal-only with `causal_claim=false`. Screen links are target-time navigation only. Missing packets/events/frames are not synthesized, and encrypted traffic is not represented as plaintext.

- source: verified repository implementation and owner directives
- authority: verified-repository + owner-directive

## Protected runtime baseline

The validated runtime remains hidden Android Emulator (`-qt-hide-window`) → Emulator gRPC → MMAP framebuffer → AndroidView, with persistent geometry-safe gRPC input. v0.10.5 remains the proven startup/clean-launch sequencing baseline.

Audio Evidence and user-facing Virtual Display remain out of scope.

## WHPX

WHPX acceptance remains advisory/non-publication-gating.
