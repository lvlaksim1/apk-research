# Latest Handoff

Generation: 26
Date: 2026-10-10
Persistent manager: `apk-research-project-manager`
Manager-state authority: `context`
Product authority: `main`

## Verified published baseline

The latest checked product commit on `main` is `1d75ec32d80cdea2af172035d43d12d3284978fa`, with published v0.30.0. Main pipeline #143 completed release acceptance. Separate full and update assets were released:
- Setup: `apk-research-setup_v0.30.0.exe`, SHA-256 `6f9f39c67a88344e7181316c6c6445660f2e1d066deaca09ba13f1ec20954e1a`.
- Update: `apk-research-update_v0.30.0.exe`, SHA-256 `4189ff6af7c793bef0db99c673b5838d0a8e6a7ad039cb80b688012353484e1a`.

v0.30.0's generic HTTPS analysis, request/response viewer and real Android 15 HTTPS acceptance are verified. Protected RAW PCAP provenance and Android runtime invariants remain binding.

## Newer owner directive, not represented in generation 25

On 2026-10-08, after analyzing owner-supplied archive `20261008T020126.928669Z-e336ad57.research.zip`, the owner explicitly instructed the manager to implement automatic HTTPS routing to the local analyzer for applications that bypass Android system proxy configuration. Previously reported archive findings: `com.evrasia` used direct remote HTTPS connections, with 23 connections on TCP/443 (21 to `evrasia.spb.ru`) and no readable normalized HTTP transactions. The new runtime must verify these archive-specific details before asserting precise causal mechanisms.

**Status: ACTIVE, not implemented/verified in GitHub.** The former statement that no further development was authorized is superseded. Next step: inspect archived evidence and source, implement a constrained routing correction on a dedicated branch, verify a representative real APK and publish only through accepted release gates.

## Other commitments

The Android home-screen shortcut requirement was expressly cancelled by the owner on 2026-10-08; do not reinstate. Application-defined trust/certificate pinning and QUIC/HTTP3 decryption are not claimed as implemented.
