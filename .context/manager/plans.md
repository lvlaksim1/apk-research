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

## HTTPS traffic analysis

The v0.30 implementation stage is complete and released.

Verified delivered scope:
- local application-managed HTTPS proxy;
- Android routing through `adb reverse`;
- temporary research CA trust in the managed rooted Android 15 environment;
- HTTP transaction metadata and bodies in Research ZIP;
- dedicated HTTP/HTTPS desktop viewer;
- passive RAW PCAP preserved as an independent evidence source;
- real Android 15 end-to-end acceptance.

Do not claim universal HTTPS decryption. Certificate pinning/custom trust and HTTP/3/QUIC remain separate bounded follow-up areas.

## Current product plan

No additional product feature stage is authorized after v0.30.0.

The next practical step is owner validation on representative real APK/XAPK targets. If a target does not expose readable HTTPS transactions, diagnose the concrete reason first and only then define a bounded follow-up.

The Android home-screen shortcut requirement remains cancelled.
