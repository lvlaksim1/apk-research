# Manager beliefs

## Product baseline and latest release

The product authority is `main`. The current verified product baseline and latest published release are `apk-research v0.21.0` at commit `250c507ca3302558ba11d5df57d3129a38ad6fbe`. Release asset `apk-research-setup_v0.21.0.exe` has SHA-256 `2d655d007b67f5d1c6f866505b9865d300caa6f951e5c90f53af83d7c862d648`.

Main pipeline #124 (`37403912914`) completed successfully for the exact release SHA and published v0.21.0. The separate WHPX acceptance run is advisory and does not gate the release.

- source: GitHub repository main, main pipeline #124 and GitHub Release v0.21.0, reconciled 2026-10-06
- authority: verified-repository + verified-ci

## v0.18.0 Raw / Packet Inspector

v0.18.0 closed the in-app raw-network inspection gap. A selected normalized TCP/UDP flow is resolved against the original `01_raw/network/traffic.pcap` using the same direction-independent canonical flow identity as the normalized inventory. Packet presentation retains original PCAP packet index, record/frame offsets, target timestamp, endpoints and lengths; raw preview is bounded and encrypted payload is not represented as plaintext.

- source: verified v0.18 release and real-AVD release acceptance
- authority: verified-repository + verified-ci

## v0.19.0 Android sidecar foundation

v0.19.0 established the project-owned temporary Android `app_process` sidecar with exact protocol/version handshake, host-listen + `adb reverse` startup, long-lived bounded transport and deterministic cleanup. It does not own display/input.

- source: verified v0.19 release
- authority: verified-repository + verified-ci

## v0.20.0 continuous screen evidence

v0.20.0 added a non-canonical experimental MediaCodec H.264 screen collector over the sidecar with exact encoded bytes, packet/raw-offset index and device-generated presentation timestamps. Canonical Android `screenrecord` remains required until a separate owner-side A/B promotion decision.

- source: verified v0.20 release
- authority: verified-repository + verified-ci

## v0.21.0 interaction completeness

v0.21.0 added geometry-safe two-pointer gestures over the established Emulator gRPC input stream and semantic `multi_touch` evidence. Input is bound to the framebuffer/display geometry generation on which the gesture began; a geometry change terminates stale input rather than remapping it.

- source: verified v0.21 release
- authority: verified-repository + verified-ci

## Proven Android runtime baseline

The validated runtime path remains hidden Android Emulator (`-qt-hide-window`) → Emulator gRPC → MMAP framebuffer → AndroidView, with input through persistent gRPC events. v0.10.5 remains the proven clean-launch sequencing baseline.

- source: repository release lineage and acceptance gates
- authority: verified-repository

## Evidence semantics

Raw PCAP remains the primary network source of truth. Package ownership attribution, normalized flows, Timeline correlation, QUIC/HTTP3 metadata, Unified Evidence Explorer and Packet Inspector are derived/presentation evidence. Action ↔ Flow correlation is temporal-only and must not be promoted into a causal claim.

- source: repository implementation and release documentation
- authority: verified-repository

## Product UX contract

apk-research is a standalone Windows GUI application. Normal use must not require Python or command-line operation; Android runtime is managed by the application. Stable installer filenames include the version.

- source: explicit owner directives
- authority: owner-directive

## Repository release contract

Stable releases are produced by the commit-triggered main pipeline. Temporary verification workflows/artifacts must not remain in the final product tree.

- source: owner directives and repository workflows
- authority: owner-directive

## Manager and product authority split

Persistent manager-state authority is branch `context`; product authority is `main`.

- source: owner authorization and Context Capsule protocol
- authority: owner-directive

## scrcpy-derived scope decision

Audio Evidence and Virtual Display are explicitly out of scope. Retained directions were sidecar, continuous screen evidence, richer multi-touch/control, geometry-generation protection and later optional keyboard/clipboard UX. Stages B-D are now implemented through v0.21.0. The gRPC/MMAP live display/input path remains authoritative.

- source: owner directive on 2026-10-06 plus verified v0.19-v0.21 releases
- authority: owner-directive + verified-repository
