# Latest Handoff

Generation: 2
Date: 2026-10-06

The persistent Project Manager `apk-research-project-manager` is active.

Authority split:
- manager state: `context`;
- product baseline: `main`;
- discovery: `main`.

Current product baseline remains apk-research v0.17.0 / `202d42fcfcccf03e0a9189a1a97f6e57be3578b8`; the later main commit only adds Project Manager discovery files. Release pipeline #118 and context-bootstrap pipeline #119 are green.

The owner reviewed the scrcpy-derived development directions and explicitly excluded Audio Evidence and Virtual Display. The accepted direction preserves the current gRPC/MMAP runtime and prioritizes: in-app raw packet inspection, a bounded Android-side app_process sidecar, continuous device-PTS screen evidence after A/B validation, and richer multi-touch/geometry-safe input.

No new product-code branch has been started for this roadmap yet.
