# Mobile Research v0.7.6

v0.7.6 fixes the DWM regression seen in the v0.7.5 real-PC test while keeping the new real-time swipe behavior.

## What failed in v0.7.5

Launching Android Emulator with a hidden Windows startup state changed the top-level-window discovery race.

The Emulator process owns several Qt/helper top-level HWNDs. Because Mobile Research allowed hidden windows during discovery, it could select a helper HWND by process ancestry before the real user-facing Emulator window became visible.

The result matched the test exactly:

- the real Android Emulator remained visible as a separate window;
- DWM was attached to the wrong source HWND;
- the Android panel inside Mobile Research showed a blank/white surface.

## v0.7.6 source selection

The DWM source is again discovered from visible top-level windows.

Candidate selection now explicitly prefers windows whose title identifies:

- Android Emulator;
- or the managed AVD name.

A same-process helper window can no longer win merely because it is larger.

Once the exact Emulator HWND is found:

1. Mobile Research briefly hides that confirmed HWND;
2. applies TOOLWINDOW / removes APPWINDOW;
3. places it fully behind the Mobile Research window;
4. shows it again without activation;
5. registers the DWM thumbnail.

This keeps the proven working GPU/DWM behavior from v0.7.4 while reducing the initial standalone flash without hiding the process before its real window can be identified.

## Input

The v0.7.5 real-time touch path is unchanged:

- mouse down → touch DOWN;
- movement → streamed MOVE;
- mouse release → UP.

The research evidence pipeline and fallback transports are unchanged.
