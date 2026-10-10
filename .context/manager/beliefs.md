# Manager beliefs

## Verified baseline

Current product baseline is **apk-research v0.33.0** at `3f3f1144e0ea8944a065e7d5950fd07fd1e17abf`. The previous verified baseline was v0.32.0.

Historical 2026-10-08 reconciliation confirmed the then-current v0.30.0 release. PR #26 delivered the HTTPS traffic analysis feature and was merged at `7f603fa95231d936039ed6dac222b11d5189ad2d`; the current main commit synchronizes release documentation and retriggered the standard release pipeline.

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

## Verified v0.31 ARM64 APK/XAPK compatibility

On 2026-10-10 PR #29 merged and main pipeline #144 attempt 2 succeeded, publishing v0.31.0 at `5aab54adc807aff401b59d4c1018795246303b89`. ARM64-only XAPK now selects a separate Android 15 Google APIs x86_64 AVD with native ARM64 execution. The default AVD and userdata remain intact. Actual Android 15 proof: device reports x86_64,arm64-v8a and loads JNI ARM64 native library from synthetic XAPK (`ARM64_NATIVE_LOADED: PASS`). Legacy AVD research, Windows installer/update and clean provisioning passed. First main attempt had an intermittent ADB Settings start failure; same main SHA passed rerun. Owner's exact XAPK was not furnished; universal app compatibility is not claimed.

Setup: `apk-research-setup_v0.31.0.exe` SHA256 `8c253edf38759830fbe8e156282beaa1b2f0f9b98fd6ad3d880679d180176b83`; Update: `apk-research-update_v0.31.0.exe` SHA256 `cb41c928aa2fadeb92bf2c17026cc3863e4d094a0cc5fa92a279597d10baabc6`.

The independent owner directive to route direct HTTPS connections of `com.evrasia` through the local analyzer remains ACTIVE and unimplemented by v0.31.

## Verified v0.32.0 direct HTTPS application routing (2026-10-10)

The owner's 2026-10-10 directive extended HTTP/HTTPS analysis to direct TCP/443 connections bypassing Android's system proxy. PR #30 merged to main `a2f0bbbca364714d37f7697ffa5ccb8204bc94b1`; pipeline #145 attempt 1 SUCCESS, GitHub Release v0.32.0 targets that exact SHA.

Implemented: per-target Android UID rule in NAT OUTPUT for IPv4 TCP/443, separate small native Android route module built from source with official NDK, preservation of destination using SO_ORIGINAL_DST and HTTPS data transfer to the existing local analyzer over adb reverse. During normal teardown, routing rules are removed and their removal verified; the RAW network log `01_raw/network/https-direct-route.log` is archived, with UID/scope/routing fields in existing HTTPS metadata.

Real Android 15 acceptance tested Java system-proxy HTTPS and `Proxy.NO_PROXY` HTTPS independently, both HTTP 200, 577-byte response bodies, `verified_routes: ["direct","system"]`. Default real AVD research, Windows build/full+update, actual v0.31.0 to v0.32.0 update and clean Windows provisioning all passed before merge and again in main pipeline #145.

Published Setup SHA-256 `226d8b4bf12ccab0b07620b8110107354b15873c1f1f93c925bc28d0f2c1c070`; Update SHA-256 `aed61edabbf81e865aa49c16743793886e2bbe5e9394f64b71e75fb7eeedd0cc`.

The actual owner's `com.evrasia` app/Research ZIP has NOT been retested with v0.32.0. Continue that validation as an ACTIVE owner-target task, not a verified field success. IPv6, QUIC/UDP443, custom TLS stores/pinning remain explicit boundaries. Terminology in owner-visible reports must be neutral; avoid language owner prohibited.

## Field-verification of owner app on v0.32.0 (2026-10-10)

Owner uploaded a private Research ZIP from v0.32.0, session 20261010T021552.574206Z-3e8e2043, app com.evrasia. **Do not copy the archive to public GitHub**: it contains authentication credential fields in saved JSON bodies. Only non-sensitive aggregates are recorded here.

Verified ZIP integrity: no ZIP errors; 99/99 listed SHA-256 entries match; session status complete, degraded false, errors empty, mandatory collectors completed.

32 fully readable HTTP/HTTPS responses with all 32 tls_decrypted=true; 28 HTTP 200 and four HTTP 301. Target evrasia.spb.ru: 23 transactions (13 API, 10 image). One evrasia.rest media transaction and eight third-party service transactions. All response bodies nonempty, total 4,669,225 bytes; 14 JSON content-type responses decoded successfully.

Direct-route log: 22 CONNECTION_ROUTED entries, including 21 to 217.197.238.66:443 (target server) and one to 213.180.193.135:443 (mapping service). Android UID 10210 is uniquely associated with com.evrasia; temporary rule cleanup confirmed true. 21 target direct TCP/443 flows appear in normalized inventory. Route counts and HTTP transaction counts are not one-to-one.

Independent raw PCAP: 22,525 packets captured; tcpdump reported 615 packets dropped by kernel. Network inventory 93 flows, 20 attributed with EXACT/HIGH/MEDIUM confidence and 73 UNKNOWN. This limits packet completeness and socket-owner attribution but does not negate the 32 readable HTTPS responses. Android SSL/certificate warnings in logcat came from unrelated PIDs, so they cannot establish failures of app com.evrasia. No logged FATAL EXCEPTION or ANR for com.evrasia in this archive.

The owner's previously unverified direct HTTPS target is NOW **field-verified functional** under v0.32.0. A future improvement to raw PCAP completeness/ownership accuracy is distinct and requires bounded scoping. Scope remains IPv4 TCP/443; no assertions about QUIC, IPv6 or arbitrary trust/pinning.

## Verified v0.33.0 minimal Research/Live HTTPS desktop (2026-10-10)

Owner requested to remove the overwhelming technical UI and retain two functions: full Research ZIP and dynamic HTTPS request/response viewing. PR #31 merged to main `3f3f1144e0ea8944a065e7d5950fd07fd1e17abf`; main pipeline #146 attempt 1 SUCCESS, GitHub Release v0.33.0 targets that exact commit.

The actual desktop entrypoint now launches base `MainWindow` instead of the inherited UI stack that added extra Network/Evidence/Packet/Investigator tabs. Visible navigation is precisely Research and Live HTTPS; Program menu preserves updater and Android maintenance. Underlying collection modules, ZIP artifacts and independent RAW PCAP are unchanged.

`LiveHttpsView` tails complete HTTP JSONL entries every 500 ms, supports filtering and request/response inspection, a 128-KiB display-only body preview, live counters beside Android, and opening completed/previous ZIPs. The reader waits for complete lines and avoids duplicate records. `tcpdump -B 16384 -s 0 -U` increases the kernel capture buffer to 16 MiB and retains full packet length; it cannot guarantee zero packet loss.

Main gate #146 includes unit tests, actual Android 15 AVD research/HTTPS ZIP, standalone Windows GUI, verified v0.32.0 to v0.33.0 in-place update, clean Windows provisioning and release publication. Assets: Setup SHA-256 `70788ed8a2cf8885eea5beb77df1cd560ad41aaa67d49978ba9e972def114718`; Update SHA-256 `a6db937f410f03b49fbc8bff4791a93b367d905245a5b4554aaeab0adb12b38a`.
