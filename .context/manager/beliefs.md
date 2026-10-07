# Manager beliefs

## Product baseline and latest release

The product authority is `main`. The current verified product baseline and latest published release are `apk-research v0.25.0` at commit `3717210a9db3074569602afc336380fd26598dd7`.

Release asset `apk-research-setup_v0.25.0.exe` has SHA-256 `f9a2a92e02b5a1da9f6b8be39d3967a54292d8c04ad20926cba2361f3d560bb7` and size 36,384,738 bytes. The exact-SHA release pipeline published GitHub Release v0.25.0 after CI, real AVD Research ZIP acceptance, Windows standalone/self-test/GUI/installer checks, clean-Windows managed Android provisioning, documentation/checksum validation and release packaging.

- source: GitHub repository main and GitHub Release v0.25.0, reconciled 2026-10-07
- authority: verified-repository + verified-ci

## Completed product roadmap through v0.25

- v0.18.0: Raw / Packet Inspector.
- v0.19.0: project-owned Android app_process sidecar foundation.
- v0.20.0: Continuous Screen foundation.
- v0.21.0: geometry-safe two-pointer interaction completeness.
- v0.22.0: Packet ↔ Action temporal evidence.
- v0.23.0: Transport Session Evidence.
- v0.23.1: Sidecar infrastructure isolation + idle stability correction.
- v0.24.0: Unified Session Evidence and cross-navigation.
- v0.25.0: capture-bounded Transport and Protocol Analysis.

## v0.25 Transport and Protocol Analysis

v0.25 extends Packet Inspector without changing RAW authority. It adds capture-bounded TCP sequence/ACK/window observations, explicit missing-start/missing-end semantics, DNS message/transaction analysis, TLS ClientHello/ServerHello metadata, QUIC Initial/SNI/ALPN aggregation, HTTP/3 reporting only when `h3` is observed, and cleartext HTTP parsing only where captured bytes directly support it.

Sequence gaps are observations in the capture and are not automatically packet-loss claims. Repeated sequence ranges are not automatically network retransmission claims. DNS and HTTP transactions are paired only when the selected flow contains an unambiguous request/query followed by the matching response in capture order. Encrypted application payload is never synthesized as plaintext.

- source: v0.25.0 implementation, PR #16 gates and exact-release publication
- authority: verified-repository + verified-ci

## Screen evidence role

The owner-approved dual-source model remains active:
- Continuous Screen is the stable continuous/timeline screen-evidence source at the current 540×960 / 2 Mbit/s profile;
- Android screenrecord remains the high-resolution 1080×1920 screen-evidence source;
- future sole-source replacement requires a separate quality uplift and revalidation.

The proven live UI transport remains hidden Emulator → gRPC/MMAP → AndroidView and is not replaced by encoded Continuous Screen video.

## Evidence semantics

Raw PCAP remains the primary network source of truth. Researcher-induced infrastructure traffic remains preserved in RAW evidence but may be excluded from ordinary derived app-analysis. Action↔Flow and Packet↔Action remain temporal-only with `causal_claim=false`. Screen links are target-time navigation only. Missing packets/events/frames are not synthesized, and encrypted traffic is not represented as plaintext.

## Protected runtime baseline

The validated runtime remains hidden Android Emulator (`-qt-hide-window`) → Emulator gRPC → MMAP framebuffer → AndroidView, with persistent geometry-safe gRPC input. v0.10.5 remains the proven startup/clean-launch sequencing baseline.

Audio Evidence and user-facing Virtual Display remain out of scope.

## WHPX

WHPX acceptance remains advisory/non-publication-gating.
