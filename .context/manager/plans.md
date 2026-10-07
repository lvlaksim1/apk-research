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
- v0.25 — Transport and Protocol Analysis — COMPLETE and RELEASED.

## Active roadmap stage — v0.26 Investigator Workspace

The owner directed execution. Build the investigation workflow on top of existing evidence, rather than changing capture/runtime foundations:
- a coherent behavior/session overview assembled from already observed actions, process/socket attribution, network/protocol evidence and screen timing;
- global search across investigation evidence;
- filters by time, process, remote endpoint, protocol and action;
- bookmarks and saved evidence sets with stable references back to existing evidence identifiers;
- report generation from selected evidence;
- reverse navigation from each report/evidence-set item back to the exact source view/item where possible;
- explicit labels for observed fact, established technical relationship, temporal relationship and analyst selection; no causal upgrade.

Implementation should reuse v0.24 Session Evidence/Evidence Explorer and v0.25 Packet Inspector analysis rather than duplicating parsers or capture logic.

## Explicit exclusions

- Audio Evidence: out of scope.
- User-facing Virtual Display: out of scope.
- encoded Continuous Screen does not replace the proven gRPC/MMAP live display path.
