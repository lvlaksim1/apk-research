# Latest Handoff

Generation: 24
Date: 2026-10-08
Checkpoint: owner clarified the next development target as decrypted HTTPS traffic display.

Persistent manager: `apk-research-project-manager`.

Verified product baseline: **apk-research v0.29.2** at `0f9d949e5158860a51d4e83624fa1cbf3db121cc`.

Live reconciliation on 2026-10-08 confirmed:
- `main` HEAD = `0f9d949e5158860a51d4e83624fa1cbf3db121cc`;
- latest GitHub Release = `v0.29.2`, targeting that exact SHA;
- dedicated Update installer remains `apk-research-update_v0.29.2.exe`.

OWNER CANCELLATION:
The Android home-screen shortcut requirement remains cancelled and must not be resumed unless explicitly reopened.

ACTIVE OWNER REQUIREMENT:
The next product capability is display of decrypted HTTPS traffic directly in apk-research.

Acceptance meaning:
- seeing only TLS/QUIC metadata, SNI, host or encrypted packet evidence is insufficient;
- where interception succeeds, the UI must expose the actual HTTP transaction: URL, method/status, headers and request/response bodies;
- passive RAW PCAP remains independently authoritative;
- active interception must carry explicit provenance and must not be confused with passive observation;
- certificate pinning/custom trust and HTTP/3/QUIC are separate capability tiers and must be reported honestly.

Current implementation direction:
- application-managed intercepting HTTP(S) proxy bundled into the standalone Windows application;
- automatic routing of the managed emulator through that proxy;
- trusted research CA provisioning in the managed Android environment;
- first-class HTTPS transaction capture/storage/UI;
- real-AVD end-to-end acceptance for HTTP/1.1 and HTTP/2 first;
- explicit detection of pinning/custom-trust failures before adding an enhanced interception mode.
