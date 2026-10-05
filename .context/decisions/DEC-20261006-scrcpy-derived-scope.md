# DEC-20261006 — scrcpy-derived development scope

Status: accepted.

## Decision

Following review of Genymobile/scrcpy v5.0 against apk-research, retain the following development directions:
- project-owned temporary Android-side `app_process` sidecar architecture;
- continuous screen evidence with device-generated presentation timestamps, subject to A/B validation;
- richer multi-touch/control over the existing Emulator gRPC transport;
- stale display-geometry protection for input;
- later optional keyboard/clipboard usability improvements.

Explicitly exclude from the current roadmap:
- Audio Evidence;
- Virtual Display.

The established hidden Emulator → gRPC/MMAP → AndroidView live display/input path remains the product baseline and must not be replaced merely to imitate scrcpy.

## Rationale

The retained items improve evidence continuity, control completeness and runtime robustness while preserving the already validated local Emulator architecture. Audio and Virtual Display do not match the owner's desired product scope.

## Authority

Explicit owner directive on 2026-10-06.
