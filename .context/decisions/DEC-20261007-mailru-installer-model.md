# DEC-20261007 — MailRu-style installer model

Status: accepted and released in v0.29.2.

## Decision

apk-research adopts the proven Windows packaging/update pattern used by lvlaksim1/mailru-desktop:

- separate full installer for first installation;
- separate update installer for existing installations;
- same Inno Setup AppId for both;
- fixed per-user install directory under LocalAppData;
- the application checks GitHub Releases for the dedicated Update asset only;
- the application downloads/verifies that asset, launches it through the Windows shell, then exits;
- Inno Setup owns file replacement and Start-menu/desktop shortcut recreation;
- no PowerShell relay, detached waiter, custom update protocol or uninstall-first flow.

apk-research retains its stronger SHA-256 verification. Stable releases publish both installers plus one SHA256SUMS file covering both.

The redundant Android Home button is removed.

## Evidence

PR #24 passed CI, real AVD acceptance, Windows standalone/GUI, dedicated v0.29.1→v0.29.2 update acceptance and clean-Windows provisioning. Main pipeline #141 passed on exact release SHA 0f9d949e5158860a51d4e83624fa1cbf3db121cc and published v0.29.2.
