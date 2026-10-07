# Latest Handoff

Generation: 19
Date: 2026-10-07

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

Verified product baseline is **apk-research v0.29.0** at `81a565dbc3b4c41712b8a6e3c3ba8020060ff5a2`.

Installer: `apk-research-setup_v0.29.0.exe`.
SHA-256: `a6277849cc9ced994cb439698f84d3376cadf373fa3358d1e0e8e16b69f216c5`.
Size: 36,475,884 bytes.
Release published: 2026-10-07T14:02:55Z.

v0.29.0 delivers:
- new application icon used by window, EXE, installer and shortcuts;
- ABI-aware XAPK split selection and readable mismatch diagnostics;
- explicit install/launch/Android-home controls;
- in-place installer update mode without uninstall-first behavior.

PR #20 and main pipeline #139 passed all mandatory gates, including CI, real XAPK installation, real AVD Research ZIP acceptance, Windows GUI/installer, clean-Windows provisioning and release publication.

WHPX remains advisory/non-publication-gating.

Protected evidence/runtime semantics remain unchanged.

No v0.30 or later feature stage is active. Await owner direction.
