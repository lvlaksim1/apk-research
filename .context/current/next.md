# Next Actions

1. Treat v0.22.0 / `d58265584223246974fb641f02e0dd3fb8d3f4f1` as the current verified release baseline.
2. Complete v0.23 release preparation for `dev-v023-transport-session`: release/version documentation, final branch consistency check and promotion through the commit-triggered main pipeline.
3. Do not change the already-green v0.23 transport evidence semantics merely to make lifecycle coverage look more complete; absence from capture must remain `not observed`, not inferred absence.
4. Keep Audio Evidence and Virtual Display out of scope.
5. Preserve hidden Emulator → gRPC/MMAP → AndroidView and v0.10.5 startup/clean-launch sequencing.
6. Keep continuous-screen evidence experimental until explicit owner-side A/B promotion evidence exists.
7. After v0.23 release, choose the next Stage E increment from remaining packet/session/provenance gaps, preferring stronger evidence interpretation over new capture mechanisms.
8. If an owner-side v0.22+ Research ZIP is supplied, perform real-world acceptance and use observed gaps to reprioritize Stage E.
