# apk-research v0.28.0 — Direct GitHub Self-Update

v0.28.0 adds user-controlled application updates directly from the latest stable GitHub Release.

## Settings

- Adds «Проверить обновления».
- Shows «Обновить до <version>» only when GitHub reports a strictly newer stable release.
- Displays current version, discovery status and download progress.
- Does not poll for updates in the background.

## Direct GitHub release verification

- Queries `https://api.github.com/repos/lvlaksim1/apk-research/releases/latest`.
- Requires the exact `apk-research-setup_v<version>.exe` asset.
- Requires the release `SHA256SUMS.txt`.
- Downloads both directly from the project GitHub Release.
- Computes SHA-256 locally and refuses installation on digest or size mismatch.

## Safe application handoff

- The running apk-research process never overwrites itself.
- After verification, a detached Windows helper waits for the current process to exit.
- The verified Inno Setup package updates the same installation directory silently.
- apk-research is started again after a successful installer exit.

## Compatibility

- APK/XAPK package intake is unchanged.
- Android runtime and research collectors are unchanged.
- Research ZIP schemas and evidence semantics are unchanged.
- Hidden Emulator → gRPC/MMAP → AndroidView and v0.10.5 startup/clean-launch sequencing remain protected.
