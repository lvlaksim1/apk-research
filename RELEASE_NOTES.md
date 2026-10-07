# apk-research v0.29.1 — Reliable Self-Update Handoff

v0.29.1 fixes the automatic-update failure where the application downloaded and verified a new release, announced restart, closed, and then nothing else happened.

## Update handoff

- Removes the hidden PowerShell relay entirely.
- Launches the already verified Inno Setup package directly.
- Closes apk-research only after the installer process has been created successfully.
- Lets Inno Setup relaunch the installed application after a successful update.
- Keeps the same installation directory and same AppId; no uninstall-first step is introduced.

## Diagnostics

- Writes a handoff log before closing.
- Passes a persistent installer log path to Inno Setup.
- A future installation failure therefore leaves useful evidence even if apk-research is no longer running.

## Windows acceptance

The build now performs an end-to-end upgrade test:
1. install published v0.29.0;
2. verify the installed version;
3. invoke the candidate updater through production Python code;
4. allow that initiating process to exit;
5. wait in five-second intervals;
6. verify that the installed application becomes v0.29.1.

All previous CI, real AVD, XAPK, Windows GUI/installer and clean-Windows checks remain required.
