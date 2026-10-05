# Manager intentions and commitments

## Active — Stage B Android sidecar foundation

Status: active.

Continue from the verified v0.18.0 baseline and implement a project-owned temporary Android-side `app_process` sidecar foundation. It must use explicit client/agent version compatibility, a long-lived local transport, deterministic lifecycle/cleanup and a startup design that avoids polling races where practical.

The sidecar is infrastructure for future evidence collection. It must not replace or become a fallback for the proven hidden Emulator → gRPC/MMAP → AndroidView display/input path.

## Active — continuity and evidence-preserving development

Status: active.

Maintain project continuity across runtimes, reconcile durable context with live repository/CI/release evidence before consequential changes, and preserve the established RAW-first evidence and v0.10.5 runtime/clean-launch invariants.

## Proposed — owner-side v0.18.0 real-world validation

Status: proposed, not blocking.

If the owner supplies a real v0.18.0 Research ZIP or reports GUI behavior, validate Packet Inspector, Evidence Explorer and the unchanged forensic chain against that owner-side evidence. The successful release-gate real AVD evidence is sufficient to continue Stage B without waiting for this.
