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
- v0.27 — APK/XAPK Package Intake — COMPLETE and RELEASED.

## v0.27 delivered model

APK and XAPK are first-class desktop inputs. XAPK handling is strict rather than heuristic: one base APK, compatible splits, safe extraction, post-install OBB deployment, and real-AVD acceptance. Existing APK behavior is preserved.

## Next planning state

No further product stage is authorized at this checkpoint. Start any new feature version from verified v0.27.0 / `f6a39f21583273f91b192d14fa258bc1e7613a93` only after a new owner direction.

## Explicit exclusions

- Audio Evidence: out of scope.
- User-facing Virtual Display: out of scope.
- Continuous Screen sole-source replacement remains a separate future quality/revalidation gate.
