# 2026-10-08 — v0.29.2 chat transition checkpoint

The owner requested that all current project state be persisted before moving to a new chat.

## Live reconciliation

Verified on 2026-10-08:
- main HEAD: `0f9d949e5158860a51d4e83624fa1cbf3db121cc`;
- latest release: `v0.29.2`;
- release target: exact main HEAD;
- PR #24: merged at exact baseline SHA;
- Setup + Update + SHA256SUMS are published.

## Completed work

The Windows installer/update model was replaced with the pattern proven in `lvlaksim1/mailru-desktop`:
- separate Setup and Update Inno installers;
- direct Windows-shell execution of Update;
- no uninstall-first path;
- Inno owns Windows shortcut creation/recreation;
- SHA-256 verification retained in apk-research.

The redundant Android Home button was removed.

## Open work

The owner's earlier requirement remains: after APK/XAPK installation, a launch shortcut for the installed Android application must appear on the managed Android home screen.

MailRu Desktop does not solve this Android requirement; its shortcut is a Windows shortcut.

Research on Launcher3 established:
- managed Android 15 uses Launcher3;
- legacy INSTALL_SHORTCUT is unsuitable;
- provider and direct-database experiments were not stable enough after Launcher3 reconciliation;
- direct database work exposed WAL/cache/reload behavior;
- the experimental branch must not be merged as-is.

Next chat should continue this one bounded Android feature from clean v0.29.2 and require real AVD proof of visible, launchable, stable, non-duplicating shortcut placement.

## Transition

No further code changes are required for this checkpoint. Resume as `apk-research-project-manager` from generation 22.
