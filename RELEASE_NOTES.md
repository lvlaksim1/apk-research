# apk-research v0.22.0

v0.22.0 adds **Packet ↔ Action Evidence** to the Raw / Packet Inspector without changing capture or runtime behavior.

## Added

- packet-level correlation to existing exported Research Timeline action windows;
- a strict two-part match: the action must reference the same canonical `flow_id` and the packet target timestamp must fall inside that action's exported target-time window;
- Action-window column in the Packets tab;
- action ID/label search inside Packet Inspector;
- packet details showing the exact temporal window, Timeline confidence label and explicit non-causality;
- direct Packet → Timeline action navigation;
- real-AVD acceptance of packet/action correlation invariants on a generated Research ZIP.

## Evidence boundary

Packet ↔ Action is derived only from evidence already stored in the Research ZIP. v0.22 does not invent a new window, widen an existing window or infer that an action caused a packet.

Every packet/action relation is explicitly `temporal-only` and `causal_claim=false`. Raw `01_raw/network/traffic.pcap` remains the network source of truth and the archived Research Timeline remains the source of the action windows used by this view.

## Unchanged

- hidden Emulator → gRPC/MMAP → AndroidView live display;
- persistent geometry-safe gRPC input;
- v0.10.5 startup/clean-launch sequencing;
- Android sidecar and experimental continuous-screen A/B collector;
- canonical screenrecord evidence;
- packet/socket attribution and QUIC/HTTP3 boundaries;
- Audio Evidence and Virtual Display remain out of scope.
