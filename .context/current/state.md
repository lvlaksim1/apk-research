# Current Project State

Last reconciled: 2026-10-07.

## Product

- Current release/main commit: `0f9d949e5158860a51d4e83624fa1cbf3db121cc`.
- Latest release: `v0.29.2`.
- Full installer: `apk-research-setup_v0.29.2.exe`.
- Update installer: `apk-research-update_v0.29.2.exe`.
- Setup SHA-256: `6acc5b72337faa92cfd930ed88151445fb218eb580b54eb4e5f65112b457c1f0`.
- Update SHA-256: `812382bbf61613f296e011c4fead9d5ede00bab9fb44679c76a6b27a542d4821`.

## v0.29.2

The Windows packaging/update path now matches MailRu Desktop structurally: distinct Setup and Update installers, direct Windows-shell launch of Update, same AppId, fixed per-user install directory, and Inno-owned shortcut recreation.

SHA-256 verification remains mandatory and validates both published installers.

The explicit Android Home button is removed.

## Verification

PR #24 and main pipeline #141 passed:
- full CI;
- real AVD acceptance;
- Windows standalone and GUI smoke;
- full + update installer build;
- real v0.29.1 → v0.29.2 dedicated update acceptance;
- clean-Windows Android provisioning;
- GitHub Release publication.

## Development status

v0.29.2 is the verified baseline. No later feature stage is active.
