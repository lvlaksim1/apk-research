# Project Architecture

## Desktop/runtime

- Python application packaged as a standalone Windows desktop executable and installer.
- Desktop UI embeds a managed Android Emulator view.
- Proven display path: hidden Emulator (`-qt-hide-window`) → Emulator gRPC → MMAP framebuffer → AndroidView.
- Pointer input uses persistent Emulator gRPC input events.
- v0.10.5 is the proven startup/clean-launch sequencing baseline.

## Research capture

The runtime arms evidence collectors around a controlled application launch and session:
- Android logcat/lifecycle evidence;
- Android screen recording;
- raw network PCAP;
- package/process/socket attribution snapshots;
- user actions and clock calibration.

The resulting Research ZIP contains raw evidence plus normalized/derived data.

## Network/evidence model

- Raw `01_raw/network/traffic.pcap` is the network source of truth.
- Package-aware attribution links package → UID → PID/process → FD → socket inode → normalized bidirectional 5-tuple → PCAP.
- `network-flows.json` stores normalized flow identity/counters/ownership/protocol metadata.
- `research-timeline.json` correlates user actions and flows with temporal-only semantics.
- QUIC v1/v2 Initial analysis is passive post-capture metadata extraction; it does not imply Handshake/1-RTT decryption.
- Unified Evidence Explorer is presentation-only and navigates existing Timeline/flow/socket/raw evidence.

## Build/release

- PyInstaller produces the standalone desktop application.
- Inno Setup produces `apk-research-setup_v<version>.exe`.
- The commit-triggered main pipeline runs CI, real AVD acceptance, Windows desktop build/smoke, clean-Windows provisioning and release publication.
