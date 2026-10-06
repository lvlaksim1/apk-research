# Manager plans

## Default product-change plan

1. Reinstate from `context` and reconcile live `main`, latest release and CI.
2. Work on a dedicated feature branch from current product authority.
3. Make the minimum coherent change with explicit evidence boundaries.
4. Run unit/compile plus relevant AVD/desktop verification.
5. For release-bound work, use the existing commit-triggered main pipeline.
6. Persist verified durable findings and reseal manager state.

## Completed roadmap stages

### Stage A — Raw / Packet Inspector — COMPLETE (v0.18.0)
Concrete PCAP packet inspection with reproducible raw offsets and bounded hex preview.

### Stage B — Android sidecar foundation — COMPLETE (v0.19.0)
Temporary project-owned app_process agent, exact handshake, long-lived transport and deterministic cleanup.

### Stage C — continuous screen evidence — COMPLETE AS EXPERIMENTAL (v0.20.0)
Parallel MediaCodec/device-PTS screen evidence with explicit A/B report. Canonical screenrecord is not yet replaced.

### Stage D — interaction completeness — COMPLETE (v0.21.0)
Two-pointer gestures over existing gRPC input plus display-geometry generation safety and semantic interaction evidence.

## Stage E — deeper evidence intelligence — ACTIVE

### v0.22 target — Packet ↔ Action temporal evidence

Extend Packet Inspector using only evidence already present in the Research ZIP:
- read canonical `research-timeline.json` action windows;
- for each inspected packet, identify action windows that contain the packet target timestamp and that reference the selected flow;
- label relation strictly as `temporal-only` with `causal_claim=false`;
- expose action IDs/labels in packet search/table/details;
- add direct Packet → Timeline navigation;
- preserve raw PCAP authority and create no new raw artifact;
- add regression tests and real-AVD acceptance for correlation invariants.

Later Stage E work may deepen protocol/session drill-down and screen/network cross-links only where clock-domain provenance is sufficient.

## Explicit exclusions

- Audio Evidence: out of scope.
- Virtual Display: out of scope.
- scrcpy-style encoded video must not replace gRPC/MMAP live display.
