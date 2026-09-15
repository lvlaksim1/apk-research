# Mobile Research v0.8.0

v0.8.0 removes the startup-window race from the normal architecture instead of trying to hide a visible Emulator window after it appears.

## Primary startup sequence

On Windows the normal startup sequence is now:

1. Mobile Research starts the managed Android Emulator with `-qt-hide-window`.
2. The Emulator therefore has no normal user-visible desktop window.
3. Mobile Research waits briefly for the local Emulator gRPC service.
4. As soon as gRPC is ready, the controller starts the framebuffer worker.
5. The worker consumes `streamScreenshot`, preferring MMAP transport.
6. Android boot frames are painted directly by `AndroidView`.
7. Input continues through persistent gRPC `streamInputEvent`.
8. Android boot completion, root ADB and APK preparation continue independently.

There is no HWND discovery, Z-order manipulation or DWM thumbnail in the successful primary path.

## Windows compatibility order

1. embedded gRPC/MMAP + GPU host;
2. embedded gRPC/MMAP + GPU auto;
3. headless SwiftShader compatibility;
4. DWM live + GPU host compatibility;
5. DWM live + GPU auto compatibility.

DWM remains available only as a last-resort compatibility fallback.

## Early display

The framebuffer worker starts before `sys.boot_completed`, so the user can see the actual boot framebuffer inside Mobile Research.

If gRPC is not ready at the instant the worker starts, the worker can temporarily use ADB screenshots and automatically upgrade to gRPC/MMAP when the client becomes available.

## Unchanged

- real-time mouse DOWN/MOVE/UP swipe behavior;
- evidence collection;
- root/ADB preparation;
- research ZIP pipeline;
- DWM fallback implementation itself.
