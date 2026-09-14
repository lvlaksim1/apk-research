# Mobile Research v0.7.7

v0.7.7 fixes the reset/crash/orphan-Emulator sequence found in the real-PC v0.7.6 test.

## Root cause

The old reset implementation did:

1. request Emulator shutdown;
2. wait only briefly for the launcher process;
3. immediately delete AVD userdata files.

Android Emulator can keep qemu child processes and AVD locks alive after the launcher changes state. This allowed reset to race the still-running Emulator.

The next launch then failed with:

`Another emulator instance is running. Please close it...`

At the same time DWM/controller state was not explicitly invalidated, so the UI could keep referring to a dead source HWND and stale display state.

## Atomic clean reset

Reset now performs a controlled transaction:

1. detach DWM and suspend frame publishing;
2. close gRPC;
3. request `adb emu kill`;
4. wait for ADB to go offline and the owned launcher to exit;
5. on Windows, terminate only residual emulator/qemu processes whose command line belongs to the private `mobile_research_api35` AVD;
6. write a persistent `reset-userdata.pending` marker;
7. clear the installed package state.

No live AVD files are manually deleted.

On the next managed boot Mobile Research adds the official Emulator `-wipe-data` flag. The marker is removed only after Android boots successfully, so the reset remains pending even if Mobile Research is closed in between.

## Recovery after an earlier crash

If Mobile Research starts and sees `emulator-5554` online but has no process owned by the current application instance, it treats that Emulator as an orphan left by a prior crash.

The private orphan is stopped first, then a fresh owned Emulator is started. This automatically repairs the exact state produced by the v0.7.6 test and prevents the AVD single-instance lock from poisoning later launches.

## Display state

Reset and component repair explicitly invalidate DWM/controller display state and stale frames. The UI reports Android as reset and requires the APK to be installed again before research can start.

The v0.7.5 real-time touch DOWN/MOVE/UP behavior is unchanged.
