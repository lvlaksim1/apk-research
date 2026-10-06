# Manager plans

## Default product-change plan

1. Reinstate from `context` and reconcile live `main`, latest release and CI.
2. Work on a dedicated feature/fix branch from current product authority.
3. Make the minimum coherent change with explicit evidence boundaries.
4. Run unit/compile plus relevant real-AVD and Windows verification.
5. Publish stable releases only through the existing commit-triggered main pipeline.
6. Persist verified durable findings and reseal manager state.

## Completed roadmap

- Stage A / v0.18 — Raw / Packet Inspector — COMPLETE.
- Stage B / v0.19 — Android sidecar foundation — COMPLETE.
- Stage C / v0.20 — continuous screen evidence — COMPLETE AS EXPERIMENTAL; canonical screenrecord retained.
- Stage D / v0.21 — interaction completeness — COMPLETE.
- Stage E increment 1 / v0.22 — Packet ↔ Action temporal evidence — COMPLETE.

## Stage E continuation

Choose the next increment by the remaining investigative gap, not by feature novelty. Strong candidates are:
- richer flow/session semantics derived directly from packet bytes (for example transport lifecycle and transaction/handshake boundaries);
- additional cross-navigation among packet, process/socket and timeline evidence;
- screen/network cross-links only after clock-domain provenance is sufficient.

Any new derived inference must expose its source/provenance and confidence. No feature may silently reinterpret encrypted traffic, manufacture causality or weaken RAW authority.

## Explicit exclusions

- Audio Evidence: out of scope.
- Virtual Display: out of scope.
- encoded scrcpy-style live mirroring: not a replacement for gRPC/MMAP.
