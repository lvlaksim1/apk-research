# Next Actions

1. Treat v0.22.0 / `d58265584223246974fb641f02e0dd3fb8d3f4f1` as the verified product baseline.
2. Keep Audio Evidence and Virtual Display out of scope.
3. Preserve hidden Emulator → gRPC/MMAP → AndroidView and v0.10.5 startup/clean-launch sequencing.
4. For the next Stage E increment, first inspect the remaining evidence-navigation/packet-analysis gaps on v0.22 and choose the smallest high-value addition; prefer richer packet/session semantics or provenance-preserving cross-links over new capture mechanisms.
5. If an owner-side v0.22+ Research ZIP is supplied, perform real-world acceptance of Evidence → Packet → Timeline navigation and use it to prioritize the next Stage E work.
6. Keep continuous-screen evidence experimental until explicit owner-side A/B promotion evidence exists.
7. For every release-bound change, add regression coverage, run real-AVD/Windows gates and publish only through the main pipeline.
