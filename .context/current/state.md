# Current Project State

Last reconciled: 2026-10-10.

## Product

- Current release/main commit: `2efec386cff0b204ee56d8bee365f3c52caefcb5`.
- Latest release: `v0.34.0`.
- Full installer: `apk-research-setup_v0.33.0.exe` (SHA256 `70788ed8a2cf8885eea5beb77df1cd560ad41aaa67d49978ba9e972def114718`).
- Update installer: `apk-research-update_v0.33.0.exe` (SHA256 `a6db937f410f03b49fbc8bff4791a93b367d905245a5b4554aaeab0adb12b38a`).
- Main pipeline #146 attempt 1 SUCCESS (2026-10-10); GitHub Release targets exact main SHA.

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

## v0.33.0 — simplified study window and live HTTPS

- Only Research and Live HTTPS tabs are visible at actual program entrypoint. Technical results tabs no longer added by the historical desktop subclass stack.
- HTTPS transactions are displayed during an active session at 500-ms intervals from incremental JSONL; full request/response evidence remains in ZIP, with UI previews limited to 128 KiB.
- Research tab includes live count and quick switch to HTTPS, direct ZIP folder access, Russian progress and archive completion status.
- Mandatory RAW network, screen, actions, logcat, HTTPS, attribution, other evidence collection and integrity workflow remain enabled automatically.
- Capture buffer enlarged to 16 MiB, full packet snaplen retained; actual field packet drop reductions remain unverified until the next owner research ZIP.
- Windows setup and v0.32.0 → v0.33.0 update, real AVD research and clean Windows provisioning all passed.

## v0.34.0 work in progress (not released)

Latest verified product is v0.33.0 at 3f3f1144e0ea8944a065e7d5950fd07fd1e17abf. Work branch feature/v0.34-emulator-controls-network-evidence, PR #32 draft, latest proposed SHA 8c1dbcc81fa3620ed96b30300211c90fb7872ec3. Right-hand Android control panel and derived DNS/TLS/HTTP timing/action correlation/screen timing evidence are implemented in source. Independent RAW PCAP, original HTTPS bodies, gRPC/MMAP, v0.31 ARM64 and old UI tabs remain intact.

Windows and final Android acceptance are PENDING. Prior PR candidate 8afe5c1d passed all unit and real AVD acceptance, including six new ZIP files and 3660 scanned PCAP packets; latest TLS all-port tweak still needs exact-head proof. Previous AVD CI attempts for intermediate candidates hit intermittent ADB com.android.settings start exit 255 before derived ZIP checks. Do not mark release ready until final tests pass.

## Definitive release reconciliation — 2026-10-13 (generation 32)

This section SUPERSEDES earlier historical v0.33 and v0.34-pending statements in this document.

- Product authority: `main` at `2efec386cff0b204ee56d8bee365f3c52caefcb5`.
- Published and verified: `v0.34.0`, GitHub Release target EXACTLY `2efec386cff0b204ee56d8bee365f3c52caefcb5`, published 2026-10-13.
- PR #32 merged (commit `e9240f05e620b1cee4f2d1d4ee0c14f1d36a111d`); draft PR #33 separately closed **unmerged**. Do not mistake its changes for the product.
- Successful final release run: GitHub Actions #38375309755; CI, Android 15 AVD, standalone Windows GUI/installer, previous-release update, clean Windows provisioning and Publish Release all SUCCESS.
- Earlier main run #38023468111 failed the Windows update gate. Subsequent fix and full rerun succeeded; it is incorrect to treat the old failed run as the final release status.
- Setup: `apk-research-setup_v0.34.0.exe`, SHA256 `7ba45c3d5fb4a91d5df8bc3d8431928b135b76251470c0b41f458e778711d233`.
- Update: `apk-research-update_v0.34.0.exe`, SHA256 `1df62f8a39c1efbabe201eafaeaaa93e8dd2b4e597bce7364249fafff252e779`.
- Release files also contain `SHA256SUMS.txt`.
- Release URL: https://github.com/lvlaksim1/apk-research/releases/tag/v0.34.0

### Delivered user-facing features

Only two primary tabs: Research and HTTPS online. A conventional slim right-side Android control panel provides navigation, volume, rotation, screenshot, fullscreen, install, reboot, file transfer, app operations, simulated location/motion and clipboard-based input as covered by the published release. Potentially destructive actions are protected. Existing embedded gRPC/MMAP Android display and XAPK workflow preserved.

### Additional research artifacts

Six normalized files in Research ZIP: `dns.jsonl`, `tls-sessions.jsonl`, `network-timings.jsonl`, `action-network-links.jsonl`, `screen-timing.jsonl`, `network-enrichment.json`. Data derive from recorded observations; DNS-over-HTTPS and encrypted or absent TLS details may be inaccessible. User-action timing is temporal association, not proven causation. Original RAW PCAP, full HTTPS content, video, logs and hash integrity remain independent.

### Field issue status

The owner's earlier v0.33.0 transient com.evrasia loading stall resolved after restarting Android. Root cause was not demonstrated. Experimental network reset changes were NOT merged/released. No unresolved owner-reported failure is established for newly published v0.34.0; installation and field validation are awaiting user feedback.
