# Manager beliefs

## Product baseline and latest release

The product authority is `main`. The current verified product baseline and latest published release are `apk-research v0.23.1` at commit `39e483ee03d5337e4e928b4b85cce85c40f4fe35`.

Release asset `apk-research-setup_v0.23.1.exe` has SHA-256 `b5bf2d31da1c47ef59d351988a09f5c0dad72a8117aab0c4849ae30bb54eb540` and size 36,323,501 bytes. Main pipeline #127 (`37460233667`) completed SUCCESS for the exact release SHA, including CI, real AVD Research ZIP acceptance, Windows standalone/GUI/installer smoke, clean-Windows managed Android provisioning, checksum verification and GitHub Release publication.

- source: GitHub repository main, pipeline #127 and GitHub Release v0.23.1, reconciled 2026-10-06
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

Packet Inspector derives per-packet TCP sequence/acknowledgment numbers, flags, header length, receive window and payload length directly from observed TCP headers. Transport-session summaries remain capture-bounded and never infer missing lifecycle packets.

### v0.23.1 owner-driven corrective release

The owner-side v0.23.0 archive proved two experimental-sidecar defects: Sidecar adb-reverse loopback traffic polluted normalized app evidence, and the long-lived media connection inherited the generic 8 s socket timeout.

v0.23.1 corrects both:
- exact dynamic Sidecar control/media ports are read from `continuous-screen.json`; matching TCP loopback packets stay in RAW PCAP but are marked as apk-research infrastructure and excluded from ordinary app flow inventory, Timeline markers and action correlations;
- the established binary media stream clears the short socket timeout and becomes blocking; stop/liveness remains controlled through the separate control channel.

Real-AVD acceptance now includes a 10 s static-screen idle interval, longer than the former timeout, and fails if exact Sidecar loopback flows leak into normalized app evidence. PR acceptance and exact-release main pipeline both passed.

- source: owner-provided v0.23.0 archive, release commit `39e483ee03d5337e4e928b4b85cce85c40f4fe35`, PR #14 gates and main pipeline #127
- authority: owner-evidence + verified-repository + verified-ci

### Owner-side v0.23.1 revalidation

Owner-provided archive `20261006T230500.602195Z-1206ec46.research.zip` verifies both v0.23.1 Sidecar corrections in a real session.

- Product version 0.23.1; 31/31 archive checksums valid; session `complete`, `degraded=false`.
- Continuous Screen completed cleanly with 1,613 decoded H.264 frames and 131.195188 s presentation span.
- A real static-screen interval produced a 59.005490 s gap between consecutive Sidecar media frames. Canonical screenrecord shows the same static period as a 60.001711 s frame gap. Both resume at approximately 23:07:00Z. The media connection therefore survived far beyond the former 8 s timeout and resumed normally.
- The action log contains an 83.418846 s no-action interval across the idle period; later interaction is captured normally.
- RAW PCAP contains 22,520 packets, including 21,787 exact Sidecar loopback TCP packets on archived dynamic ports 53659/53669. All remain preserved in RAW evidence; zero Sidecar-port flows appear in the 32 normalized app flows and zero infrastructure events appear in action correlations.
- Canonical screenrecord completed with 925 frames and 132.671076 s presentation span.
- Continuous H.264 decodes cleanly end-to-end. Time-aligned visual samples, including the first frame after the long idle interval, match canonical screenrecord.
- Continuous presentation span is 1.475888 s shorter than canonical, but the first continuous frame still precedes target package launch and the last extends beyond the owner stop request; no target-interaction loss is observed in this session.

Conclusion: the two owner-proven v0.23.0 Sidecar defects are closed in v0.23.1.

- source: owner-provided v0.23.1 Research ZIP `20261006T230500.602195Z-1206ec46.research.zip`, inspected 2026-10-07
- authority: owner-evidence + verified-archive-analysis

## Proven Android runtime baseline

The validated runtime remains hidden Android Emulator (`-qt-hide-window`) → Emulator gRPC → MMAP framebuffer → AndroidView, with persistent geometry-safe gRPC input. v0.10.5 remains the proven startup/clean-launch sequencing baseline.

- source: verified release lineage
- authority: verified-repository

## Evidence semantics

Raw PCAP remains the primary network source of truth. Researcher-induced infrastructure traffic may be classified and excluded from derived app-analysis but must remain preserved in RAW evidence. Temporal adjacency and unobserved packets must never be promoted into stronger claims.

- source: verified repository implementation and owner-side v0.23.0 findings
- authority: verified-repository + owner-evidence

## Scope decisions

Audio Evidence and Virtual Display remain explicitly out of scope. scrcpy-style encoded mirroring must not replace the proven gRPC/MMAP live display path.

- source: explicit owner directive 2026-10-06
- authority: owner-directive

## WHPX

WHPX acceptance remains advisory/non-publication-gating.

- source: repository workflow
- authority: verified-repository


### Owner-side long-session / rollover validation

Owner-provided archive `20261006T231833.446176Z-710dfbe4.research.zip` closes the remaining continuity experiment.

- 33/33 checksummed artifacts verified; session `complete`, `degraded=false`.
- Canonical screenrecord rotated from chunk 1 to chunk 2 with a 1.965848 s frame gap.
- Continuous Screen remained one clean stream with 6,970 frames / 256.466399 s and no receiver error.
- 66 Continuous Screen frames lie inside the canonical rollover gap; the largest adjacent PTS gap there is 0.100000 s.
- Owner action `action-000166` occurred entirely inside the canonical rollover gap, and Continuous Screen contains a frame about 2.179 ms after its target-estimated start.
- The complete continuous H.264 stream decodes without error.
- 93,556 Sidecar infrastructure packets / 65,433,681 bytes remain preserved in RAW PCAP but zero Sidecar-port flows leak into the 82 ordinary normalized flows.

This proves idle resilience, long-session operation and continuity through canonical chunk rotation.

A separate quality boundary remains: Continuous Screen is currently 540×960 at 2 Mbit/s, while canonical screenrecord is 1080×1920. The mechanism can therefore be considered technically validated as a continuous evidence source, but replacing canonical high-resolution screenrecord outright would reduce spatial evidence detail unless the Sidecar quality profile is raised and revalidated.

- source: owner-provided v0.23.1 Research ZIP `20261006T231833.446176Z-710dfbe4.research.zip`, inspected 2026-10-07
- authority: owner-evidence + verified-archive-analysis
