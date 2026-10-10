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
