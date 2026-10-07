# Manager intentions and commitments

## Completed — v0.29.2 MailRu-style installer model
Status: completed and released.

Owner direction: inspect the working update installer and application shortcut implementation in `lvlaksim1/mailru-desktop` and make apk-research use the same Windows installation/update approach.

Delivered:
- dedicated full Setup installer;
- dedicated Update installer;
- latest-release discovery selects only Update;
- SHA-256 verification retained;
- direct Windows-shell launch of Update followed by application exit;
- Inno-owned Start-menu/optional desktop shortcut creation and refresh;
- no uninstall-first behavior;
- redundant Android Home button removed;
- GitHub Release contains Setup + Update + SHA256SUMS.

Completion evidence: PR #24 and main pipeline #141 passed mandatory CI/AVD/Windows/release gates.

## Active — Android home-screen shortcut after APK/XAPK install
Status: open owner requirement; not released.

Required behavior:
- after successful APK/XAPK installation, the Android application launch shortcut should be visible on the managed Android home screen;
- there must be no separate user-facing Home button.

Important history:
- direct LauncherProvider insertion and direct Launcher3 database manipulation were researched on the managed Android 15 AVD;
- those experimental implementations were not merged because the final shortcut state was not reliably verified across Launcher3 reload/reconciliation;
- do not merge the old experimental branch as-is;
- continue this as a narrowly scoped Android-emulator feature from the verified v0.29.2 baseline.

## Active — continuity and release integrity
Status: active.

Reconcile live product/release/CI before consequential changes and preserve all verified evidence/runtime boundaries.
