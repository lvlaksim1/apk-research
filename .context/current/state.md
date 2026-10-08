# Current Project State

Last reconciled: 2026-10-08.

## Product

- Current release/main commit: `1d75ec32d80cdea2af172035d43d12d3284978fa`.
- Latest release: `v0.30.0`.
- Full installer: `apk-research-setup_v0.30.0.exe`.
- Update installer: `apk-research-update_v0.30.0.exe`.
- Setup SHA-256: `6f9f39c67a88344e7181316c6c6445660f2e1d066deaca09ba13f1ec20954e1a`.
- Update SHA-256: `4189ff6af7c793bef0db99c673b5838d0a8e6a7ad039cb80b688012353484e1a`.
- Latest release target verified live on 2026-10-08: exact main SHA above.

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

v0.30.0 is the verified baseline. The requested HTTPS traffic display stage is complete. No further product stage is authorized yet.
