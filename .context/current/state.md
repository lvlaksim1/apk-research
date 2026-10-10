# Current Project State

Last reconciled: 2026-10-10.

## Product

- Current release/main commit: `a2f0bbbca364714d37f7697ffa5ccb8204bc94b1`.
- Latest release: `v0.32.0`.
- Full installer: `apk-research-setup_v0.32.0.exe` (SHA256 `226d8b4bf12ccab0b07620b8110107354b15873c1f1f93c925bc28d0f2c1c070`).
- Update installer: `apk-research-update_v0.32.0.exe` (SHA256 `aed61edabbf81e865aa49c16743793886e2bbe5e9394f64b71e75fb7eeedd0cc`).
- Main pipeline #145 attempt 1 SUCCESS (2026-10-10); GitHub Release targets exact main SHA.

## v0.30.0

The application now displays decrypted HTTP/HTTPS transaction content where the managed research environment can establish trust:
- URL and method;
- request headers/body;
- response status;
- response headers/body;
- HTTP protocol and timing;
- searchable dedicated HTTP/HTTPS results viewer.

The managed Android environment is routed through an application-owned local HTTPS proxy over `adb reverse`. A temporary research CA is trusted in the rooted Android 15 system environment for the session.

The Research ZIP records HTTP transaction metadata/bodies and routing/trust provenance separately from passive RAW PCAP.

## Verification

PR #26 is merged.

Main pipeline #143 passed:
- full CI;
- real Android 15 AVD acceptance;
- actual HTTPS request to `https://example.com/` with status 200 and non-empty 577-byte response body;
- full existing AVD research acceptance after the HTTPS test;
- Windows standalone build and GUI smoke;
- standalone HTTPS component smoke;
- full + update installer build;
- real v0.29.2 → v0.30.0 dedicated update acceptance;
- clean-Windows Android provisioning;
- GitHub Release publication.

WHPX remains advisory/non-publication-gating.

## Known bounded limitations

Applications with certificate pinning or application-owned trust stores may reject the research CA.

HTTP/3/QUIC content decryption is not claimed by v0.30.0.

## Owner cancellation

The Android home-screen shortcut requirement remains cancelled.

## Development status

v0.30.0 was the earlier HTTPS baseline; new v0.31.0 ARM-only APK support is independent and does not establish success for the owner-tested direct HTTPS connections; its generic HTTPS acceptance does not establish working HTTPS inspection for the owner-tested `com.evrasia` APK. Prior-chat analysis of `20261008T020126.928669Z-e336ad57.research.zip` reported 23 direct TCP connections to remote port 443 (21 to `evrasia.spb.ru`) and zero entries in `http-transactions.jsonl`. This report must be corroborated against the archive before making implementation claims.

**A newer owner directive from 2026-10-08 is active:** implement automatic routing of relevant target HTTPS traffic into the local analyzer even when the Android application ignores the configured system proxy. The old "no additional stage authorized" statement is superseded. The HTTPS routing correction remains unimplemented in v0.31.0.

## Verified v0.31.0 ARM64 XAPK addition

ABI preflight selects on-demand separate Google APIs Android 15 x86_64 image with system ARM64 translation for ARM-only APK/XAPK. Legacy default AVD/userdata are preserved. Live Android 15 acceptance confirmed x86_64,arm64-v8a and successfully loaded real ARM64 JNI from test XAPK (`ARM64_NATIVE_LOADED: PASS`). Real standard AVD acceptance and Windows Setup/Update/clean-provisioning acceptance passed before PR #29 merge and in main pipeline #144 attempt 2. The owner's exact application was not provided for testing.

## v0.32.0 — directly connected HTTPS from selected application

- Android application UID read from package manager. Scoped NAT OUTPUT rule routes only the selected package's IPv4 TCP/443 data to a small Android-local module; all other apps are outside this new rule.
- Native module obtains original destination with `SO_ORIGINAL_DST`, sends traffic to existing HTTPS analyzer via `adb reverse`; readable request/response records appear in existing HTTP/HTTPS viewer when TLS trust permits.
- New raw diagnostic artifact: `01_raw/network/https-direct-route.log`; metadata records target UID, route usage, route cleanup confirmation and routing limitations. RAW PCAP remains a separate source.
- Real Android 15 acceptance proved system+direct `Proxy.NO_PROXY` HTTPS requests to `https://example.com/` both HTTP 200, 577 bytes. Main pipeline #145 succeeded including Windows Setup/Update and clean provisioning.
- Field validation of `com.evrasia` remains outstanding. Specific application TLS trust or QUIC handling cannot be asserted without a fresh archive.

## Actual owner app field result — verified 2026-10-10

Uploaded private evidence: 20261010T021552.574206Z-3e8e2043.research.zip, produced by published apk-research v0.32.0 on installed com.evrasia.

- Session complete, not degraded, no errors; all 99 enumerated SHA-256 checksums match.
- 32 HTTP(S) transactions with tls_decrypted=true, 28 HTTP 200 / 4 HTTP 301, all with nonempty responses (4,669,225 bytes total); 14/14 JSON responses parse successfully.
- 23 evrasia.spb.ru transactions, of which 13 API and 10 media; one additional evrasia.rest media response; eight third-party service responses.
- Native direct route log: 21 entries to 217.197.238.66:443, one to 213.180.193.135:443. The device route cleanup succeeded. The selected package's unique UID was 10210.
- RAW PCAP has 22,525 captured packets; tcpdump reported 615 kernel drops. 93 normalized flow entries, 20 attributed at EXACT/HIGH/MEDIUM and 73 UNKNOWN. These are accuracy findings distinct from successfully readable HTTPS.
- No FATAL EXCEPTION or ANR for com.evrasia evident in this session.
- Recorded auth JSON includes access/refresh token fields; these values and the private ZIP MUST NOT be posted to public GitHub.

**The com.evrasia-specific previous HTTPS gap is verified resolved for this observed run.** Older paragraphs in this history calling for a future target test are superseded.
