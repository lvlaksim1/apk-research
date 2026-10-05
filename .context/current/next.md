# Next Actions

1. Treat Audio Evidence and Virtual Display as out of scope unless the owner later explicitly reopens them.
2. Keep the current hidden Emulator → gRPC/MMAP → AndroidView path and v0.10.5 startup/clean-launch sequencing unchanged.
3. First product stage: design and implement a Raw/Packet Inspector under Unified Evidence Explorer so a flow locator can be resolved to concrete PCAP packets inside the GUI.
4. Second stage: introduce a version-pinned project-owned Android-side `app_process` sidecar with deterministic handshake/lifecycle and long-lived transport, without taking over display/input.
5. Third stage: use that sidecar for an experimental continuous screen evidence collector with device PTS; retain current chunked screenrecord until real A/B evidence proves the new collector.
6. Fourth stage: add multi-touch over the existing gRPC input stream and bind input events to display-geometry generation so stale rotation/resize events are rejected.
7. Keep v0.17.0 real-world owner ZIP validation available as a parallel acceptance task; it is useful but not a blocker for starting Stage 1.
8. For every release-bound stage, preserve RAW-first provenance, add regression tests, pass main release gates and verify with real Research ZIP evidence when applicable.
