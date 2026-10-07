# apk-research v0.24.0 — Unified Session Evidence

v0.24.0 turns the existing Timeline, Evidence Explorer, Packet Inspector, socket attribution and dual-source screen evidence into one cross-navigable investigation model.

## Unified Session Evidence

- Adds a `Session Evidence` view with one chronological table over existing Research Timeline events.
- Each row can expose the linked action, normalized flow(s), packet counts, process/socket ownership and time-aligned screen evidence.
- Navigation now connects Timeline ↔ Evidence ↔ Packets ↔ screen moments instead of leaving those views as separate analysis islands.
- Evidence Explorer gains a reverse Process/Socket index so one attributed inode/process can reveal all related flows and their action/raw paths.

## Screen evidence navigation

- Continuous Screen device MediaCodec PTS is mapped to target UTC for navigation using the realtime↔elapsed transform already archived by high-resolution Android `screenrecord` frame timing.
- The screen locator shows the nearest Continuous Screen packet/frame and the matching high-resolution screenrecord chunk/relative time when covered.
- During a canonical screenrecord rollover gap, navigation explicitly reports the high-resolution coverage gap while still locating Continuous Screen evidence.
- Screen links are `time-aligned-navigation`; they never claim that a screen change caused a packet/action or vice versa.

## Continuous Screen product role

Owner-side v0.23.1 validation proved idle survival and uninterrupted coverage across the 170-second canonical screenrecord chunk rollover. v0.24.0 therefore records Continuous Screen as a stable continuous/timeline source rather than an experimental source.

The dual-source boundary remains deliberate:
- Continuous Screen: stable uninterrupted temporal coverage at the current 540×960 / 2 Mbit/s profile;
- Android `screenrecord`: high-resolution 1080×1920 screen evidence.

Continuous Screen still does not replace the proven hidden Emulator → gRPC/MMAP → AndroidView live display path.

## Evidence boundaries

- Raw `01_raw/network/traffic.pcap` remains authoritative network evidence.
- Action ↔ Flow and Packet ↔ Action remain temporal relations with `causal_claim=false`.
- Flow ↔ Process/Socket displays the existing attribution confidence; reverse indexing does not strengthen that confidence.
- Screen ↔ event/packet links are navigation by aligned target time, not causal inference.
- Encrypted traffic is not represented as plaintext and absent packets/events are not synthesized.

## Runtime and scope

The v0.10.5 startup/clean-launch sequencing and hidden Emulator → gRPC/MMAP → AndroidView runtime remain unchanged. Audio Evidence and user-facing Virtual Display remain out of scope.
