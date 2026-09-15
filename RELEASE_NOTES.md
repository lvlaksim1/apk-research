# Mobile Research v0.9.1

v0.9.1 improves Research Timeline accuracy and presentation without changing the validated Android runtime.

## Changes

- User actions are accepted only after the target package launch boundary.
- A high-resolution Windows/Android clock calibration is recorded before launch.
- The refined Timeline uses exclusive post-action windows capped by the next action.
- Correlations expose confidence and ambiguity instead of implying guaranteed causality.
- The Results tab displays Timeline events in a table instead of a raw JSON dump.
- Real AVD acceptance validates the refined timing model.

The embedded runtime remains unchanged: hidden Emulator, gRPC/MMAP framebuffer, and persistent gRPC input.
