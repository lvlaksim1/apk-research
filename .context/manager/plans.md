# Manager plans

## Default product-change plan

1. Reinstate from `context` and reconcile live `main`, latest release and CI.
2. Work on a dedicated feature/fix branch from current product authority.
3. Make the minimum coherent change with explicit evidence boundaries.
4. Run unit/compile plus relevant real-AVD and Windows verification.
5. Publish stable releases only through the existing commit-triggered main pipeline.
6. Persist verified durable findings and reseal manager state.

## Completed roadmap

- v0.18 — Raw / Packet Inspector — COMPLETE.
- v0.19 — Android sidecar foundation — COMPLETE.
- v0.20 — Continuous Screen foundation — COMPLETE.
- v0.21 — interaction completeness — COMPLETE.
- v0.22 — Packet ↔ Action temporal evidence — COMPLETE.
- v0.23 — Transport Session Evidence — COMPLETE.
- v0.23.1 — Sidecar evidence isolation + idle stability — COMPLETE.
- v0.24 — Unified Session Evidence — COMPLETE and RELEASED.

## v0.24 delivered model

The release unifies navigation across screen, user actions, normalized flows, raw packets and process/socket attribution while preserving source authority. Continuous Screen target-time links are derived from archived clock conversion and remain time-aligned navigation only. Process/socket reverse indexes retain original confidence.

## Next agreed roadmap stage — v0.25

Do not start implementation until the next owner-directed execution step. When activated, v0.25 should combine transport-session and protocol-analysis work:
- capture-bounded TCP session/lifecycle structure;
- sequence/acknowledgment/retransmission/window evidence;
- explicit missing-start/missing-end/gap semantics;
- DNS, TLS metadata, QUIC, HTTP/3 and observable HTTP;
- transaction/grouping only when supported by observed packets/protocol evidence.

Any new inference must expose provenance/confidence and must not synthesize missing traffic, plaintext or causality.

## Explicit exclusions

- Audio Evidence: out of scope.
- User-facing Virtual Display: out of scope.
- encoded Continuous Screen does not replace the proven gRPC/MMAP live display path.
