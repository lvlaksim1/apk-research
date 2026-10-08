# Manager intentions and commitments

## Completed — v0.30.0 HTTPS traffic display
Status: completed and released.

Owner requirement: display actual decrypted HTTPS application traffic in apk-research, not only TLS/QUIC metadata.

Delivered:
- application-managed local HTTPS proxy bundled with the Windows application;
- automatic managed-emulator routing through `adb reverse`;
- temporary trusted research CA for the rooted Android 15 environment;
- HTTP transaction evidence in Research ZIP;
- request/response headers and bodies where decryption succeeds;
- dedicated HTTP/HTTPS viewer with search and readable bodies;
- explicit provenance preserving the distinction from passive RAW PCAP;
- real Android 15 acceptance proving `https://example.com/` with status 200 and non-empty response body;
- successful v0.29.2 → v0.30.0 dedicated update verification.

Completion evidence: PR #26 merged; main pipeline #143 passed mandatory CI, real AVD, Windows build/update/install and release gates; GitHub Release v0.30.0 published.

Known bounded limitations:
- certificate pinning or application-owned trust stores may reject the research CA;
- HTTP/3/QUIC content decryption is not claimed.

## Completed — v0.29.2 MailRu-style installer model
Status: completed and preserved in v0.30.0.

Separate Setup and Update installers, Update-only discovery, SHA-256 verification, direct Windows-shell launch and Inno-owned shortcut refresh remain the release architecture.

## Cancelled — Android home-screen shortcut after APK/XAPK install
Status: cancelled by owner on 2026-10-08.

Do not resume this work unless explicitly reopened.

## Active — continuity and release integrity
Status: active.

Reconcile live product/release/CI before consequential changes and preserve all verified evidence/runtime boundaries.
