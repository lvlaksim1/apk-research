# Mobile Research v0.8.4

v0.8.4 is the second technical-cleanup release. It removes legacy native-HWND terminology and dead code left by the v0.5-v0.7 display experiments without changing the validated runtime behavior.

## Preserved

- primary `-qt-hide-window + gRPC/MMAP` display path;
- top-down framebuffer contract;
- persistent gRPC DOWN/MOVE/UP input and smooth swipe;
- DWM live as the last compatibility fallback;
- one-shot `-wipe-data` guest boot recovery from v0.8.3;
- evidence collectors and Research ZIP pipeline.

## Cleaned up

The active DWM implementation was still stored in `native_emulator.py` and exposed names such as `NativeEmulatorEmbedder`, even though the rejected SetParent/native HWND architecture had already been removed.

v0.8.4 makes the active architecture explicit:

- `native_emulator.py` is replaced by `dwm_emulator.py`;
- `NativeEmulatorEmbedder` becomes `DwmEmulatorPresenter`;
- controller/UI native-display state and signals become DWM-specific;
- AndroidView no longer requests its own native HWND through `WA_NativeWindow`;
- unused Win32 virtual-screen definitions, the no-op focus helper and the unused detach restore argument are removed;
- the dead `tapRequested → controller.tap` GUI path is removed.

The DWM fallback itself remains functional and retains its source-window discovery, toolbar cropping, z-order covering and thumbnail presentation logic.

## Result

The active display architecture now has only two clearly separated implementations:

1. primary framebuffer path: hidden Emulator → gRPC/MMAP → AndroidView;
2. compatibility DWM path: visible standalone Emulator source → DWM thumbnail presenter.

There is no active SetParent/native-HWND embedding path.
