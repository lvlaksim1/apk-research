# Mobile Research v0.10.0

v0.10.0 adds package-aware network attribution while preserving the validated hidden Emulator + gRPC/MMAP + persistent gRPC input runtime.

## Changes

- Resolves the researched Android package to its UID and continuously samples target-UID processes and `/proc/net` TCP/UDP sockets during capture.
- Links socket inode and 5-tuple evidence to raw PCAP flows.
- Classifies flow ownership as `EXACT`, `HIGH`, `MEDIUM`, or `UNKNOWN` instead of treating nearby traffic as target-app traffic by default.
- `EXACT` requires inode + exact 5-tuple + directly observed socket lifetime plus unambiguous ownership: either a unique package UID or a direct target-package PID/process → FD → inode link when the UID is shared. Shared UID without that process/socket link is `UNKNOWN`; sampling-margin matches are `HIGH`.
- Adds `socket-attribution.jsonl`, `socket-attribution.json`, and whole-session `network-flows.json` to the Research ZIP.
- Research Timeline schema 0.3 includes package ownership on flows and package-attributed packet counts.
- User-action correlation remains explicitly `temporal-only` with `causal_claim=false`.
- Real AVD acceptance verifies non-empty socket-attribution evidence and the attributed flow inventory in the finished Research ZIP.
- The socket sampler records its real remote shell PID and uses it for graceful stop/cleanup, preventing stale attribution samplers after research.
- Installer asset: `MobileResearchSetup_v0.10.0.exe`.

Raw `traffic.pcap` remains the source of truth; attribution is an additive forensic index and may leave short-lived or insufficiently observed traffic as `UNKNOWN`.
