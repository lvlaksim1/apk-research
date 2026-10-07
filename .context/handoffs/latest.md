# Latest Handoff

Generation: 20
Date: 2026-10-07

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

Verified product baseline is **apk-research v0.29.1** at `ae4450ba662299c30199742ba4b1d2bbcdb27601`.

Installer: `apk-research-setup_v0.29.1.exe`.
SHA-256: `f853d8672dd4f0c5e80ed39c4b538d38d25b52ea6be8a1cbee3ba03f3e194e49`.
Size: 36,474,197 bytes.
Release published: 2026-10-07T14:37:24Z.

v0.29.1 fixes the owner-reported updater failure after GUI exit:
- hidden PowerShell relay removed;
- verified installer launched directly;
- Inno Setup owns successful relaunch;
- persistent handoff/installer logs added;
- Windows acceptance proves v0.29.0 → v0.29.1 update survives initiating-process exit.

Main pipeline #140 passed all mandatory gates after one exact AVD rerun. The first AVD attempt had a non-reproduced Continuous Screen failure while the session/ZIP and other layers passed; the rerun passed.

Important: installed v0.28.0/v0.29.0 contains the old broken relay, so an affected user must manually install v0.29.1 once. Future updates can then use the corrected mechanism.

No later feature stage is active. Await owner direction.
