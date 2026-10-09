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

## Active — HTTPS traffic of applications that bypass the Android system proxy

Status: **active / implementation not verified**.

Following the owner archive analysis on 2026-10-08, the owner directed the manager to implement automatic handling/routing of HTTPS traffic emitted by target Android applications that do not use the system proxy, beginning with `com.evrasia`.

Acceptance objective: in a controlled research session, applicable target HTTPS requests and responses should be available in the desktop HTTP/HTTPS viewer and Research ZIP where the technical trust and protocol conditions allow. Preserve independent RAW PCAP provenance, explicit session routing diagnostics, previous installation/update behavior and the known restrictions from v0.30.0.

Next action: re-read the supplied archive (if accessible) and relevant code, establish a narrow viable routing design, implement on a dedicated branch, verify on real Android 15 AVD and affected APK, then deliver via the accepted Setup/Update release process after required acceptance gates. Do not mark this commitment complete merely because the v0.30.0 generic HTTPS test passed.

- source: Owner instruction following analysis of `20261008T020126.928669Z-e336ad57.research.zip`.
