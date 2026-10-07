# DEC-20261007 — Direct GitHub self-update

Status: accepted and released.

## Decision

apk-research provides user-controlled application updating from the public `lvlaksim1/apk-research` GitHub Releases.

The Settings tab contains:
- `Проверить обновления`;
- an `Обновить до <version>` button that remains hidden unless a newer stable release is confirmed.

No automatic background polling is performed.

## Release verification boundary

The updater reads `releases/latest`, accepts only a strict stable X.Y.Z tag, and requires the exact versioned Windows installer plus `SHA256SUMS.txt` from the project release.

The installer is downloaded directly from GitHub, locally hashed with SHA-256, and never started if size or digest disagrees with the published release.

## Installation boundary

The running application never overwrites itself. A detached Windows helper waits for the current process to exit, runs the already verified Inno Setup package into the same installation directory, and restarts apk-research only after installer success.

Update installation is forbidden while a research session or another managed operation is active.

## Compatibility

This feature does not alter Android runtime, APK/XAPK intake, capture, Research ZIP schemas or forensic semantics.

## Authority

Explicit owner directive on 2026-10-07; implemented and published in v0.28.0.
