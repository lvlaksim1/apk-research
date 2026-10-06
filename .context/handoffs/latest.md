# Latest Handoff

Generation: 4
Date: 2026-10-06

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

Verified product baseline is apk-research v0.21.0 at `250c507ca3302558ba11d5df57d3129a38ad6fbe`. Main pipeline #124 completed SUCCESS and GitHub Release v0.21.0 is published. Installer SHA-256: `2d655d007b67f5d1c6f866505b9865d300caa6f951e5c90f53af83d7c862d648`.

Roadmap stages A-D are implemented:
- v0.18 Raw / Packet Inspector;
- v0.19 Android sidecar foundation;
- v0.20 experimental Continuous Screen Evidence;
- v0.21 Interaction Completeness.

Stage E is active. Immediate v0.22 work is Packet ↔ Action temporal evidence: annotate inspected packets using existing archived Timeline action windows and selected-flow references, keep `causal_claim=false`, and add direct Packet → Timeline navigation.

Audio Evidence and Virtual Display remain excluded. Canonical screenrecord remains authoritative pending explicit promotion decision for the experimental continuous-screen collector.
