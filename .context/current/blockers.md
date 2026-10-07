# Current Blockers and Unknowns

Last reconciled: 2026-10-08.

## Release blockers

None for the published v0.29.2 baseline.

## Android home-screen shortcut — open

Owner requirement: successful APK/XAPK installation should leave a visible launch shortcut on the managed Android home screen, with no separate Home button.

What has been learned:
- MailRu Desktop shortcut handling is a Windows/Inno mechanism and does not provide an Android analogue.
- Managed Android 15 uses Launcher3.
- Legacy `INSTALL_SHORTCUT` broadcast is not a valid modern solution.
- Direct LauncherProvider insertion returned success-like behavior but the shortcut was not reliably present after Launcher3 reconciliation.
- Direct Launcher3 SQLite manipulation exposed WAL/cache/reload ordering issues; experimental versions were not sufficiently reliable and were not merged.
- Some early synthetic XAPK acceptance packages were not representative launchable apps; later acceptance work moved toward a real MainActivity/DEX package.

Do not treat a successful provider/database write alone as acceptance. The gate must prove a stable, visible, launchable shortcut after Launcher3 has settled.

## Experimental branch

The prior Launcher3 experiment branch is research history only. It must not be merged into main as-is. Future work should start from the verified v0.29.2 baseline and reuse only individually proven findings.

## WHPX

WHPX remains advisory/non-publication-gating.
