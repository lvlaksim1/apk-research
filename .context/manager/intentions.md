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

Status: **generic routing implemented/released in v0.32.0; owner-specific application verification pending**.

Following the owner archive analysis on 2026-10-08, the owner directed the manager to implement automatic handling/routing of HTTPS traffic emitted by target Android applications that do not use the system proxy, beginning with `com.evrasia`.

Acceptance objective: in a controlled research session, applicable target HTTPS requests and responses should be available in the desktop HTTP/HTTPS viewer and Research ZIP where the technical trust and protocol conditions allow. Preserve independent RAW PCAP provenance, explicit session routing diagnostics, previous installation/update behavior and the known restrictions from v0.30.0.

Next action: re-read the supplied archive (if accessible) and relevant code, establish a narrow viable routing design, implement on a dedicated branch, verify on real Android 15 AVD and affected APK, then deliver via the accepted Setup/Update release process after required acceptance gates. Do not mark this commitment complete merely because the v0.30.0 generic HTTPS test passed.

- source: Owner instruction following analysis of `20261008T020126.928669Z-e336ad57.research.zip`.

## Completed — v0.31.0 ARM64-only APK/XAPK support

Status: **completed and released 2026-10-10**. Owner required support for ARM64-only XAPK rejected by original x86_64-only AVD. Delivered automatic package ABI preflight, separate official Android 15 Google APIs x86_64 image with native ARM translation, original AVD/userdata isolation, root/gRPC/MMAP/ABI validation, and normal XAPK split/OBB handling. Acceptance proved actual ARM64 JNI library execution in an Android 15 test XAPK (`ARM64_NATIVE_LOADED: PASS`), legacy AVD and Windows acceptance, main pipeline #144 attempt 2 and published v0.31.0 assets tied to main `5aab54adc807aff401b59d4c1018795246303b89`.

Owner's actual rejected XAPK still needs field validation. The separate owner HTTPS routing commitment remains ACTIVE.

## Completed — v0.32.0 direct TCP/443 routing to HTTPS analyzer

Owner's 2026-10-10 request was implemented and published. PR #30, main `a2f0bbbca364714d37f7697ffa5ccb8204bc94b1`, pipeline #145 attempt 1 success. A separate Android-local module uses Android's true package UID and original destination to direct only selected-app IPv4 TCP/443 data to the existing HTTPS analyzer; archived route diagnostics and verified cleanup are part of the session. Android 15 live acceptance required both system-proxy and `Proxy.NO_PROXY` HTTPS with nonempty HTTP 200 response bodies (577 bytes each). Windows build, prior-release update and clean provisioning passed. Published Setup and Update assets are available for v0.32.0.

## Active — owner-specific `com.evrasia` verification

The original owner Research ZIP `20261008T020126.928669Z-e336ad57.research.zip` previously showed direct TLS connections and zero readable HTTP records under v0.30.0. User must test their actual APK using published v0.32.0; inspect newly generated `02_normalized/http-transactions.jsonl`, `01_raw/network/https-direct-route.log`, and `02_normalized/http-interception.json`. Do not claim success of this specific APK without real new evidence. App-specific TLS trust and QUIC restrictions remain.

## Completed — com.evrasia field validation on v0.32.0

Status: **completed and proven by the owner's uploaded v0.32.0 session archive on 2026-10-10**.

The user's actual com.evrasia app produced 32 readable HTTP/HTTPS responses (23 on evrasia.spb.ru), with 21 direct target TCP/443 route entries and confirmed cleanup. Session complete with 99/99 archive checksum matches. The former zero-HTTP-transaction problem is solved for the tested session. Do not conflate this with universal TLS compatibility.

Private evidence: owner Research ZIP 20261010T021552.574206Z-3e8e2043.research.zip, NOT to be stored publicly. Its JSON responses include authentication credential fields. No credential values should be entered into any project report, commit, issue or release.

## Observation only — capture completeness and attribution

tcpdump reported 615 kernel-dropped packets out of a session with 22,525 captured packets; flow inventory 93, of which 73 have UNKNOWN ownership attribution. The user has not separately authorized changes to these subsystems; first propose measurable, scoped improvements if requested.

## Completed — simplified Research + live HTTPS user interface (v0.33.0)

Owner requested to remove the other complicated result/analysis tabs and focus on maximum Research ZIP completeness plus live HTTPS requests for the studied application. Implemented only two visible tabs via actual Windows entrypoint, one-click HTTPS access and counter, automatic JSONL updating every 500 ms and completed ZIP viewing; removed technical UI navigation but retained all collectors and data, updater and maintenance in Program menu. Full-length RAW PCAP capture buffer raised to 16 MiB, with no unsupported guarantee of zero packet drops. PR #31, main `3f3f1144e0ea8944a065e7d5950fd07fd1e17abf`, pipeline #146 attempt 1 SUCCESS; versioned standalone setup and update installers released.

## ACTIVE — deliver tested v0.34.0 panel + network ZIP extensions

Source implemented in draft PR #32; v0.34.0 is not yet published. Required remaining steps: latest exact candidate SHA 8c1dbcc full Windows GUI/build/setup/update, Android AVD ZIP verification, full CI. Only then merge to main and wait for main release pipeline to publish two verified installers. Record user-requested UI shape and neutral HTTPS terminology.
