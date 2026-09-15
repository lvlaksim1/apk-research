# Mobile Research v0.8.3

v0.8.3 is a technical-cleanup release built on the real-PC validated v0.8.2 runtime.

## Preserved stable baseline

The following v0.8.2 behavior is intentionally unchanged:

- hidden `-qt-hide-window` Emulator startup;
- gRPC/MMAP framebuffer presentation;
- top-down display orientation;
- display/touch coordinate agreement;
- persistent gRPC DOWN/MOVE/UP input;
- smooth swipe response;
- DWM only as a last-resort compatibility fallback;
- research collectors and Research ZIP evidence pipeline.

## Boot recovery cleanup

The previous runtime still contained an older two-stage recovery path:

`soft restart → wipe-data → possible graphics-profile fallback`.

Real-PC testing had already shown that the soft restart did not repair the affected AVD and could extend the wait through additional boot cycles.

v0.8.3 replaces that path with a strict failure-class policy:

1. process/graphics startup failures may use the normal compatibility profile ladder;
2. once the Emulator process is alive but Android fails to reach `sys.boot_completed=1`, the problem is classified as a guest/AVD boot stall;
3. Mobile Research performs exactly one official `-wipe-data` recovery launch on the same selected profile;
4. the clean AVD receives an extended boot timeout;
5. if it still stalls, startup stops and reports the failure;
6. no soft restart and no new graphics-profile cycling occurs after a guest boot stall.

## Documentation cleanup

- `docs/V0.2_DESKTOP.md` now describes the actual gRPC/MMAP embedded architecture instead of the obsolete ADB-screenshot design.
- The release-gate documentation now matches the workflow: CI, AVD Research Acceptance and Desktop Build block publication; Windows WHPX Acceptance is currently advisory.
- `REFACTORING.md` now contains an explicit active runtime contract and marks the older two-stage boot-recovery ADR as superseded.
- The obsolete v0.2.0rc1 pull request is closed as historical.
