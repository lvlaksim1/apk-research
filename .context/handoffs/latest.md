# Latest Handoff

Generation: 21
Date: 2026-10-07

Persistent manager: `apk-research-project-manager`.

Verified product baseline: **apk-research v0.29.2** at `0f9d949e5158860a51d4e83624fa1cbf3db121cc`.

Release assets:
- Setup: `apk-research-setup_v0.29.2.exe`, SHA-256 `6acc5b72337faa92cfd930ed88151445fb218eb580b54eb4e5f65112b457c1f0`, 36,477,159 bytes.
- Update: `apk-research-update_v0.29.2.exe`, SHA-256 `812382bbf61613f296e011c4fead9d5ede00bab9fb44679c76a6b27a542d4821`, 36,477,534 bytes.

v0.29.2 adopts the proven MailRu Desktop Windows installer pattern:
- separate first-install Setup and existing-install Update packages;
- Update is the only asset used by the in-app updater;
- downloaded Update retains SHA-256 verification;
- Update is launched directly via the Windows shell;
- apk-research exits after launch;
- Inno Setup updates files and recreates Start-menu/optional desktop shortcuts;
- no uninstall-first flow.

The redundant Android Home button is removed.

PR #24 and main pipeline #141 passed all mandatory release gates.

The prior experimental forced Android Launcher3 workspace shortcut work was not merged; MailRu Desktop provides no Android analogue. Continue that only as a separate feature if explicitly requested.
