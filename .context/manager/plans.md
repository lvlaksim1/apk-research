# Manager plans

## Default plan for product changes

1. Reinstate from `context` and reconcile live `main`, latest release and relevant CI.
2. Preserve the current product baseline; use a dedicated feature/fix branch for substantive work.
3. Make the minimum coherent change and keep runtime/capture/evidence boundaries explicit.
4. Run compile/tests and the relevant specialized regression tests before promotion.
5. For release-bound changes, rely on the existing main pipeline: CI → real AVD acceptance → Windows standalone/GUI/installer smoke → clean-Windows provisioning → Publish Release.
6. For evidence/network changes, verify with a real Research ZIP when owner evidence is available.
7. After verified durable findings, persist semantic changes to the authoritative `context` branch and reseal manager state.

## Product roadmap after v0.17.0

### Stage A — close the RAW inspection gap

Extend Unified Evidence Explorer from raw locators to an in-app Raw/Packet Inspector. A selected flow should resolve to concrete PCAP packet records with timestamp, direction, endpoints, protocol, packet/frame length and safe bounded payload/hex visibility where meaningful. Preserve raw PCAP as authority and do not infer plaintext that is not present.

This stage directly advances the core product goal: from an observed user action to a host/flow/process and finally to inspectable raw evidence without leaving the application.

### Stage B — Android sidecar foundation

Introduce a project-owned, version-pinned temporary Android-side `app_process` agent as an experimental infrastructure component. Use a long-lived local transport, exact client/agent version handshake and deterministic cleanup. Prefer host-listen + `adb reverse` startup to avoid polling races. The sidecar must not replace the Emulator gRPC/MMAP display/input path.

### Stage C — continuous screen evidence

Build an experimental continuous screen evidence collector on the sidecar using Android Surface/MediaCodec concepts and device-generated presentation timestamps. Keep the accepted chunked `screenrecord` collector as the baseline during A/B verification. Promotion requires real Research ZIP evidence showing no coverage regression, stable timing/provenance and cleaner session continuity.

Audio capture is excluded.

### Stage D — interaction completeness

Extend the existing gRPC input path with multi-touch gestures and explicit gesture evidence. Add a display-geometry generation invariant so stale input created for an old rotation/geometry is rejected rather than remapped heuristically.

Later keyboard/clipboard improvements may be added as opt-in UX features; automatic host clipboard synchronization must not be enabled by default.

Virtual Display is excluded.

### Stage E — deeper evidence intelligence

After RAW packet inspection and continuous media evidence are stable, extend analyzers only where raw evidence can support stronger conclusions: richer packet/session drill-down, protocol metadata and cross-links among Timeline, process/socket evidence, screen timing and network evidence. Preserve explicit confidence/provenance and avoid causal overclaim.

## Context maintenance plan

- Keep `main` discovery-only for Context Capsule bootstrap.
- Persist manager identity, BDI state, memory and current working views only on `context`.
- Never let a temporary feature branch become manager-state authority.
- Keep secrets, transient runtime state and hidden reasoning out of the capsule.
