# Mobile Research v0.10.0

v0.10.0 adds package-aware network attribution while preserving the validated hidden Emulator + gRPC/MMAP + persistent gRPC input runtime.

## Changes

- Resolves the researched Android package to its UID and continuously samples target-UID processes and `/proc/net` TCP/UDP sockets during capture.
- Links socket inode and 5-tuple evidence to raw PCAP flows.
- Classifies flow ownership as `EXACT`, `HIGH`, `MEDIUM`, or `UNKNOWN` instead of treating nearby traffic as target-app traffic by default.
- `EXACT` is reserved for a unique package UID, inode, exact 5-tuple and directly observed socket lifetime; shared UID and sampling-margin matches are downgraded.
- Adds `socket-attribution.jsonl`, `socket-attribution.json`, and whole-session `network-flows.json` to the Research ZIP.
- Research Timeline schema 0.3 includes package ownership on flows and package-attributed packet counts.
- User-action correlation remains explicitly `temporal-only` with `causal_claim=false`.
- Real AVD acceptance verifies non-empty socket-attribution evidence and the attributed flow inventory in the finished Research ZIP.
- Installer asset: `MobileResearchSetup_v0.10.0.exe`.

Raw `traffic.pcap` remains the source of truth; attribution is an additive forensic index and may leave short-lived or insufficiently observed traffic as `UNKNOWN`.
