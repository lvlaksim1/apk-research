# Mobile Research v0.7.11

v0.7.11 is the release-ready self-healing build for the specific failure observed on the real PC: the Emulator window and DWM surface exist, but Android inside the AVD never reaches `sys.boot_completed=1`. Runtime behavior is the same as the v0.7.10 implementation; this commit includes the corrected test gate.

## Recovery sequence

Normal boot is unchanged until a real boot stall is detected.

For hardware-accelerated Android, a boot is treated as stalled when either:

- total boot time reaches 150 seconds; or
- ADB has been continuously online for 75 seconds while `sys.boot_completed` remains unset.

Then Mobile Research automatically performs a bounded recovery:

1. stop the current managed Emulator;
2. reuse the existing v0.7.9 stale-process/lock cleanup;
3. restart the same AVD with the same userdata;
4. if that boot succeeds, continue normally;
5. if it stalls again, stop it;
6. launch the same private AVD exactly once with the official Emulator `-wipe-data` flag;
7. allow the clean boot up to 240 seconds;
8. continue APK installation and preparation automatically after success.

The wipe flag exists only for that single recovery launch and is immediately cleared in memory.

## Safety

There is no recovery loop. A single boot sequence can use at most one soft restart and one wipe-data recovery before returning to the existing graphics-profile fallback/error path.

DWM source-window handling, real-time DOWN/MOVE/UP swipe, reset behavior and research evidence collection are otherwise unchanged.
