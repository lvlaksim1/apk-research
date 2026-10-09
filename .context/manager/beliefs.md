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

## Owner-directed HTTPS follow-up after the v0.30.0 capsule (2026-10-08)

The owner inspected the real archive `20261008T020126.928669Z-e336ad57.research.zip` after publication of v0.30.0. Prior-chat analysis reported 23 TCP connections to remote port 443, of which 21 connected to `evrasia.spb.ru`; the `02_normalized/http-transactions.jsonl` transaction list was empty. The analyzed `com.evrasia` application used direct HTTPS connections rather than the configured Android system proxy. These archive-specific observations are carried forward from the prior conversation and should be revalidated against the actual archive before a code-level diagnosis or claims of successful remediation.

Subsequently the owner expressly directed the manager to implement automatic routing of target HTTPS connections that disregard the Android system proxy to the local HTTPS analyzer. This is an ACTIVE owner commitment, chronologically newer than generation 25, and supersedes the old claim that no further feature work is authorized. No implementation, test or release after v0.30.0 is verified in GitHub as of 2026-10-10.

For owner-visible communications, use neutral accurate language such as "HTTPS traffic analysis" and "HTTPS routing"; avoid the terminology the owner expressly prohibited.

- authority: direct owner instruction in 2026-10-08 project chat;
- technical evidence: prior-chat Research ZIP analysis, not yet rechecked in this reinstantiated runtime;
- product confirmation: GitHub main and latest release checked 2026-10-10.
