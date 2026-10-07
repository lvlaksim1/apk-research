# apk-research v0.29.2 — Automatic Home Shortcut

v0.29.2 completes the emulator installation workflow requested by the owner.

## Simplified controls

- Removes «Открыть главный экран Android».
- Keeps «Установить в эмулятор».
- Keeps «Запустить приложение».

## Home shortcut after install

After a successful APK/XAPK install, apk-research automatically:
- resolves the installed package launcher activity;
- adds a non-duplicate shortcut to a free Launcher3 home-screen cell;
- verifies the shortcut record;
- reloads the managed launcher and shows the Android home screen.

The shortcut uses the application label reported by `aapt2` and launches the package's standard MAIN/LAUNCHER activity.

## Verification

The real Android AVD acceptance uses a synthetic launchable XAPK and requires the installed package to appear in the Launcher3 favorites model after installation.

## Compatibility

- ABI-aware XAPK handling is unchanged.
- OBB deployment is unchanged.
- v0.29.1 self-update handoff is unchanged.
- Research capture and all evidence semantics are unchanged.
