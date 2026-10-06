# Latest Handoff

Generation: 10
Date: 2026-10-07

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

This handoff is the clean-chat checkpoint.

Verified product baseline is **apk-research v0.23.1** at `39e483ee03d5337e4e928b4b85cce85c40f4fe35`.

Installer: `apk-research-setup_v0.23.1.exe`.
SHA-256: `b5bf2d31da1c47ef59d351988a09f5c0dad72a8117aab0c4849ae30bb54eb540`.
Size: 36,323,501 bytes.

Main pipeline #127 (`37460233667`) completed SUCCESS and GitHub Release v0.23.1 was published.

v0.23.1 corrects the two defects proven by the owner's real v0.23.0 Research ZIP:
1. exact Sidecar control/media loopback traffic remains preserved in RAW PCAP but is excluded from ordinary app flow inventory, Timeline markers and Action/Packet correlations, with explicit infrastructure accounting;
2. the established Sidecar media stream no longer inherits the short 8 s socket timeout.

Real-AVD release acceptance includes a 10 s idle-screen regression and Sidecar-flow leakage assertion; both passed.

Protected baselines:
- raw PCAP is authoritative;
- Packet ↔ Action remains `temporal-only`, `causal_claim=false`;
- hidden Emulator → gRPC/MMAP → AndroidView remains the live display path;
- v0.10.5 clean-launch/startup sequencing remains the proven runtime baseline;
- canonical Android screenrecord remains authoritative;
- Continuous Screen remains experimental/non-canonical;
- Audio Evidence and user-facing Virtual Display remain out of scope.

No v0.24 implementation is active. Historical corrective branches must not be treated as active product authority; start any new development from current `main`.

Best next input is an owner-side v0.23.1 Research ZIP. If supplied, verify Continuous Screen completion, Sidecar infrastructure isolation/accounting, canonical screenrecord coverage, packet/action navigation and v0.23 transport-session evidence before selecting the next Stage E increment.
