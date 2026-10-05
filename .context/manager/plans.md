# Manager plans

## Default plan for product changes

1. Reinstate from `context` and reconcile live `main`, latest release and relevant CI.
2. Preserve the current product baseline; use a dedicated feature/fix branch for substantive work.
3. Make the minimum coherent change and keep runtime/capture/evidence boundaries explicit.
4. Run compile/tests and the relevant specialized regression tests before promotion.
5. For release-bound changes, rely on the existing main pipeline: CI → real AVD acceptance → Windows standalone/GUI/installer smoke → clean-Windows provisioning → Publish Release.
6. For evidence/network changes, verify with a real Research ZIP when owner evidence is available.
7. After verified durable findings, persist semantic changes to the authoritative `context` branch and reseal manager state.

## Product roadmap from v0.18.0

### Stage A — Raw / Packet Inspector — COMPLETE

Released as v0.18.0. Unified Evidence Explorer can resolve a normalized flow to concrete packet records in the original PCAP with reproducible packet index/byte-offset locators and bounded raw preview. Real-AVD release acceptance verifies packet count and locator integrity against a generated Research ZIP.

### Stage B — Android sidecar foundation — ACTIVE

Introduce a project-owned, version-pinned temporary Android-side `app_process` agent as an experimental infrastructure component.

Required design:
- no installed Android APK/service and no persistent guest modification;
- host deploys a versioned jar/dex payload to a private path under `/data/local/tmp`;
- execute as Android shell via `app_process`;
- exact client/agent protocol/version handshake before use;
- one long-lived local transport instead of repeated short-lived `adb shell` commands for sidecar functions;
- prefer host-listen + `adb reverse` so host readiness precedes guest connection and polling races are avoided;
- bounded startup timeout, explicit failure reason and deterministic teardown/removal;
- sidecar diagnostics are observable but do not weaken existing research completeness semantics until a specific collector adopts it;
- no display/input responsibility: Emulator gRPC/MMAP remains authoritative.

Initial Stage B completion should prove lifecycle/handshake/transport on real AVD before any collector is migrated onto it.

### Stage C — continuous screen evidence

Build an experimental continuous screen evidence collector on the verified sidecar foundation using Android Surface/MediaCodec concepts and device-generated presentation timestamps. Keep the accepted chunked `screenrecord` collector as the baseline during A/B verification. Promotion requires real Research ZIP evidence showing no coverage regression, stable timing/provenance and cleaner session continuity.

Audio capture is excluded.

### Stage D — interaction completeness

Extend the existing gRPC input path with multi-touch gestures and explicit gesture evidence. Add a display-geometry generation invariant so stale input created for an old rotation/geometry is rejected rather than remapped heuristically.

Later keyboard/clipboard improvements may be added as opt-in UX features; automatic host clipboard synchronization must not be enabled by default.

Virtual Display is excluded.

### Stage E — deeper evidence intelligence

After continuous media evidence is stable, extend analyzers only where raw evidence can support stronger conclusions: richer packet/session drill-down, protocol metadata and cross-links among Timeline, process/socket evidence, screen timing and network evidence. Preserve explicit confidence/provenance and avoid causal overclaim.

## Context maintenance plan

- Keep `main` discovery-only for Context Capsule bootstrap outside product release changes.
- Persist manager identity, BDI state, memory and current working views only on `context`.
- Never let a temporary feature branch become manager-state authority.
- Keep secrets, transient runtime state and hidden reasoning out of the capsule.
