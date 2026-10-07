# Latest Handoff

Generation: 22
Date: 2026-10-08
Checkpoint: user requested durable save before moving to a new chat.

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

v0.29.2 adopts the proven MailRu Desktop Windows installer pattern:
- separate first-install Setup and existing-install Update packages;
- Update is the only asset used by the in-app updater;
- downloaded Update retains SHA-256 verification;
- Update is launched directly via the Windows shell;
- apk-research exits after launch;
- Inno Setup updates files and recreates Start-menu/optional desktop shortcuts;
- no uninstall-first flow.

The redundant Android Home button is removed.

OPEN OWNER REQUIREMENT FOR NEXT CHAT:
After APK/XAPK installation, the installed Android application should appear as a launch shortcut on the managed Android home screen. There should be no separate Home button.

Do not confuse this with MailRu Desktop's Windows shortcut. The prior experimental Launcher3 provider/database branch was not merged because stable real-AVD shortcut persistence was not proven. Continue this feature from clean v0.29.2, using only proven findings from those experiments.

No broader v0.30 stage is active.
