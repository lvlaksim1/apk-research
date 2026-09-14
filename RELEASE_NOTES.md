# Mobile Research v0.7.1

v0.7.1 replaces cross-process `SetParent` embedding with DWM live composition and includes the final Win32 thumbnail-handle correction from the implementation pass.

The real-PC v0.6.0 test proved that Mobile Research could find and re-parent the correct standalone Android Emulator window, but the Emulator GPU surface stopped rendering after the parent change. The original standalone window rendered normally again when Mobile Research closed. This release therefore removes `SetParent` from the active display architecture.

## DWM live presentation

The primary Windows path is now:

`Android Emulator standalone GPU window → Windows DWM → Mobile Research Android panel`

The Emulator remains a normal top-level Qt/GPU window. Mobile Research registers a DWM thumbnail relationship using its own top-level window as the destination and the Emulator top-level window as the source. The live destination rectangle is aligned to the Android panel.

No Android frame is copied by Python or QPainter in DWM mode.

## Source-window handling

After DWM registration and the first successful thumbnail update:

- the standalone Emulator window is moved outside the visible virtual desktop;
- it is not hidden or minimized, so DWM can continue composing it;
- it is not re-parented;
- it is not restored during Mobile Research shutdown, preventing the second-window flash seen in v0.6.0.

The Emulator side toolbar is cropped from the source rectangle when the phone content aspect can be inferred.

## Input

Mouse, swipe, keyboard and text input remain on the existing persistent Emulator gRPC control stream. Presentation and input are therefore independent.

## Fallback

If DWM composition, source-window discovery or thumbnail registration fails, Mobile Research automatically keeps using:

1. gRPC/MMAP framebuffer;
2. gRPC bytes;
3. ADB screenshot/input fallback.

The evidence pipeline is unchanged.

## Research core

No evidence collector is replaced or weakened:

- ADB target management;
- root;
- raw PCAP/tcpdump;
- logcat;
- screen recording;
- package metadata;
- Research ZIP;
- semantic audit.
