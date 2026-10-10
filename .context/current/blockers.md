# Current Blockers and Unknowns

Last reconciled: 2026-10-10.

## Release blockers

None for the published v0.31.0 baseline. Main pipeline #144 succeeded after retrying intermittent ADB Settings start failure.

## HTTPS traffic analysis boundaries

Not release blockers:
- applications with certificate pinning may reject the research CA;
- applications with their own trust store may reject the research CA;
- HTTP/3/QUIC content decryption is not part of the v0.30.0 acceptance contract.

These require concrete target evidence before any follow-up work is defined.

## Android home-screen shortcut

Not a blocker. The owner cancelled this requirement on 2026-10-08.

## WHPX

WHPX remains advisory/non-publication-gating.

## Active owner-target gap after v0.30.0

The prior-chat `com.evrasia` archive reportedly contains direct remote HTTPS connections but no readable HTTP transaction evidence. The generic system-proxy implementation does not cover an application that bypasses that proxy. Root cause at the precise socket/routing level and a robust automatic routing solution have not been validated in this reinstantiated runtime. Certificate-specific causes must not be asserted for this case without packet/proxy evidence. This is an active owner-target requirement, not a retroactive blocker to the already published v0.30.0.

## ARM64 XAPK boundaries

The official Android 15 Google APIs x86_64 image advertises ARM64 native translation and has executed an actual ARM64 JNI library from synthetic XAPK. No owner-specific original XAPK was provided for field testing. App-specific services/device checks may still limit launch; additional Android image download is expected on first use. Not a release blocker.
