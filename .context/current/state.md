# Current Project State

Last reconciled: 2026-10-06.

## Product

- Product: `apk-research`.
- Product authority branch: `main`.
- Current product/release commit: `4d9f3097406502ec397416ea3e7ce07264e74814`.
- Latest published release: `v0.18.0`.
- Release installer: `apk-research-setup_v0.18.0.exe`.
- Installer SHA-256: `dcae7555a407ba840577e22e4447d20e4afc44804582e8ab8954d40406d9f2a9`.
- Release published: 2026-10-05T23:56:05Z.

## v0.18.0 — Raw / Packet Inspector

Stage A of the post-v0.17 roadmap is complete.

The desktop GUI now resolves:
`Action → Host → Flow → Process/Socket → Packet → Raw PCAP`.

Packet Inspector reads the existing raw PCAP directly from the Research ZIP, uses the canonical bidirectional normalized-flow identity, exposes per-packet timestamp/direction/endpoints/lengths, preserves global packet index plus PCAP record/frame byte offsets, and provides only a bounded raw hex preview. It does not create a replacement forensic artifact or present encrypted payload as plaintext.

## Verified release state

Main pipeline #120 (`37390818056`) completed successfully for the exact v0.18.0 release commit:
- CI/compile/tests passed;
- real AVD boot and required gRPC/MMAP transport passed;
- real AVD Research Session and generated Research ZIP verification passed;
- Packet Inspector real-archive acceptance passed, including normalized-flow packet-count equality and valid raw PCAP offsets;
- Windows standalone build/self-test/full GUI smoke passed;
- Inno installer build passed;
- installed application self-test/GUI smoke passed;
- clean-Windows managed Android provisioning passed;
- installer checksum verification and GitHub Release publication passed.

## Real-world validation lineage

- v0.16.1 remains owner-accepted from a real owner-provided Research ZIP.
- v0.18.0 has exact-SHA release-gate real AVD/Research ZIP acceptance, including the new Packet Inspector.
- No owner-provided v0.18.0 Research ZIP acceptance is recorded yet; this is useful but not a blocker.

## Current development direction

Stage B is next and active: establish a project-owned temporary Android `app_process` sidecar with deterministic version handshake, long-lived local transport and cleanup. It is infrastructure only at this stage and must not replace gRPC/MMAP display/input.

Audio Evidence and Virtual Display remain explicitly excluded by owner decision.
