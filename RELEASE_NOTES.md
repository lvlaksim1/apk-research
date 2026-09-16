# Mobile Research v0.10.4

v0.10.4 fixes the remaining delayed clean-start effect observed on real Windows hardware.

## What changed

- The true clean restart still occurs only after logcat, raw screen recording, PCAP and socket attribution are armed.
- The expensive full Device/Package Metadata snapshot no longer runs before that restart.
- Clean restart is now requested immediately after the capture collectors become active, instead of several seconds later.
- Full metadata and clock calibration are collected after the package has been cold-started; they remain part of the same Research ZIP and remain mandatory for a complete session.
- The operator preview hold introduced in v0.10.3 is unchanged.
- A real AVD release gate now rejects builds where the clean-restart request is delayed by more than 4 seconds from session creation.
- Installer asset: `MobileResearchSetup_v0.10.4.exe`.

A clean launch still necessarily restarts the target process once; v0.10.4 makes that restart part of the immediate start action instead of a delayed surprise.
