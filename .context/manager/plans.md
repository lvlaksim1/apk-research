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

## Next product work

The outstanding owner-requested corrective feature is Android home-screen placement after APK/XAPK installation:
- keep the Home button removed;
- do not modify the verified Windows Setup/Update architecture;
- do not merge the abandoned Launcher3 experimental branch;
- start from v0.29.2 on a clean branch;
- first select a mechanism that is actually supported by the managed Android/Launcher3 environment;
- acceptance must install a genuinely launchable APK/XAPK on the real managed AVD and prove the resulting shortcut is visible/launchable after Launcher3 stabilization, not merely that a database/provider write returned success.

No broader v0.30 feature stage is authorized.
