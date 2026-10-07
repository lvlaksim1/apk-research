# Next Actions

1. Reinstate from this generation and live-reconcile `main`/latest release before changing product code.
2. Treat v0.29.2 / `0f9d949e5158860a51d4e83624fa1cbf3db121cc` as the verified baseline.
3. Preserve the separate Setup/Update installer contract and Inno-owned Windows shortcuts.
4. Preserve SHA-256 verification and GitHub Release publication of both installers.
5. Keep «Открыть главный экран Android» removed.
6. Continue the owner-requested Android home-screen shortcut feature on a clean branch from v0.29.2; do not merge the old Launcher3 experimental branch.
7. Before implementation, establish the supported Launcher3 pinning mechanism for the managed Android 15 AVD. Prefer a platform-supported mechanism over database surgery.
8. Real AVD acceptance must install a genuinely launchable APK/XAPK, allow Launcher3 to stabilize, then prove a visible/launchable home shortcut and prove repeat installation does not duplicate it.
9. Preserve ABI-aware XAPK handling and all evidence/runtime invariants.
10. Do not begin a broader v0.30 roadmap stage until the owner defines it.
