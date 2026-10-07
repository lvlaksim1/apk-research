# apk-research v0.29.2 — Separate Setup and Update Installers

v0.29.2 replaces the custom single-installer update path with the same simple architecture used by MailRu Desktop.

## Windows installers

Every release now contains:
- `apk-research-setup_v0.29.2.exe` — first installation;
- `apk-research-update_v0.29.2.exe` — update of an existing installation;
- `SHA256SUMS.txt` — SHA-256 for both installers.

The Update package uses the same Inno Setup AppId and updates the existing application files without uninstalling first. It refuses to run when apk-research is not installed.

## In-app update

The application:
1. checks the latest stable GitHub Release;
2. selects only the dedicated Update installer;
3. downloads it to the local apk-research Updates directory;
4. verifies its SHA-256;
5. launches the installer through the Windows shell;
6. closes apk-research.

The installer UI then owns the update flow, matching MailRu Desktop.

## Shortcuts

Inno Setup creates the Start-menu shortcut and the optional desktop shortcut during first install and recreates them during update so icon/metadata changes are refreshed.

## UI cleanup

The redundant «Открыть главный экран Android» button is removed.

## Compatibility

Android runtime, APK/XAPK intake, evidence collection and Research ZIP semantics are unchanged.
