# Latest Handoff

Generation: 12
Date: 2026-10-07

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

Verified product baseline is **apk-research v0.23.1** at `39e483ee03d5337e4e928b4b85cce85c40f4fe35`.

Installer: `apk-research-setup_v0.23.1.exe`.
SHA-256: `b5bf2d31da1c47ef59d351988a09f5c0dad72a8117aab0c4849ae30bb54eb540`.
Size: 36,323,501 bytes.

Main pipeline #127 completed SUCCESS and GitHub Release v0.23.1 is published.

Two owner-side v0.23.1 archives now close Continuous Screen technical validation.

Short/idle archive `20261006T230500.602195Z-1206ec46.research.zip` proves:
- 59.005490 s no-frame interval survives and resumes;
- old inherited 8 s media timeout is gone;
- Sidecar traffic remains RAW/infrastructure-only in derived network views.

Long/rollover archive `20261006T231833.446176Z-710dfbe4.research.zip` proves:
- 33/33 checksums, complete/non-degraded;
- canonical screenrecord rotates across two chunks with a 1.965848 s frame gap;
- Continuous Screen remains one clean stream with 6,970 frames / 256.466399 s;
- 66 continuous frames exist inside the canonical rollover gap, maximum adjacent gap 0.100000 s;
- owner action 166 occurs entirely inside the canonical gap and is captured by Continuous Screen;
- H.264 decodes end-to-end with no error;
- 93,556 Sidecar infrastructure packets / 65,433,681 bytes are preserved in RAW PCAP, while zero exact Sidecar-port flows leak into 82 ordinary normalized flows.

Therefore Continuous Screen stability/continuity validation is complete.

Remaining product-role boundary:
- Continuous Screen current profile: 540×960 / 2 Mbit/s;
- canonical screenrecord: 1080×1920.

Manager recommendation: Continuous Screen can leave purely experimental reliability status and become a stable continuous/timeline evidence source, while canonical high-resolution screenrecord remains until either the owner chooses that dual-source role or Sidecar quality is raised/revalidated for sole-source replacement.

Protected baselines:
- raw PCAP is authoritative;
- Packet ↔ Action remains `temporal-only`, `causal_claim=false`;
- hidden Emulator → gRPC/MMAP → AndroidView remains live display;
- v0.10.5 startup/clean-launch sequencing remains protected;
- Audio Evidence and user-facing Virtual Display remain out of scope.

No v0.24 implementation is active.
