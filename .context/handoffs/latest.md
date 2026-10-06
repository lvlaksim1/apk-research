# Latest Handoff

Generation: 9
Date: 2026-10-06

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

Verified product baseline is **apk-research v0.23.1** at `39e483ee03d5337e4e928b4b85cce85c40f4fe35`.

Installer: `apk-research-setup_v0.23.1.exe`.
SHA-256: `b5bf2d31da1c47ef59d351988a09f5c0dad72a8117aab0c4849ae30bb54eb540`.
Size: 36,323,501 bytes.

Main pipeline #127 (`37460233667`) completed SUCCESS and GitHub Release v0.23.1 was published.

v0.23.1 corrects both defects proven by the owner's v0.23.0 archive:
1. exact archived Sidecar loopback control/media traffic remains in RAW PCAP but is excluded from normal app flow/Timeline/action analysis and counted explicitly as infrastructure;
2. the established Sidecar media stream no longer inherits the short 8 s socket timeout.

Real-AVD release acceptance includes a 10 s idle-screen regression and Sidecar flow leakage assertion; both passed. Canonical screenrecord remains authoritative and Continuous Screen remains experimental/non-canonical.

Next valuable input is an owner-side v0.23.1 Research ZIP revalidation.
