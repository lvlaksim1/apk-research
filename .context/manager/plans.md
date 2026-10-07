# Manager plans

## Default product-change plan

1. Reinstate from `context` and reconcile live `main`, release and CI.
2. Work on a dedicated feature/fix branch.
3. Make the minimum coherent change with explicit boundaries.
4. Run unit/compile plus relevant real-AVD and Windows verification.
5. For updater changes, require a real installed-version upgrade acceptance that survives parent-process exit.
6. Publish stable releases only through the commit-triggered main pipeline.
7. Persist verified findings and reseal manager state.

## Completed roadmap

- v0.18 — Raw / Packet Inspector — COMPLETE.
- v0.19 — Android sidecar — COMPLETE.
- v0.20 — Continuous Screen — COMPLETE.
- v0.21 — interaction completeness — COMPLETE.
- v0.22 — Packet ↔ Action — COMPLETE.
- v0.23 / v0.23.1 — transport session / sidecar correction — COMPLETE.
- v0.24 — Unified Session Evidence — COMPLETE and RELEASED.
- v0.25 — Transport and Protocol Analysis — COMPLETE and RELEASED.
- v0.26 — Investigator Workspace — COMPLETE and RELEASED.
- v0.27 — APK/XAPK Package Intake — COMPLETE and RELEASED.
- v0.28 — Direct GitHub Self-Update — COMPLETE and RELEASED.
- v0.29 — Icon + ABI-aware XAPK + explicit emulator controls + in-place updater — COMPLETE and RELEASED.
- v0.29.1 — Reliable updater handoff — COMPLETE and RELEASED.

## Next planning state

No subsequent feature stage is authorized at this checkpoint. Start future product work from verified v0.29.1 / `ae4450ba662299c30199742ba4b1d2bbcdb27601` after a new owner direction.

## Explicit exclusions

- Audio Evidence: out of scope.
- User-facing Virtual Display: out of scope.
- Continuous Screen sole-source replacement remains a separate future quality/revalidation gate.
