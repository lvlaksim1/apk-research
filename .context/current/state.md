# Current Project State

Last reconciled: 2026-10-06.

## Product

- Product: `apk-research`.
- Product authority: `main`.
- Current release/main commit: `cde0b56b5332f0b601221c9157efbd90da18fc33`.
- Latest published release: `v0.23.0`.
- Installer: `apk-research-setup_v0.23.0.exe`.
- Installer SHA-256: `c714270e3d3045d1166afa900d3a4916f7a33b11cf1d2922bb0d59c621bb34b4`.
- Installer size: 36,312,015 bytes.
- Release published: 2026-10-06T04:14:53Z.

## v0.23.0 — Transport Session Evidence

Raw / Packet Inspector now exposes TCP sequence/acknowledgment numbers, flags, header length, receive window and payload length from observed packet headers. For a selected TCP flow it builds a conservative transport-session summary:
- complete three-way handshake only from observed SYN → SYN/ACK → ACK;
- FIN/RST termination only when observed;
- explicit partial/not-observed states when lifecycle packets are absent.

This is capture-bounded presentation evidence. Missing packets are never synthesized and absence from capture is never treated as proof that the event did not occur.

## Verified release state

Main pipeline #126 (`37412349775`) completed SUCCESS for exact SHA `cde0b56b5332f0b601221c9157efbd90da18fc33`:
- CI/compile/tests passed;
- real AVD, gRPC and sidecar checks passed;
- real Research Session and generated Research ZIP acceptance passed;
- transport-session evidence acceptance passed;
- Windows standalone build/self-test/GUI smoke passed;
- v0.23 installer build/install/smoke passed;
- clean-Windows managed Android provisioning passed;
- release documentation and installer checksum passed;
- GitHub Release v0.23.0 was published.

## Runtime/evidence baseline

The hidden Emulator → gRPC/MMAP → AndroidView runtime and v0.10.5 clean-launch sequencing are unchanged. Canonical screenrecord remains authoritative; continuous-screen evidence remains experimental/non-canonical.

## Development status

v0.23.0 is complete and published. No v0.24 implementation is active at this checkpoint.

Audio Evidence and Virtual Display remain out of scope.
