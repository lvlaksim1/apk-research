# Latest Handoff

Generation: 25
Date: 2026-10-08
Checkpoint: v0.30.0 HTTPS traffic display released and verified.

Persistent manager: `apk-research-project-manager`.

Verified product baseline: **apk-research v0.30.0** at `1d75ec32d80cdea2af172035d43d12d3284978fa`.

Live reconciliation on 2026-10-08 confirmed:
- `main` HEAD = `1d75ec32d80cdea2af172035d43d12d3284978fa`;
- latest GitHub Release = `v0.30.0`, targeting that exact SHA;
- main pipeline #143 = success;
- dedicated Update installer = `apk-research-update_v0.30.0.exe`.

Release assets:
- Setup: `apk-research-setup_v0.30.0.exe`, SHA-256 `6f9f39c67a88344e7181316c6c6445660f2e1d066deaca09ba13f1ec20954e1a`, 47,454,995 bytes.
- Update: `apk-research-update_v0.30.0.exe`, SHA-256 `4189ff6af7c793bef0db99c673b5838d0a8e6a7ad039cb80b688012353484e1a`, 47,455,368 bytes.

COMPLETED OWNER REQUIREMENT:
apk-research now displays decrypted HTTP/HTTPS request/response content where the managed research environment can establish trust.

Verified behavior:
- local application-managed HTTPS proxy;
- Android routing through `adb reverse`;
- temporary trusted research CA on rooted Android 15;
- HTTP transaction metadata and bodies stored in Research ZIP;
- dedicated searchable HTTP/HTTPS desktop viewer;
- actual Android 15 HTTPS request to `https://example.com/` returned HTTP 200 with a non-empty 577-byte response body;
- full existing AVD research acceptance remained healthy afterward;
- real v0.29.2 → v0.30.0 update verification passed.

BOUNDARIES:
Certificate pinning/custom application trust and HTTP/3/QUIC content decryption are not claimed by v0.30.0.

OWNER CANCELLATION:
The Android home-screen shortcut requirement remains cancelled.

No further product stage is authorized. Next useful evidence should come from owner validation on representative real APK/XAPK targets.
