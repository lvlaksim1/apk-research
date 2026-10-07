# Current Blockers and Unknowns

Last reconciled: 2026-10-07.

## Product blockers

No known release-blocking product defect is active. v0.29.0 is published and all mandatory release gates passed on exact SHA `81a565dbc3b4c41712b8a6e3c3ba8020060ff5a2`.

## XAPK architecture boundary

ABI-aware selection now prevents known incompatible split APKs from being passed to install-multiple and gives explicit diagnostics when the package has no ABI compatible with the emulator.

If a future XAPK uses packaging conventions not represented by aapt2 native-code metadata, treat that as a new compatibility case rather than weakening validation.

## Update boundary

v0.28.0+ can self-update through Settings. v0.29.0 changes the install path to explicit in-place update mode; the updater still requires the verified installer and SHA256SUMS.

## WHPX

WHPX remains advisory/non-publication-gating.
