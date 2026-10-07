# Latest Handoff

Generation: 15
Date: 2026-10-07

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

Verified product baseline is **apk-research v0.25.0** at `3717210a9db3074569602afc336380fd26598dd7`.

Installer: `apk-research-setup_v0.25.0.exe`.
SHA-256: `f9a2a92e02b5a1da9f6b8be39d3967a54292d8c04ad20926cba2361f3d560bb7`.
Size: 36,384,738 bytes.
Release published: 2026-10-07T02:37:51Z.

v0.25.0 delivers capture-bounded Transport and Protocol Analysis in Packet Inspector: TCP sequence/ACK/window observations and lifecycle boundaries, DNS, observed TLS hello metadata, QUIC Initial/SNI/ALPN, observable HTTP/HTTP3 indicators and conservative ordered transaction grouping. RAW PCAP remains authoritative, missing data is never synthesized and encrypted bytes are never presented as plaintext.

Protected semantics/runtime:
- raw PCAP authoritative;
- Action ↔ Flow and Packet ↔ Action remain `temporal-only`, `causal_claim=false`;
- screen links remain time-aligned navigation;
- process/socket confidence is unchanged by navigation;
- protocol intelligence is capture-bounded;
- hidden Emulator → gRPC/MMAP → AndroidView remains live display;
- v0.10.5 startup/clean-launch sequencing remains protected;
- Continuous Screen is stable continuous/timeline evidence; Android screenrecord remains high-resolution evidence;
- Audio Evidence and user-facing Virtual Display remain out of scope.

Owner has directed execution of the next roadmap stage: **v0.26 Investigator Workspace**. Build it as a workflow/presentation layer over v0.24/v0.25 evidence: behavior overview, global search/filters, bookmarks/evidence sets, reports and reverse navigation to exact source evidence.
