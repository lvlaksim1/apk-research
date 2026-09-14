# Mobile Research v0.6.0

v0.6.0 introduces a fundamentally different native-display path for Windows.

The Emulator is now launched as a normal visible standalone Qt/GPU window. Mobile Research starts locating that real top-level window immediately after process creation and embeds it into the Android panel. The hidden Qt HWND created by `-qt-hide-window` is no longer treated as a native video surface.

A native attach is accepted only after Win32 parent, client-area and visibility checks. The existing gRPC/MMAP framebuffer stays available until attach is confirmed, and remains the automatic fallback.

Windows startup order is:

1. standalone native + GPU host;
2. standalone native + GPU auto;
3. hidden gRPC/MMAP + GPU host;
4. hidden gRPC/MMAP + GPU auto;
5. headless SwiftShader.

The framebuffer fallback also restores reverse-rotation normalization for rotation 2/3, fixing the upside-down first frame observed in v0.5.2 and keeping touch coordinates aligned.

The research core is unchanged: ADB, root, logcat, screen recording, raw PCAP/tcpdump, package metadata, Research ZIP and semantic audit remain independent from display transport.

Release assets:

- `MobileResearchSetup.exe`
- `SHA256SUMS.txt`
