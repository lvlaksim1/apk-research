# Mobile Research v0.10.5

v0.10.5 is based on the proven v0.10.3 startup mechanism. The v0.10.4 startup reordering is rolled back after a real Windows test produced `LaunchState=None` on `com.evrasia`.

## Changes

- Restores the complete v0.10.3 clean-launch path.
- Keeps the verified `LaunchState: COLD` check unchanged.
- Keeps the v0.10.3 live-preview hold that removed the visible minimize/reopen transition.
- Keeps logcat, raw screen recording, PCAP and socket attribution ordering unchanged.
- The only startup optimization is that the optional full Package Manager dump is deferred until research stop.
- Lightweight device/package metadata remains captured before the research collectors are armed.
- At stop, the full package dump is captured and written into `01_raw/device/package.txt`; `02_normalized/target.json` is enriched before export.
- Installer asset: `MobileResearchSetup_v0.10.5.exe`.

The goal of this release is deliberately narrow: preserve the working v0.10.3 behavior and remove the several-second pre-launch delay without redesigning startup.
