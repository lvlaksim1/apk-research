# Next Actions

1. Treat v0.23.0 / `cde0b56b5332f0b601221c9157efbd90da18fc33` as the verified product baseline.
2. Keep Audio Evidence and Virtual Display out of scope.
3. Preserve hidden Emulator → gRPC/MMAP → AndroidView and v0.10.5 startup/clean-launch sequencing.
4. For the next Stage E increment, inspect the remaining packet/process/socket/Timeline navigation and evidence gaps on v0.23 and choose the smallest high-value addition.
5. Preserve capture-bounded semantics: unobserved packets/events remain unobserved, not inferred absent.
6. Keep continuous-screen evidence experimental until explicit owner-side A/B promotion evidence exists.
7. If an owner-side v0.23+ Research ZIP is supplied, perform real-world acceptance of Evidence → Packet → Timeline plus transport-session presentation and use observed gaps to prioritize v0.24.
8. For every release-bound change, add regression coverage, run real-AVD/Windows gates and publish only through the main pipeline.
