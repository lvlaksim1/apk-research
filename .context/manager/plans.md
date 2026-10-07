# Manager plans

## Default change/release plan

1. Reinstate from `context` and reconcile live `main`, latest release and CI.
2. Use a dedicated feature/fix branch from the verified baseline.
3. Make the minimum coherent change.
4. Run unit/compile plus relevant real AVD and Windows verification.
5. For updater changes, prove a real previous-release → candidate update with the dedicated Update installer.
6. Publish stable releases only through the main pipeline.
7. Persist verified state and reseal manager integrity.

## Current release architecture

Stable releases publish:
- `apk-research-setup_v<version>.exe`;
- `apk-research-update_v<version>.exe`;
- `SHA256SUMS.txt` covering both.

The application updater uses only the dedicated Update asset.

## Current product plan — HTTPS traffic inspection

The next product stage is focused on decrypted HTTPS traffic display.

1. Add an application-managed intercepting HTTP(S) proxy bundled with the Windows package; no external Python installation or manual proxy setup for normal use.
2. Configure the managed Android emulator to route research traffic through it and provision a trusted research CA in the managed system environment.
3. Capture complete HTTP transactions where decryption succeeds: request URL/method/headers/body and response status/headers/body, with timing and protocol metadata.
4. Add a dedicated HTTPS/HTTP transactions view with search, filtering, human-readable body rendering and raw representation.
5. Archive interception evidence separately from passive RAW PCAP and preserve exact provenance so active interception is never confused with passive observation.
6. Validate on the real managed AVD with representative HTTP/1.1 and HTTP/2 applications before release.
7. Treat certificate pinning/custom trust stores as the next bounded tier. First detect and report interception failure correctly; then implement an explicit enhanced research mode rather than silently modifying applications.
8. Evaluate HTTP/3/QUIC interception separately and never downgrade or block QUIC without recording that the research environment altered transport behavior.

The Android home-screen shortcut requirement remains cancelled.
