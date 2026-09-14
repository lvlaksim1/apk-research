# Mobile Research v0.7.3

v0.7.3 completes the single-window DWM live UX.

The v0.7.2 real-PC test confirmed that DWM live composition is smooth and correctly synchronized, but the original standalone Emulator window remained visible. The reason was that Mobile Research moved it off-screen only once; Android Emulator/Qt later restored or adjusted its geometry during boot.

## Single visible application window

The Emulator remains a real visible/non-minimized top-level GPU window for DWM, but Mobile Research now treats it as an internal source window:

- the source is moved completely beyond the full Windows virtual desktop;
- the position is re-enforced every 100 ms, so later Qt geometry changes cannot bring it back;
- the source is marked TOOLWINDOW and APPWINDOW is removed, keeping it out of Alt+Tab/taskbar;
- DWM continues rendering the live GPU surface into the Android panel;
- the source is never re-parented, hidden or minimized.

Window discovery uses a 15 ms polling interval during startup to minimize any initial standalone-window flash.

## Shutdown

The shutdown order is now:

1. stop the Android Emulator while the DWM live relationship is still active;
2. unregister the DWM thumbnail;
3. close Mobile Research.

This prevents the standalone Emulator window from becoming visible for a moment when Mobile Research closes.

## Input and fallback

Input still uses the Emulator gRPC stream. If DWM live is unavailable, the existing gRPC/MMAP → gRPC bytes → ADB fallback remains unchanged.

The research evidence pipeline is unchanged.
