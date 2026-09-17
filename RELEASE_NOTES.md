# apk-research v0.17.0

v0.17.0 adds the **Unified Evidence Explorer**: a single post-capture GUI path through existing forensic evidence without changing the runtime, collectors or archive schemas.

## Added

- a dedicated `Evidence` tab in the desktop GUI;
- forward navigation `Action → Host → Flow → Process/Socket → Raw evidence`;
- reverse host-centric navigation `Host → Flow → Action / Process/Socket / Raw`;
- direct Timeline → Evidence and Network → Evidence transitions;
- direct Evidence → Timeline and Evidence → Network transitions;
- free-text search across actions, hosts, flow IDs, processes, PIDs, socket evidence, endpoints and protocols;
- explicit raw PCAP locators using canonical flow identity, target time interval and bidirectional 5-tuple;
- explicit raw socket locators using process/PID/UID/inode attribution evidence;
- human-readable provenance/details for each evidence node.

## Evidence semantics

Unified Evidence Explorer is presentation-only. It reads the existing `research-timeline.json`, `network-flows.json` and `socket-attribution.json` artifacts and does not create a new forensic source of truth.

Action ↔ Flow relationships retain the existing `temporal-only` semantics and `causal_claim=false`; the Explorer does not upgrade temporal correlation into causality. Raw locators point back to `01_raw/network/traffic.pcap` and `01_raw/network/socket-snapshots.txt` rather than replacing those artifacts.

## Validation

- full Windows development suite: 178 tests passed;
- dedicated offscreen GUI construction smoke passed for `UnifiedEvidenceMainWindow` and the Evidence tab;
- existing Timeline and Network Analyzer remain available and are cross-linked with the new Explorer.

Android runtime, v0.10.5 clean-launch sequencing, gRPC/MMAP display/input path, collectors, raw PCAP capture, socket/package attribution, QUIC/HTTP3 parsing and Research ZIP schemas are unchanged.
