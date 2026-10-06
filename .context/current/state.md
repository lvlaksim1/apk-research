# Current Project State

Last reconciled: 2026-10-06.

## Product

- Product: `apk-research`.
- Product authority: `main`.
- Current release/main commit: `d58265584223246974fb641f02e0dd3fb8d3f4f1`.
- Latest published release: `v0.22.0`.
- Installer: `apk-research-setup_v0.22.0.exe`.
- Installer SHA-256: `d6f7ae647d755455a374189a3731e15057fc74ec88c4b9a846143145ebb0ae8a`.
- Installer size: 36,311,844 bytes.
- Release published: 2026-10-06T02:57:41Z.

## Completed roadmap releases

- v0.18.0 — Raw / Packet Inspector: direct in-app inspection of concrete PCAP packets for a normalized flow, raw locators, bounded hex preview and packet-level protocol metadata.
- v0.19.0 — Android Sidecar Foundation: project-owned temporary app_process agent with host-listen-first adb reverse transport, exact version handshake, persistent control socket and deterministic cleanup.
- v0.20.0 — Continuous Screen Evidence: experimental sidecar MediaCodec H.264 capture with device PTS and A/B report; canonical screenrecord remains authoritative.
- v0.21.0 — Interaction Completeness: multi-touch gRPC gestures and display-geometry generation protection.
- v0.22.0 — Packet ↔ Action Evidence: packet-level temporal links to existing archived Timeline windows and Packet → Timeline navigation.

## Verified v0.22 release state

Main pipeline #125 (`37406246024`) completed SUCCESS for exact SHA `d58265584223246974fb641f02e0dd3fb8d3f4f1`, including CI, real AVD, Research ZIP acceptance, Windows build/GUI/installer smoke, clean-Windows provisioning and release publication.

## Active v0.23 development

Branch: `dev-v023-transport-session`.
HEAD: `654e32d2c857af7ddf0de82594ef90dd34aba3a8`.
The branch is 5 commits ahead of `main` and 0 behind.

Implemented:
- TCP header evidence in Packet Inspector: sequence/acknowledgment numbers, flags, header length, window and payload length;
- transport-session summary based only on packets actually present in PCAP;
- three-way handshake status and packet IDs when SYN → SYN/ACK → ACK are observed;
- FIN/RST termination evidence;
- explicit `partial-or-not-observed-in-capture` / `not-observed-in-capture` semantics when lifecycle packets are absent;
- Packet Inspector UI/search exposure;
- regression tests and real-AVD acceptance.

Verification for current HEAD:
- CI run #257 / `37407339493`: SUCCESS;
- AVD Acceptance run #93 / `37407339496`: SUCCESS;
- Desktop Build run #178 / `37407339506`: SUCCESS.

An earlier branch revision `d08e2d32...` had CI/Desktop failures caused by a transport-search regression expectation; commit `654e32d2...` corrected the expectation and all three gates are now green. This is not evidence of a runtime/product regression.

v0.23 has not yet been promoted to `main` or published as a release.

## Runtime/evidence baseline

The hidden Emulator → gRPC/MMAP → AndroidView runtime and v0.10.5 clean-launch sequencing remain unchanged. Canonical screenrecord remains authoritative; continuous-screen evidence remains experimental/non-canonical.

Audio Evidence and Virtual Display remain out of scope.
