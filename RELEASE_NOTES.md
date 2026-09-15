# Mobile Research v0.7.9

v0.7.9 keeps the v0.7.8 functional baseline and adds one narrowly scoped recovery feature: automatic cleanup of stale Mobile Research Android Emulator processes at application startup.

## Startup cleanup

Before the main window is created, Mobile Research checks Windows for processes belonging specifically to its private AVD `mobile_research_api35`.

A process is eligible only when all of the following are true:

- it is `emulator.exe` or `qemu-system-*.exe`;
- its command line contains the private AVD name;
- its executable/command line points into Mobile Research's managed Android Emulator directory.

This prevents the cleanup from touching unrelated Android Emulator instances.

If stale private processes are found:

1. Mobile Research first requests a clean `adb emu kill`;
2. waits briefly for normal shutdown;
3. terminates only surviving matching process trees;
4. waits until no matching private Emulator process remains;
5. removes stale root-level `*.lock` entries from the private AVD home/profile.

No userdata, configuration, SDK, system image or APK data is deleted.

Generic `adb.exe` is not killed.

If another Mobile Research executable instance is already running, startup cleanup is skipped so the second launch cannot destroy the active instance's Android environment.

## Unchanged

DWM source-window behavior, Android boot logic, reset behavior and the real-time DOWN/MOVE/UP swipe implementation are unchanged from v0.7.8.
