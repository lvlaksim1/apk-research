# Latest Handoff

Generation: 11
Date: 2026-10-07

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

Verified product baseline is **apk-research v0.23.1** at `39e483ee03d5337e4e928b4b85cce85c40f4fe35`.

Installer: `apk-research-setup_v0.23.1.exe`.
SHA-256: `b5bf2d31da1c47ef59d351988a09f5c0dad72a8117aab0c4849ae30bb54eb540`.
Size: 36,323,501 bytes.

Main pipeline #127 (`37460233667`) completed SUCCESS and GitHub Release v0.23.1 was published.

Owner-side archive `20261006T230500.602195Z-1206ec46.research.zip` revalidates both v0.23.0 corrective targets:
1. Continuous Screen survives a 59.005490 s interval with no emitted media frame and resumes normally, proving the old inherited 8 s media timeout is gone.
2. RAW PCAP preserves 21,787 exact Sidecar loopback packets on archived ports 53659/53669, while normalized app evidence contains zero Sidecar-port flows and no infrastructure action correlations.

The archive is sound: 31/31 checksums, complete/non-degraded session. Continuous H.264 decodes cleanly with 1,613 frames / 131.195188 s; canonical screenrecord completed with 925 frames / 132.671076 s. The same long static interval is visible in canonical frame timing and post-idle frames align visually.

Therefore the v0.23.0 Sidecar defects are closed.

Continuous Screen remains experimental only until one final owner-side session crosses the canonical `screenrecord` 170 s chunk boundary. That run validates the main architectural benefit—continuity through chunk rotation—before an explicit owner promotion decision.

Protected baselines:
- raw PCAP is authoritative;
- Packet ↔ Action remains `temporal-only`, `causal_claim=false`;
- hidden Emulator → gRPC/MMAP → AndroidView remains the live display path;
- v0.10.5 clean-launch/startup sequencing remains the proven runtime baseline;
- canonical Android screenrecord remains authoritative until promotion;
- Audio Evidence and user-facing Virtual Display remain out of scope.

No v0.24 implementation is active. Start new product work from current `main`.
