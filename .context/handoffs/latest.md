# Latest Handoff

Generation: 27
Date: 2026-10-10
Persistent manager: `apk-research-project-manager`
Manager-state authority: `context`
Product authority: `main`

## Latest product baseline

**apk-research v0.31.0** released on 2026-10-10 at exact main/release SHA `5aab54adc807aff401b59d4c1018795246303b89`. PR #29 merged. Main pipeline #144 attempt 2 succeeded (initial attempt had an intermittent ADB Settings launch failure; subsequent AVD rerun passed without code changes), including CI, real AVD/HTTPS research, Windows setup/update, clean Windows Android provisioning and release publication.

Setup: `apk-research-setup_v0.31.0.exe` SHA-256 `8c253edf38759830fbe8e156282beaa1b2f0f9b98fd6ad3d880679d180176b83`.
Update: `apk-research-update_v0.31.0.exe` SHA-256 `cb41c928aa2fadeb92bf2c17026cc3863e4d094a0cc5fa92a279597d10baabc6`.

## Completed ARM64 APK/XAPK work

The owner required ARM64-only XAPK installation. The app now uses ABI preflight and a separate official Android 15 Google APIs x86_64 image with ARM native translation, preserving original default AVD/userdata. Device advertised `x86_64,arm64-v8a`; real Android 15 test XAPK loaded ARM64 JNI library (`ARM64_NATIVE_LOADED: PASS`); standard research mode passed. Owner-specific XAPK has not been supplied/tested: do not claim universal compatibility.

## Still-active independent owner commitment

Follow the 2026-10-08 direction to route direct HTTPS from `com.evrasia` applications bypassing system proxy into local analyzer. Earlier owner Research ZIP reportedly contained direct remote port 443 connections and no readable transactions. Revalidate actual ZIP before concrete diagnosis. v0.31 ARM compatibility does not implement this requirement.

The owner-cancelled Android home-screen shortcut task remains CANCELLED. Preserve all existing RAW PCAP and Android research invariants. Release only via verified commit-triggered pipeline.
