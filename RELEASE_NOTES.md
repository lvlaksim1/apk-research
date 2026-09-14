# Mobile Research v0.7.5

v0.7.5 focuses on the two remaining interaction polish issues from the v0.7.4 real-PC test.

## Real-time swipe/drag

Mouse dragging no longer waits for mouse release before Android receives a swipe.

The Android panel now sends the same lifecycle as a real touchscreen:

- mouse button down → gRPC touch DOWN;
- cursor movement while held → continuous gRPC touch MOVE;
- mouse button release → final MOVE if needed + touch UP.

MOVE delivery is throttled to roughly 80 Hz to keep latency low without allowing a high-DPI mouse to flood the controller queue.

This means Android scrolling should follow the mouse while the button is still held, matching the feel of the standalone Emulator much more closely.

If gRPC input is unavailable, the existing ADB swipe/tap fallback is retained.

## Startup flash

The standalone GPU source window is still required for the working DWM path, but it should no longer visibly flash outside Mobile Research during boot.

For DWM-live launches on Windows:

1. the Emulator process receives STARTUPINFO with an initial hidden show state;
2. Mobile Research discovers the top-level HWND even while it is hidden;
3. the window is positioned completely behind Mobile Research;
4. only then is it shown without activation;
5. DWM displays its live GPU surface inside the Android panel.

HWND discovery now polls at 5 ms during this short startup phase as an additional guard.

## Existing DWM behavior

The source window remains a normal top-level GPU window and is not re-parented or moved off the active desktop. It stays behind Mobile Research and outside taskbar/Alt+Tab.

DWM remains visible only on the Исследование tab.

The research evidence pipeline is unchanged.
