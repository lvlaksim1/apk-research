# Latest Handoff

Generation: 28
Date: 2026-10-10
Persistent manager: `apk-research-project-manager`
Manager-state authority: `context`
Product authority: `main`

## Latest verified publication

**apk-research v0.32.0**, published 2026-10-10, exact main/release commit `a2f0bbbca364714d37f7697ffa5ccb8204bc94b1`. PR #30 merged. Main pipeline **#145 attempt 1 SUCCESS**: CI tests, real Android 15 AVD/HTTPS, standalone Windows build, in-place update v0.31.0 → v0.32.0, clean Windows provisioning and release publication.

Setup: `apk-research-setup_v0.32.0.exe`, SHA-256 `226d8b4bf12ccab0b07620b8110107354b15873c1f1f93c925bc28d0f2c1c070`.
Update: `apk-research-update_v0.32.0.exe`, SHA-256 `aed61edabbf81e865aa49c16743793886e2bbe5e9394f64b71e75fb7eeedd0cc`.
SHA256SUMS.txt published for both.

## Completed generic direct HTTPS support

The owner instructed the manager to support direct HTTPS connections bypassing Android system proxy. The published implementation (1) reads the exact Android package UID, (2) directs only that UID's IPv4 TCP/443 via a root Android NAT rule to a small native service, (3) uses SO_ORIGINAL_DST to retain original destination and forwards to the existing local HTTPS analyzer via adb reverse, (4) archives `01_raw/network/https-direct-route.log` and detailed route metadata, (5) checks removal of network rule on normal shutdown and recovers stale rules on a new session. Original RAW PCAP remains independent.

**Verified live:** real Android 15 application made normal-system-proxy and `Proxy.NO_PROXY` requests to `https://example.com/`, each returned HTTP 200 with a 577-byte body. Research ZIP contained both HTTP transactions and the direct-route journal. Real baseline research, Windows packaging/upgrade and clean provisioning passed.

## STILL ACTIVE — owner-specific field verification

The user's earlier `20261008T020126.928669Z-e336ad57.research.zip` from `com.evrasia` predated this feature and reportedly contained direct TCP/443 connections without readable HTTP transactions. **That same application has not yet been tested on v0.32.0.** Request its new Research ZIP; confirm destination records in the route journal and actual HTTP requests/responses in normalized transactions before marking the owner-specific case closed. App-defined TLS trust, IPv6 and QUIC/UDP443 remain explicit boundaries, with no universal claim.

## Other constraints

Owner confirms the prior ARM64/XAPK feature works. Preserve separate AVD user data, gRPC/MMAP, root, native ABI support and release integrity; Android home-screen shortcut task remains cancelled. Do not use owner-prohibited terminology in user-visible comments; use neutral Russian technical terms.
