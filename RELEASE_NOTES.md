# apk-research v0.18.0

v0.18.0 adds the **Raw / Packet Inspector** and completes the in-app evidence path from a normalized flow to the concrete packet records in the original Research ZIP PCAP.

## Added

- a dedicated `Packets` tab in the desktop GUI;
- Evidence → Packets and Network → Packets navigation for a selected normalized flow;
- direct sequential reading of `01_raw/network/traffic.pcap` from the Research ZIP;
- bidirectional packet filtering using the same canonical TCP/UDP flow identity used by Network Analyzer;
- per-packet target timestamp, direction, protocol, source/destination endpoints and captured/original lengths;
- reproducible raw locators containing the original PCAP packet index plus record/frame byte offsets;
- bounded raw-frame hex previews;
- packet-level DNS/TLS SNI and already-supported QUIC/HTTP3 metadata where the bytes provide that evidence;
- free-text packet search across IDs, timestamps, endpoints and protocol evidence.

## Evidence semantics

Packet Inspector is presentation-only. It does not rewrite, extract or replace the PCAP as a new source of truth.

Encrypted payload is never presented as decoded plaintext. Existing Action ↔ Flow relationships remain `temporal-only` with `causal_claim=false`.

## Compatibility boundary

- no Research ZIP schema change;
- no collector change;
- no Android runtime change;
- no change to v0.10.5 startup/clean-launch sequencing;
- hidden Emulator → gRPC/MMAP → AndroidView remains the only supported live display path.

## Validation

Release validation requires the normal test suite, Windows GUI/package smoke, real AVD acceptance and the commit-triggered release pipeline.
