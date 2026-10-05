# Next Actions

1. Treat v0.18.0 Raw / Packet Inspector as the verified product baseline.
2. Keep Audio Evidence and Virtual Display out of scope unless the owner explicitly reopens them.
3. Start Stage B from current `main`: create a dedicated sidecar feature branch and introduce the minimum project-owned Android `app_process` agent plus host lifecycle/transport abstraction.
4. Implement exact client/agent protocol-version handshake, host-listen + `adb reverse` connection establishment, bounded timeout/error reporting and deterministic guest/host cleanup.
5. Add unit/protocol tests first, then a dedicated real-AVD acceptance proving start → handshake → request/response → stop/cleanup without changing display/input or the v0.10.5 launch sequence.
6. Do not migrate screen recording onto the sidecar during Stage B. Continuous screen evidence is Stage C and begins only after the sidecar foundation itself is verified.
7. Keep owner-side v0.18.0 Research ZIP validation available in parallel; it is not a blocker for Stage B.
8. Persist any verified Stage B architecture finding and reseal manager state before moving to Stage C.
