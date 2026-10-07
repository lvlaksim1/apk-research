# Current Blockers and Unknowns

Last reconciled: 2026-10-07.

## Product blockers

No known release-blocking product defect is active. v0.28.0 is published and all mandatory release gates passed on exact SHA `df2faf74a707cf99afa366433c34dc89cec37dcc`.

## Update bootstrap boundary

Versions before v0.28.0 do not contain the new updater. Therefore a user on v0.27.0 or older must install v0.28.0 manually once; subsequent supported releases can be discovered/installed from Settings.

The updater intentionally requires Windows installed/frozen application mode for installation. Source/development runs can check code/tests but do not self-install.

## XAPK scope boundary

XAPK supports one base APK, compatible split APKs and optional OBB. Other bundle formats remain separate scope.

## WHPX

WHPX remains advisory/non-publication-gating.
