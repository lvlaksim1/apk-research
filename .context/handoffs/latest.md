# Latest Handoff

Generation: 23
Date: 2026-10-08
Checkpoint: owner cancelled the Android home-screen shortcut task and requested the current update installer.

Persistent manager: `apk-research-project-manager`.

Verified product baseline: **apk-research v0.29.2** at `0f9d949e5158860a51d4e83624fa1cbf3db121cc`.

Live reconciliation on 2026-10-08 confirmed:
- `main` HEAD = `0f9d949e5158860a51d4e83624fa1cbf3db121cc`;
- PR #24 is merged at that SHA;
- latest GitHub Release = `v0.29.2`, targeting that exact SHA.

Release assets:
- Setup: `apk-research-setup_v0.29.2.exe`, SHA-256 `6acc5b72337faa92cfd930ed88151445fb218eb580b54eb4e5f65112b457c1f0`, 36,477,159 bytes.
- Update: `apk-research-update_v0.29.2.exe`, SHA-256 `812382bbf61613f296e011c4fead9d5ede00bab9fb44679c76a6b27a542d4821`, 36,477,534 bytes.
- `SHA256SUMS.txt` covers both.

v0.29.2 uses the MailRu Desktop Windows installer pattern: separate Setup and Update packages, Update-only in-app discovery, SHA-256 verification, direct Windows-shell launch of Update, application exit, and Inno-owned shortcut recreation.

The redundant Android Home button is removed.

OWNER CANCELLATION:
The prior requirement to create an Android home-screen shortcut after APK/XAPK installation was explicitly cancelled on 2026-10-08. It is not an active commitment or blocker and must not be resumed unless explicitly reopened.

No broader v0.30 stage is active.
