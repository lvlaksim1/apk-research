# Latest Handoff

Generation: 18
Date: 2026-10-07

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

Verified product baseline is **apk-research v0.28.0** at `df2faf74a707cf99afa366433c34dc89cec37dcc`.

Installer: `apk-research-setup_v0.28.0.exe`.
SHA-256: `9c5444503b6306497ebe5acac87040830d0eefa2fbdb16c06cd521b50f8bd61e`.
Size: 36,436,053 bytes.
Release published: 2026-10-07T12:31:51Z.

v0.28.0 adds verified direct GitHub self-update:
- Settings button to check latest stable release;
- update button appears only for a newer version;
- exact versioned installer + SHA256SUMS are required;
- installer downloads directly from GitHub and is locally SHA-256/size verified;
- detached Windows handoff waits for app exit, silently updates same directory, then restarts;
- no background polling;
- update is blocked during active research/managed operations.

PR #19 and main pipeline #138 passed all mandatory gates, including CI, real XAPK installation, real AVD Research ZIP acceptance, Windows GUI/installer, clean-Windows provisioning and release publication.

Important bootstrap: v0.27.0 and older do not contain the updater, so v0.28.0 must be installed manually once. From v0.28.0 onward this update path is available.

Protected evidence/runtime semantics remain unchanged.

No v0.29 or later feature stage is active. Await owner direction.
