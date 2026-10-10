# Manager plans

## Default change/release plan

1. Reinstate from `context` and reconcile live `main`, latest release and CI.
2. Use a dedicated feature/fix branch from the verified baseline.
3. Make the minimum coherent change.
4. Run unit/compile plus relevant real AVD and Windows verification.
5. For updater changes, prove a real previous-release → candidate update with the dedicated Update installer.
6. Publish stable releases only through the main pipeline.
7. Persist verified state and reseal manager integrity.

## Current release architecture

Stable releases publish:
- `apk-research-setup_v<version>.exe`;
- `apk-research-update_v<version>.exe`;
- `SHA256SUMS.txt` covering both.

The application updater uses only the dedicated Update asset.

## HTTPS traffic analysis

The v0.30 implementation stage is complete and released.

Verified delivered scope:
- local application-managed HTTPS proxy;
- Android routing through `adb reverse`;
- temporary research CA trust in the managed rooted Android 15 environment;
- HTTP transaction metadata and bodies in Research ZIP;
- dedicated HTTP/HTTPS desktop viewer;
- passive RAW PCAP preserved as an independent evidence source;
- real Android 15 end-to-end acceptance.

Do not claim universal HTTPS decryption. Certificate pinning/custom trust and HTTP/3/QUIC remain separate bounded follow-up areas.

## Current product plan

The owner subsequently authorized a bounded HTTPS routing correction for applications that bypass the Android system proxy. Begin with the reported `com.evrasia` evidence from `20261008T020126.928669Z-e336ad57.research.zip`, independently re-check archive evidence and then inspect the current routing/proxy implementation. Develop and verify a robust automatic routing path without weakening protected Android runtime or forensic invariants. Preserve explicit technical boundaries (application-controlled trust and QUIC/HTTP3 remain unclaimed unless separately verified).

The previous "no further stage is authorized" assertion was true at the v0.30.0 seal but is superseded by the later 2026-10-08 owner directive. v0.31.0 delivered the separate ARM64 XAPK requirement, but did **not** implement the active direct HTTPS routing requirement.

The Android home-screen shortcut requirement remains cancelled.

## ARM64 compatibility maintenance

Preserve the separate default and Google APIs Android 15 AVD userdata, verify real ARM64 execution (not just installation) and use target-specific diagnosis for owner-supplied APK/XAPK. Avoid breaking the proven root/gRPC-MMAP research runtime. Direct TCP/443 routing is now delivered in v0.32.0; next action is field validation on the owner's `com.evrasia` APK.

## Follow-up plan after v0.32.0

Obtain a real v0.32.0 session on the owner's target app, compare route log (actual direct target IP/port) with readable transactions, count HTTP responses and inspect TLS trust errors if any. Keep RAW PCAP independent. Do not infer decrypted HTTPS from TCP/443 connectivity alone; acknowledge custom certificate trust or QUIC/UDP443 limitations where supported by evidence. Develop further only from verified owner artifacts. Owner-visible terminology: neutral HTTPS routing and analysis terms.

## v0.32.0 owner target field verification — closed

The owner supplied a v0.32.0 session of com.evrasia. Its HTTP records, route journal, session status and 99/99 checksum verification establish that selected-app direct HTTPS analysis now works for the previously problematic target. Historic notes instructing a future field validation are superseded by this observation.

Next possible investigation: packet loss (615 kernel drops), unassigned ownership (73 of 93 flow entries), and optional per-transaction route source labels. Do not assume these are equivalent to lost HTTP transactions. Do not change implementation without agreeing on scope. Never commit the private Research ZIP or any authentication contents.

## v0.33.0 field usability and completeness follow-up

The simplification is complete and published. Request the owner's field confirmation that precisely two tabs appear, the current HTTPS list updates while interacting with the Android screen, ZIP is created, and existing studies remain accessible. If a new archive is supplied, measure actual packet drops after the new 16-MiB kernel buffer instead of asserting the issue is fixed. Technical workspace tabs remain out of the main window by explicit owner decision; do not restore them without permission.

## v0.34.0 delivery plan

All source in PR #32, branch feature/v0.34-emulator-controls-network-evidence. Await required latest commit tests. Optional six derived ZIP artifacts cannot replace RAW PCAP or HTTP bodies. Avoid false claims from null TLS/DNS fields and temporal correlation. Full update installer must update from published v0.33.0 without deleting app data. Publish only through main pipeline; then user should validate panel controls and target real APK and provide new ZIP to assess DNS/TLS and packet drop results.
