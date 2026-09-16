# Mobile Research v0.10.1

v0.10.1 hardens the package-aware network attribution introduced in v0.10.0 after validation on a real Windows Research ZIP.

## Changes

- Fixes target process/PID discovery in the Android socket sampler. `/proc/<pid>/status` uses TAB-separated `Uid:` fields; the previous custom shell IFS did not contain a real TAB, so process observations could remain empty even while UID-owned sockets were collected.
- Restores the complete ownership chain `package → UID → PID/process → FD → socket inode → 5-tuple → PCAP`.
- Preserves unique-UID attribution semantics from v0.10.0 while making shared-UID PID/socket disambiguation operational on real Android.
- Real AVD release acceptance now fails if no process observations are captured or if the launched target package process is absent from normalized socket snapshots.
- Adds a regression test for the generated remote shell parser.
- No change to the validated Windows runtime: hidden Emulator, top-down gRPC/MMAP framebuffer and persistent gRPC input remain the only interactive path.
- Installer asset: `MobileResearchSetup_v0.10.1.exe`.

Raw `traffic.pcap` remains the source of truth; socket/process attribution is additive forensic evidence.
