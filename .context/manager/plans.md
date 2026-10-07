# Manager plans

## Default change/release plan

1. Reinstate from `context` and reconcile live `main`, latest release and CI.
2. Use a dedicated feature/fix branch from the verified baseline.
3. Make the minimum coherent change.
4. Run unit/compile plus relevant real AVD and Windows verification.
5. For updater changes, prove a real previous-release → candidate update with the dedicated Update installer.
6. Publish stable releases only through the main pipeline.
7. Persist verified state and reseal manager integrity.

## Current release architecture

Stable releases publish:
- `apk-research-setup_v<version>.exe`;
- `apk-research-update_v<version>.exe`;
- `SHA256SUMS.txt` covering both.

The application updater uses only the dedicated Update asset.

## Current product work

No additional product feature stage is currently authorized.

The Android home-screen shortcut requirement was cancelled by the owner on 2026-10-08 and must not be resumed without a new explicit directive.

Until a new owner task arrives:
- treat v0.29.2 as the verified baseline;
- preserve the separate Setup/Update installer contract;
- keep «Открыть главный экран Android» removed;
- preserve ABI-aware XAPK handling and all evidence/runtime invariants.
