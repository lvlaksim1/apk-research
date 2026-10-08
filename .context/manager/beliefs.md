# Manager beliefs

## Verified baseline

Current product baseline is **apk-research v0.30.0** at `1d75ec32d80cdea2af172035d43d12d3284978fa`.

Live reconciliation on 2026-10-08 confirmed that `main` and the latest GitHub Release both point to that exact SHA. PR #26 delivered the HTTPS traffic analysis feature and was merged at `7f603fa95231d936039ed6dac222b11d5189ad2d`; the current main commit synchronizes release documentation and retriggered the standard release pipeline.

Published assets:
- `apk-research-setup_v0.30.0.exe` — 47,454,995 bytes — SHA-256 `6f9f39c67a88344e7181316c6c6445660f2e1d066deaca09ba13f1ec20954e1a`;
- `apk-research-update_v0.30.0.exe` — 47,455,368 bytes — SHA-256 `4189ff6af7c793bef0db99c673b5838d0a8e6a7ad039cb80b688012353484e1a`;
- `SHA256SUMS.txt` covers both installers.

Main pipeline #143 passed all mandatory release gates and published v0.30.0.

## HTTPS traffic analysis

v0.30.0 adds first-class display of decrypted HTTP/HTTPS transactions in the managed Android research environment.

The managed emulator is routed through a local application-owned HTTPS proxy using `adb reverse`, and a temporary research CA is trusted inside the rooted Android 15 environment for the duration of the research session.

Where decryption succeeds, the Research ZIP stores URL, method, protocol, request/response headers, status, timing and request/response body evidence. The desktop UI exposes these through the dedicated HTTP/HTTPS viewer.

Real Android 15 acceptance proved an actual `https://example.com/` request with HTTP status 200 and a non-empty 577-byte response body. The complete AVD research acceptance then remained healthy and exported a valid Research ZIP.

Passive RAW PCAP remains independently authoritative for packets observed in the configured research environment.

Applications with certificate pinning or application-owned trust stores may reject the research CA. HTTP/3/QUIC content decryption is not claimed by v0.30.0.

## Windows installer/update architecture

The separate Setup/Update architecture introduced in v0.29.2 remains intact. v0.30.0 successfully passed a real v0.29.2 → v0.30.0 update test using the dedicated Update installer.

## Android installation UX

The redundant «Открыть главный экран Android» button remains removed.

The Android home-screen shortcut requirement was explicitly cancelled by the owner on 2026-10-08 and must not be resumed unless explicitly reopened.

## Protected product semantics

APK/XAPK handling, hidden Emulator → gRPC/MMAP → AndroidView, v0.10.5 startup sequencing, Research ZIP, RAW PCAP authority, evidence semantics and the accepted dual-source screen model remain protected.
