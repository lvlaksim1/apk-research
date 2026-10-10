# Latest Handoff

Generation: 29
Date: 2026-10-10
Persistent manager: apk-research-project-manager
Product authority: main
Manager-state authority: context

## Published baseline

apk-research v0.32.0, exact main/release SHA a2f0bbbca364714d37f7697ffa5ccb8204bc94b1; pipeline #145 attempt 1 success. Separate Setup and Update assets are published. Preserve all prior Android and evidence invariants.

## Owner target field verification — CONFIRMED

Owner uploaded private archive 20261010T021552.574206Z-3e8e2043.research.zip from an actual com.evrasia research session using v0.32.0. ZIP integrity checks: 99/99 valid; status complete, no degraded collectors/errors. It contains 32 readable HTTP(S) transactions (28 HTTP 200, 4 HTTP 301) with 4,669,225 total response-body bytes. 23 transactions relate to evrasia.spb.ru (13 API, 10 images), plus one evrasia.rest response. Native route diagnostics contain 21 successful direct TCP/443 entries to 217.197.238.66 and one to a mapping-service IP. Temporary Android UID route cleanup confirmed, UID 10210 uniquely identified the target package. Hence the original owner issue of direct HTTPS without readable requests is **resolved in this measured session**.

## Remaining measured quality issues

Raw TCP dump reported 22,525 captured packets and 615 kernel drops. Of 93 normalized network flow entries, only 20 were attributed at EXACT/HIGH/MEDIUM; 73 UNKNOWN. These concern packet capture reliability and ownership correlation, not the demonstrated presence of HTTP responses. No new changes authorized for these yet. Per-transaction provenance of direct vs configured system proxy is not explicitly represented.

## Confidentiality

The ZIP has authenticated API responses with access_token and refresh_token fields. Treat the entire ZIP as private; no values or archive copies are to be put in a public GitHub repository. Only aggregate project conclusions are suitable for durable context.

## Boundaries

No universal HTTPS claims: current routing covers selected-app IPv4 TCP/443; app-specific trust, IPv6 and UDP/QUIC need separate evidence. Preserve independent RAW PCAP, Android 15 ARM64 profiles, installer architecture and cancellation of home-screen shortcut. Use neutral owner-visible terminology.
