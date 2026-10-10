# Current Blockers and Unknowns

Last reconciled: 2026-10-10.

## Release blockers

None for published v0.33.0. Main pipeline #146 attempt 1 passed all mandatory gates.

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

The prior-chat `com.evrasia` archive reportedly contains direct remote HTTPS connections but no readable HTTP transaction evidence. The v0.32.0 selected-app direct IPv4 TCP/443 routing solution has passed live Android 15 acceptance; however, the original owner `com.evrasia` case has NOT been re-tested under v0.32.0. A new Research ZIP is needed for target-specific validation. Certificate-specific causes must not be asserted for this case without packet/proxy evidence. This is an active owner-target requirement, not a retroactive blocker to the already published v0.30.0.

## ARM64 XAPK boundaries

The official Android 15 Google APIs x86_64 image advertises ARM64 native translation and has executed an actual ARM64 JNI library from synthetic XAPK. No owner-specific original XAPK was provided for field testing. App-specific services/device checks may still limit launch; additional Android image download is expected on first use. Not a release blocker.

## v0.32.0 limits and target field verification

The owner-specific `com.evrasia` deployment is not yet verified, although the general routing mechanism has passed a real `Proxy.NO_PROXY` Android 15 HTTPS test. No assumption about that app's TLS trust, certificate restrictions, IPv6 or UDP/QUIC behavior is warranted. The isolated rule only addresses IPv4 TCP/443 by installed package UID. The owner needs a new Research ZIP and route log for authoritative conclusion. This is not a blocker to published v0.32.0.

## Findings after actual v0.32.0 com.evrasia validation

The direct HTTPS routing capability is no longer awaiting target proof: the actual app produced 32 readable responses and 21 route journal entries to its server. This closes the prior field-verification blocker for the observed run.

Quality observations, not blockers to the v0.32.0 publication: 615 kernel packet drops in tcpdump; 73 of 93 network flow entries UNKNOWN for ownership attribution. No evidence that these caused missing HTTP transactions. Scope remains IPv4 TCP/443 and certificate trust assumptions remain bounded. The owner ZIP contains authentication data, so it must not be copied to public project storage.

## Follow-up limitations after v0.33.0

The 16-MiB kernel tcpdump buffer is a preventative improvement; zero packet drops are not proven and must be measured in a future owner ZIP. Live HTTPS rows represent completed request/response transaction records as written by the analyzer; they are not evidence that all encrypted transport data became readable. Default/Google APIs AVD and all prior known protocol/trust boundaries remain. Technical tabs were intentionally removed from main navigation by owner request, without deleting ZIP evidence.

## v0.34.0 release gate pending

New code not yet in main; no v0.34.0 installer link to offer. Final PR SHA 8c1dbcc acceptance pending; earlier Android runner had intermittent ADB 255 on starting Settings, then later identical base AVD acceptance passed without changing startup code. This is a release gate, not demonstrated regression of new network parser. Historic observed com.evrasia direct HTTPS on v0.32 remains proven. Keep v0.33.0 as last stable release until v0.34 acceptance.
