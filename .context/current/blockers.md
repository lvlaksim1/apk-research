# Current Blockers and Unknowns

Last reconciled: 2026-10-08.

## Release blockers

None for the published v0.30.0 baseline.

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
