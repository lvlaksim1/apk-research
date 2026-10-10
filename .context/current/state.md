# Current Project State

Last reconciled: 2026-10-10.

## Product

- Current release/main commit: `5aab54adc807aff401b59d4c1018795246303b89`.
- Latest release: `v0.31.0`.
- Full installer: `apk-research-setup_v0.31.0.exe` (SHA256 `8c253edf38759830fbe8e156282beaa1b2f0f9b98fd6ad3d880679d180176b83`).
- Update installer: `apk-research-update_v0.31.0.exe` (SHA256 `cb41c928aa2fadeb92bf2c17026cc3863e4d094a0cc5fa92a279597d10baabc6`).
- Main pipeline #144 attempt 2 SUCCESS (2026-10-10); GitHub Release targets exact main SHA.

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
