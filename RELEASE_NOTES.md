# apk-research v0.23.0

v0.23.0 adds **Transport Session Evidence** to Raw / Packet Inspector without changing capture or runtime behavior.

## Added

- per-packet TCP sequence and acknowledgment numbers;
- decoded TCP flags, header length, receive window and TCP payload length;
- a capture-bounded transport-session summary for selected TCP flows;
- complete three-way-handshake evidence only when SYN → SYN/ACK → ACK are all present in the PCAP;
- FIN/RST termination evidence with packet IDs;
- explicit `partial-or-not-observed-in-capture` and `not-observed-in-capture` states instead of inferring missing lifecycle events;
- transport-session summary/details/search in the Packets GUI;
- regression tests for TCP header/session parsing;
- real-AVD acceptance against a generated Research ZIP.

## Evidence boundary

Transport Session Evidence describes only TCP headers actually observed in the authoritative raw PCAP. A packet missing from the capture is not treated as proof that the corresponding network event did not occur.

No TCP stream reassembly, application plaintext inference or causal upgrade is introduced. Existing Packet ↔ Action links remain `temporal-only` with `causal_claim=false`.

## Unchanged

- raw `01_raw/network/traffic.pcap` remains authoritative;
- no Research ZIP schema or collector change;
- hidden Emulator → gRPC/MMAP → AndroidView live display;
- persistent geometry-safe gRPC input;
- v0.10.5 startup/clean-launch sequencing;
- Android sidecar and experimental continuous-screen A/B collector;
- canonical screenrecord evidence;
- Audio Evidence and Virtual Display remain out of scope.
