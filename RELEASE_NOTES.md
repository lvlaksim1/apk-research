# apk-research v0.19.0

v0.19.0 adds the **Android Sidecar Foundation**: a minimal, versioned, temporary `app_process` agent for future evidence collectors without changing the validated Emulator display/input runtime.

## Added

- project-owned Java sidecar source compiled to a DEX/JAR during release builds;
- bundled `apk-research-agent.jar` inside the standalone Windows distribution;
- deterministic deployment under `/data/local/tmp/apk-research/sidecar`;
- host-listen-first TCP transport bridged by `adb reverse`, avoiding device-port readiness polling;
- exact protocol-version and agent-version handshake;
- a single persistent control socket with bounded line protocol;
- `PING/PONG` health request with agent-side monotonic uptime;
- graceful `STOP/BYE` shutdown;
- deterministic removal of the adb reverse mapping and temporary agent JAR;
- real-AVD lifecycle acceptance followed by a second gRPC/MMAP validation;
- packaged self-test verification that the sidecar payload is present in the installed product.

## Boundary

The sidecar is infrastructure only in v0.19.0. No collector uses it yet.

It does **not** replace:
- hidden Emulator → gRPC/MMAP → AndroidView display;
- persistent Emulator gRPC input;
- v0.10.5 startup/clean-launch sequencing;
- current screenrecord capture;
- raw PCAP/network collectors.

Audio Evidence and Virtual Display remain out of scope.

## Validation

Stable publication requires normal CI, sidecar build, real AVD sidecar lifecycle acceptance, real Research ZIP acceptance, Windows standalone/GUI/installer smoke, clean-Windows provisioning and checksum verification.
