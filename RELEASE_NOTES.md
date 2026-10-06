# apk-research v0.21.0

v0.21.0 adds **Interaction Completeness** without changing the established Emulator display/runtime architecture.

## Added

- two-pointer Emulator gRPC input through the existing persistent `streamInputEvent`;
- Ctrl+drag symmetric pinch/rotate gesture;
- Shift+drag vertical tilt gesture;
- Ctrl+Shift+drag horizontal tilt gesture;
- one semantic `multi_touch` Timeline action per completed gesture;
- explicit pointer count, gesture mode, start/end points, duration and display-geometry generation in user-action evidence;
- display geometry generations derived from framebuffer size, input size and rotation;
- stale-geometry gesture cancellation instead of remapping old pointer motion onto a new display geometry;
- real-AVD gRPC acceptance that sends a two-pointer TouchEvent.

## Evidence boundary

Multi-touch records what apk-research injected. It does not claim that the target application consumed or causally reacted to the gesture. Existing Action ↔ Flow relationships remain `temporal-only` with `causal_claim=false`.

A gesture interrupted by a display geometry change is recorded explicitly as incomplete rather than silently translated to new coordinates.

## Unchanged

- hidden Emulator → gRPC/MMAP → AndroidView live display;
- v0.10.5 startup/clean-launch sequencing;
- Android sidecar and continuous-screen A/B collector;
- canonical screenrecord evidence;
- raw PCAP and package/socket attribution;
- Audio Evidence and Virtual Display remain out of scope.

## Validation

Release validation includes unit coverage for multi-pointer wire encoding, display-generation tracking, synthetic second-pointer geometry and semantic action recording, plus real-AVD transmission of a two-pointer gRPC TouchEvent.
