# Mobile Research v0.7.12

v0.7.12 fixes the repeated 150-second recovery cycle observed in the real-PC test.

## What was wrong

The previous self-healing logic correctly detected an Android boot timeout, but a failed recovery could then fall back into the existing graphics-profile loop.

That was inappropriate for this failure class: the Emulator process and DWM were alive, while the guest Android itself was not reaching `sys.boot_completed=1`.

As a result the program could repeatedly start another normal 150-second boot under the next graphics profile.

## v0.7.12 behavior

A boot stall is now treated as an AVD/guest-state failure.

The recovery path is strictly bounded:

1. normal boot stalls;
2. Mobile Research stops the managed Emulator;
3. stale private processes/locks are cleaned;
4. the same private AVD is launched exactly once with official `-wipe-data`;
5. the clean boot gets up to 240 seconds;
6. if it succeeds, normal APK preparation continues;
7. if it fails, Mobile Research stops and reports an error.

There is no soft restart and no graphics-profile fallback after a boot stall.

Graphics-profile fallback is still retained for genuine Emulator startup/graphics failures where the process exits or fails before Android boot can be evaluated.

DWM and real-time swipe code are unchanged.
