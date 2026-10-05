# Dialogue evidence — scrcpy v5.0 applicability review

Date: 2026-10-06
Source repository: Genymobile/scrcpy
Source revision: 19871982cefb9de4c981c2314dfda2ac81564b48
Reviewed release: v5.0, published 2026-10-05

## Purpose

Assess scrcpy as an engineering reference for apk-research without replacing the proven Emulator gRPC/MMAP runtime by assumption.

## Verified scrcpy architecture

scrcpy is split into a host client and a temporary Android-side Java server executed as shell via app_process. The server is pushed to /data/local/tmp and communicates over long-lived video, audio and control sockets. Video is captured to a Surface and encoded by MediaCodec. Control injects Android input events and supports clipboard/device messages. The host decodes media using FFmpeg/SDL.

The default tunnel direction uses adb reverse with the host listening before the Android server starts. This reverses the application-level client/server network roles and removes the need to poll for a device-side listening socket.

The current v5.0 host supports hardware video decoding, including D3D11VA on Windows, with automatic software fallback.

## High-value findings for apk-research

### 1. Do not replace the current live Emulator display path with scrcpy video

apk-research already receives local Emulator RGBA frames through gRPC/MMAP and renders them directly. Replacing this with MediaCodec encode on Android plus host decode would add compression/decompression and hidden-API dependencies without a demonstrated benefit for the local managed Emulator.

The proven apk-research live path remains:
hidden Emulator -> Emulator gRPC -> MMAP framebuffer -> AndroidView.

### 2. Android-side sidecar is a strong architecture candidate for new evidence collectors

A small app_process server running as shell could provide persistent event-driven collection without repeated adb shell process startup. If introduced, it should be an additional bounded collector/control sidecar, not a replacement for the established Emulator display/input transport.

Useful scrcpy patterns:
- push a version-pinned jar to /data/local/tmp;
- execute with app_process as shell;
- exact client/server version handshake;
- separate long-lived channels by concern;
- host-listen + adb reverse startup to avoid polling races;
- cleanup with nothing installed persistently on Android.

### 3. Continuous screen evidence is a high-value candidate

apk-research currently uses Android screenrecord chunks because screenrecord is time-limited. scrcpy demonstrates continuous Surface -> MediaCodec streaming until explicitly stopped, with device-generated packet PTS.

A future experimental collector could therefore:
- eliminate periodic screenrecord chunk rotation;
- avoid possible evidence gaps at chunk boundaries;
- preserve per-packet/device presentation timestamps;
- mux/store the stream on the host;
- keep current screenrecord as the accepted baseline until real Research ZIP comparison proves equivalence or improvement.

### 4. Audio evidence is currently missing and scrcpy provides a mature reference

scrcpy captures Android output/playback/microphone via AudioRecord and can encode Opus/AAC/FLAC or preserve raw PCM. On the project's managed API 35 Emulator these APIs are available.

Potential apk-research addition:
- optional audio collector with explicit source and capture semantics;
- store audio plus timing/provenance metadata in Research ZIP;
- never imply completeness where Android playback capture permits app opt-out;
- document any behavior change such as REMOTE_SUBMIX affecting local playback.

### 5. Multi-touch gesture support can be added without changing transport

scrcpy's control layer supports synthetic multi-touch gestures such as pinch/rotate/tilt. apk-research's Emulator gRPC schema already supports repeated Touch entries but AndroidView currently emits one touch identifier.

This is a low-risk UX improvement:
- Ctrl+drag pinch/rotate or another explicit gesture mode;
- preserve multi-pointer actions in Timeline;
- keep the existing persistent gRPC input stream.

### 6. PositionMapper is a useful robustness model

scrcpy uses affine transforms for crop/orientation/resize and rejects stale input generated against an outdated video size after rotation. apk-research currently maps ratios using current frame dimensions and a simpler rotation mapping.

No immediate replacement is required for the current fixed Emulator display. If crop, virtual display, arbitrary rotation or dynamic display geometry is added, adopt the invariant:
an input event is valid only for the display geometry generation from which it was produced.

### 7. Virtual display is useful only as an optional research mode

scrcpy can create a touch-capable virtual display, set size/DPI/IME policy, launch an app on that display and dynamically resize it. This could provide a controlled app-only viewport.

For apk-research it must not replace the default environment because running an app on a secondary/virtual display can change app behavior and therefore the evidence environment. Treat it as an explicit experimental mode with the display topology recorded in session metadata.

### 8. App discovery/start patterns are useful, but the proven clean-launch path stays authoritative

scrcpy enumerates launchable apps through PackageManager and starts them through ActivityManager with a target display ID. This is useful reference for richer package metadata and virtual-display launch.

apk-research's proven v0.10.5 clean launch and am start -W sequencing must remain unchanged unless a real defect justifies replacement.

### 9. Clipboard/keyboard improvements are useful but must be opt-in and provenance-aware

scrcpy provides bidirectional clipboard sync, paste acknowledgements, SDK key injection and UHID keyboard/mouse modes.

For apk-research:
- clipboard sync could improve data-entry usability;
- it can expose sensitive host clipboard content to Android apps, so automatic sync should not be default;
- richer keyboard/modifier behavior is useful;
- UHID is optional and should not displace the working gRPC input path without evidence.

### 10. scrcpy display-change handling is a useful implementation reference

scrcpy monitors display properties, resets capture on rotation/folding and debounces client-driven virtual-display resize. These state-machine patterns are relevant if apk-research later adds dynamic display topology; they are not a justification to alter current startup sequencing.

## Priority assessment

Recommended order of investigation:
1. experimental continuous video evidence collector using app_process + MediaCodec + device PTS;
2. optional audio evidence collector;
3. multi-touch gesture support over existing gRPC input;
4. reusable Android-side sidecar transport/version-handshake architecture;
5. only later, optional virtual-display research mode and richer clipboard/keyboard controls.

Not recommended:
- replacing the proven live gRPC/MMAP framebuffer with scrcpy H.264/H.265 streaming;
- replacing v0.10.5 startup sequencing;
- introducing scrcpy-style fallbacks as a way to mask failure of the primary Emulator path.

## Licensing

scrcpy is Apache License 2.0. Architectural ideas may be reimplemented independently. Any direct code reuse must preserve applicable copyright/license notices and comply with Apache-2.0 requirements.

## Authority

- source: Genymobile/scrcpy master at 19871982cefb9de4c981c2314dfda2ac81564b48 and v5.0 documentation/source reviewed 2026-10-06
- authority: trusted-external-evidence
