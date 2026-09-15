# Mobile Research v0.8.6

v0.8.6 removes the compatibility display/input chain and makes the validated embedded runtime the only supported user path.

## Required Windows runtime

```text
Android Emulator -qt-hide-window
        ↓
Emulator gRPC
        ↓
MMAP streamScreenshot
        ↓
AndroidView
```

Input is required to use the persistent Emulator gRPC `streamInputEvent` path.

## Removed

- DWM live presenter and standalone source-window management;
- visible Emulator display fallback;
- gRPC byte-frame framebuffer fallback;
- ADB screencap interactive fallback;
- unary sendTouch/sendKey fallback;
- ADB tap/swipe/key/text fallback;
- Windows graphics/display profile ladder.

A failure in the required display or input transport is now surfaced as an explicit Mobile Research error.

## Preserved recovery

The following are intentionally retained because they restore the same required architecture rather than switching to another mode:

- cleanup of stale processes belonging only to the private Mobile Research AVD;
- stale AVD lock cleanup after those processes are gone;
- one official `-wipe-data` launch after a guest boot stall;
- virtualization/hypervisor diagnostics and setup.

If the clean AVD still stalls, or required gRPC/MMAP cannot operate, startup fails.

## Validation changes

- the first gRPC/MMAP frame is now a preparation gate;
- framebuffer worker failures are no longer silently swallowed;
- input failures are surfaced instead of falling back;
- Windows runtime acceptance validates an actual `grpc-mmap` frame;
- Linux/KVM acceptance remains headless at the window-system level but uses the same required gRPC/MMAP transport.

The v0.8.2 display orientation and smooth DOWN/MOVE/UP behavior remain unchanged.
