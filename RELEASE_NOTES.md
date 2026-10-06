# apk-research v0.23.1

v0.23.1 corrects two defects proven by an owner-side real v0.23.0 Research ZIP.

## Fixed

- Sidecar `adb reverse` control/media loopback packets are classified from the exact dynamic ports stored in continuous-screen provenance.
- Those researcher-induced packets remain untouched in raw `01_raw/network/traffic.pcap` but no longer become ordinary app flows, Timeline flow markers or Packet/Action correlations.
- Network/Timeline summaries expose explicit infrastructure packet/byte accounting.
- The long-lived Sidecar media socket no longer inherits the 8-second handshake/control read timeout after the binary stream is established.
- A static Android screen can therefore remain silent for longer than eight seconds without being treated as a dead media stream.
- Real-AVD acceptance now includes a 10-second idle-screen interval and rejects any Sidecar loopback flow that leaks into normalized app evidence.
- Unit regressions cover exact dynamic-port classification, raw-vs-derived accounting and inherited media timeout removal.

## Evidence boundary

Raw PCAP remains authoritative and is never filtered or rewritten. Infrastructure classification affects only derived app-analysis views.

Continuous Screen remains experimental/non-canonical. Canonical Android `screenrecord` remains required and authoritative.

## Unchanged

- hidden Emulator → gRPC/MMAP → AndroidView live display;
- persistent geometry-safe gRPC input;
- v0.10.5 startup/clean-launch sequencing;
- Packet ↔ Action remains `temporal-only` with `causal_claim=false`;
- Transport Session Evidence remains capture-bounded;
- Audio Evidence and Virtual Display remain out of scope.
