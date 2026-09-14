# Mobile Research v0.7.4

v0.7.4 keeps the working smooth DWM path from v0.7.2 while removing the separate Emulator window from the user experience.

The v0.7.3 test proved that moving the standalone Emulator completely outside the Windows virtual desktop stops its DWM surface from updating and produces a black thumbnail. The source therefore remains on the active desktop in this release.

## Source window hidden by z-order

The primary display path is now:

`Android Emulator visible GPU top-level window → kept directly behind Mobile Research → Windows DWM live thumbnail → Android panel`

The source window is not re-parented, hidden during normal operation, minimized, or moved off-screen.

Instead Mobile Research continuously:

- places the Emulator source fully inside its own top-level screen rectangle;
- scales the source down only when necessary so no edge can protrude beyond Mobile Research;
- keeps the source immediately behind the Mobile Research top-level HWND;
- removes APPWINDOW and applies TOOLWINDOW so the source is absent from taskbar/Alt+Tab.

This preserves the normal standalone GPU surface while ensuring the user only sees the DWM-rendered Android view inside Mobile Research.

## Minimize/restore

When Mobile Research is minimized, the source window is hidden because the covering window is no longer present.

On restore, Mobile Research first places the source behind itself and only then shows it without activation, preserving the single-window UX.

## Tabs

DWM thumbnails are top-level DWM composition objects rather than Qt child widgets. v0.7.4 therefore explicitly controls thumbnail visibility from the tab selection:

- Исследование → DWM live visible;
- Результаты / История / Диагностика / Настройки → DWM live hidden.

Returning to Исследование restores the same live view.

## Fallback and evidence

Input remains on the Emulator gRPC control stream. gRPC/MMAP → gRPC bytes → ADB remains the fallback if DWM is unavailable.

The research evidence pipeline is unchanged.
