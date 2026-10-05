# Current Blockers and Unknowns

Last reconciled: 2026-10-06.

## Product blockers

No known product-code blocker is active. v0.18.0 is published and all publication gates passed.

## Stage B unknowns to prove

The Android sidecar design is not yet validated in apk-research. Stage B must prove on the managed real AVD:
- `app_process` execution of the project-owned payload under shell;
- deterministic host-listen + `adb reverse` connection establishment;
- exact version/protocol handshake;
- bounded startup and failure behavior;
- reliable teardown and removal;
- no interference with the existing Emulator gRPC/MMAP runtime.

These are implementation/acceptance questions, not current product defects.

## Owner-side evidence

A real owner-side v0.18.0 Research ZIP is not yet recorded as accepted. This is useful confirmation of Packet Inspector and Evidence Explorer UX, but it does not block Stage B because v0.18.0 already passed exact-SHA real-AVD release acceptance.

## WHPX

WHPX acceptance is advisory/non-publication-gating. Treat cancellation or queue behavior as infrastructure evidence only, not as a product defect, unless a future claim explicitly requires WHPX.
