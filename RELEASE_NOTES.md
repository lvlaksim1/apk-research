# apk-research v0.29.0 — Icon, ABI-aware XAPK and Emulator Controls

v0.29.0 is a corrective usability/runtime release.

## Application icon

- Adds a dedicated apk-research icon based on Android research: phone + Android + magnifier.
- The same icon is used by the Qt window, Windows executable, installer and shortcuts.

## XAPK ABI compatibility

- Reads the running emulator ABI list before installation.
- Parses `native-code` from every APK member.
- Excludes incompatible native ABI split APKs before `adb install-multiple`.
- Rejects a genuinely incompatible package before installation with a clear package/emulator ABI explanation.
- Preserves non-ABI splits and the existing one-base/package/version safety checks.

## Emulator application controls

- File selection is now separate from installation.
- Adds «Установить в эмулятор».
- Adds «Запустить приложение».
- Adds «Открыть главный экран Android».

## In-place updates

- The updater passes `/UPDATE=1` to the verified release installer.
- The installer reuses the existing application directory, program group and tasks.
- The existing installation is not uninstalled before update.
- User settings and Research ZIP data are preserved.

## Compatibility

- Research collectors and evidence schemas are unchanged.
- Hidden Emulator → gRPC/MMAP → AndroidView remains unchanged.
- v0.10.5 clean-launch sequencing remains protected.
- v0.24–v0.28 forensic semantics remain unchanged.
