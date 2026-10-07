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
- v0.26 — Investigator Workspace — COMPLETE and RELEASED.

The owner-agreed consolidated roadmap `v0.24 → v0.25 → v0.26` is complete.

## v0.26 delivered model

Investigator Workspace is a presentation/workflow layer over existing evidence. It adds global investigation search/filtering, stable EV navigation keys, analyst bookmarks/evidence sets, reverse navigation and report export. It does not create stronger forensic facts or modify the Research ZIP.

## Next planning state

No new product stage is authorized at this checkpoint.

When the owner directs further development:
- start from verified v0.26.0 / `cbf6d177e67cd56e980319ab654da2f27a73176a`;
- preserve all current evidence authority and non-causality boundaries;
- treat any Continuous Screen sole-source replacement as a separate quality/revalidation project;
- do not add Audio Evidence or user-facing Virtual Display unless the owner explicitly changes scope.

## Explicit exclusions

- Audio Evidence: out of scope.
- User-facing Virtual Display: out of scope.
- encoded Continuous Screen does not replace the proven gRPC/MMAP live display path.
