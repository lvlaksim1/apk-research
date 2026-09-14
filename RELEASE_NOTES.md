# Mobile Research v0.7.8

v0.7.8 is an intentional rollback release.

## Baseline

The complete functional tree is restored to **v0.7.4**.

Changes introduced after v0.7.4 in these areas are not included:

- Emulator startup/window suppression;
- DWM source-HWND discovery changes;
- reset/wipe-data lifecycle changes;
- orphan Emulator cleanup;
- AVD shutdown/recovery changes.

The DWM, startup, reset and AVD behavior is therefore exactly the v0.7.4 implementation.

## Only retained change: real-time swipe

The only functional addition to the v0.7.4 baseline is continuous touch input:

- mouse press → touch DOWN;
- mouse movement while held → streamed touch MOVE;
- mouse release → final MOVE if necessary + touch UP.

MOVE events are rate-limited to roughly 80 Hz to avoid queue buildup.

If gRPC input is unavailable, the existing v0.7.4 ADB tap/swipe fallback remains.

No other runtime behavior is intentionally changed.
