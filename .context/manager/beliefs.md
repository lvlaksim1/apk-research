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

Packet Inspector derives per-packet TCP sequence/acknowledgment numbers, flags, header length, receive window and payload length directly from observed TCP headers. A flow-level transport summary reports a complete three-way handshake only when SYN → SYN/ACK → ACK are actually present in capture order, and reports FIN/RST termination only when observed.

Missing lifecycle packets are represented as `partial-or-not-observed-in-capture` or `not-observed-in-capture`; absence from PCAP is not evidence that the event did not occur. No TCP application-stream reconstruction or plaintext inference was introduced.

- source: release commit `cde0b56b5332f0b601221c9157efbd90da18fc33` and pipeline #126
- authority: verified-repository + verified-ci

## Owner-side v0.23 real Research ZIP findings

The owner supplied real archive `20261006T105244.785342Z-3076e6ba.research.zip`. All 31 checksummed artifacts verified. Session status is complete, degraded=false, target package is com.evrasia 2.8.4, launch is verified COLD, canonical screenrecord covers the launch and user interaction period, tcpdump reports 12429 captured packets and 0 kernel drops, and no app crash/ANR was observed.

Two verified defects exist in the experimental continuous-screen path:

1. Sidecar control/media adb-reverse loopback traffic is currently normalized as ordinary network flows. In this archive `flow-000001` and `flow-000002` are 127.0.0.1 sidecar flows on the dynamically allocated control/media ports. They account for 11,993 of 12,419 TCP/UDP flow packets (96.57%) and 7,208,463 of 7,396,346 TCP/UDP captured bytes (97.46%). The media flow is correlated with 15 of 16 user actions, polluting Timeline/Network/Packet analysis. Raw PCAP itself remains valid.

2. Experimental continuous screen fails after about 10.04 s of media PTS. The sidecar encoder logs show `repeat-previous-frame-after` is unsupported by the C2 encoder, while the host media socket retains the generic 8 s socket timeout. The last media PTS maps to approximately 10:53:01.030Z and the first subsequent user action begins at target-estimated 10:53:09.655Z, an 8.624 s idle gap. This exceeds the socket timeout and is consistent with the recorded receiver error `Unable to read Android sidecar media stream`. Cleanup is incomplete and collector status is `failed-experimental`.

The canonical screenrecord remains healthy and authoritative; therefore the overall Research Session remains complete despite the experimental collector failure.

- source: owner-provided v0.23 Research ZIP plus main-branch continuous-screen/sidecar implementation
- authority: owner-evidence + verified-repository

## Proven Android runtime baseline

The validated runtime remains hidden Android Emulator (`-qt-hide-window`) → Emulator gRPC → MMAP framebuffer → AndroidView, with persistent geometry-safe gRPC input. v0.10.5 remains the proven startup/clean-launch sequencing baseline.

- source: verified release lineage
- authority: verified-repository

## Evidence semantics

Raw PCAP remains the primary network source of truth. Package/socket ownership, normalized flows, Timeline correlation, QUIC/HTTP3 metadata, Evidence Explorer, Packet Inspector, packet/action links and transport-session summaries are derived/presentation evidence. Temporal adjacency, infrastructure-induced traffic and unobserved packets must never be promoted into stronger claims.

- source: verified repository implementation and owner-side v0.23 archive
- authority: verified-repository + owner-evidence

## Product UX and release contract

apk-research is a standalone Windows GUI with managed Android runtime; normal use does not require Python or CLI. Stable releases are commit-triggered through the repository pipeline and installers include the version.

- source: explicit owner directives and repository workflows
- authority: owner-directive + verified-repository

## Scope decisions

Audio Evidence and Virtual Display remain explicitly out of scope. scrcpy-style encoded mirroring must not replace the proven gRPC/MMAP live display path.

- source: explicit owner directive 2026-10-06
- authority: owner-directive

## WHPX

WHPX acceptance remains advisory/non-publication-gating.

- source: repository workflow
- authority: verified-repository
