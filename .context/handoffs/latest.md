# Latest Handoff

Generation: 3
Date: 2026-10-06

The persistent Project Manager `apk-research-project-manager` is active.

Authority split:
- manager state: `context`;
- product baseline: `main`;
- discovery: `main`.

Current verified product baseline is apk-research v0.18.0 at `4d9f3097406502ec397416ea3e7ce07264e74814`. Main pipeline #120 completed SUCCESS and GitHub Release v0.18.0 was published. Installer `apk-research-setup_v0.18.0.exe` SHA-256 is `dcae7555a407ba840577e22e4447d20e4afc44804582e8ab8954d40406d9f2a9`.

Stage A is complete: Raw / Packet Inspector resolves normalized flows to concrete records in the original PCAP and passed real-AVD Research ZIP acceptance plus Windows packaged GUI/install smoke.

Stage B is now the active roadmap item: a project-owned temporary Android `app_process` sidecar foundation with exact version handshake, long-lived transport, host-listen + adb reverse startup and deterministic cleanup. It must not replace the established gRPC/MMAP display/input path.

Audio Evidence and Virtual Display remain explicitly excluded.
