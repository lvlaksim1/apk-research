# Latest Handoff

Generation: 14
Date: 2026-10-07

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

Verified product baseline is **apk-research v0.24.0** at `176dc1f1302c729456fc0d5711d0e5879e36837e`.

Installer: `apk-research-setup_v0.24.0.exe`.
SHA-256: `f1ee0ec8e60345b17a21d00c8a5f4b4f616c8ed6c1aca24714f92eb912cb2c3c`.
Size: 36,355,696 bytes.
Release published: 2026-10-07T01:43:15Z.

Main pipeline #133 (`37558075676`) completed SUCCESS for the exact release SHA. CI, real AVD Research ZIP acceptance, Windows standalone/self-test/GUI smoke, installer install/smoke, clean-Windows Android provisioning, documentation/checksum gates, GitHub Release publication and artifact cleanup all passed.

v0.24.0 delivers Unified Session Evidence:
- chronological `Session Evidence` view;
- screen ↔ action ↔ normalized flow ↔ packet ↔ process/socket ↔ raw navigation;
- reverse Process/Socket → related flows index;
- device-PTS → target-UTC screen locator using archived realtime↔elapsed conversion;
- explicit evidence relation type/strength without causal upgrade.

Protected semantics:
- raw PCAP is authoritative;
- Action ↔ Flow and Packet ↔ Action remain `temporal-only`, `causal_claim=false`;
- screen links are `time-aligned-navigation`, not causality;
- reverse process/socket navigation retains existing attribution confidence;
- hidden Emulator → gRPC/MMAP → AndroidView remains live display;
- v0.10.5 startup/clean-launch sequencing remains protected;
- Continuous Screen is stable continuous/timeline evidence; Android screenrecord remains high-resolution evidence;
- Audio Evidence and user-facing Virtual Display remain out of scope.

No v0.25 implementation is active. The next agreed roadmap stage is v0.25 Transport and Protocol Analysis, to start when the owner directs execution.
