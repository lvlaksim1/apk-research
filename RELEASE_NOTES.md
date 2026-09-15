# Mobile Research v0.9.2

v0.9.2 makes the refined Research Timeline canonical inside the exported forensic archive and introduces versioned installer filenames.

## Changes

- ResearchOrchestrator now builds the schema 0.2 refined Timeline before creating the Research ZIP.
- The Timeline stored in the ZIP uses the recorded high-resolution `adb-ntp-midpoint` Windows/Android clock calibration.
- Correlation windows are exclusive and capped by the next user action.
- Exported correlations keep `causal_claim=false` and `attribution=temporal-only`.
- Real AVD acceptance validates these invariants directly in the finished ZIP instead of only rebuilding the Timeline afterward.
- End-to-end regression coverage checks that the exported archive itself contains the refined Timeline.
- The Windows installer is now named `MobileResearchSetup_v0.9.2.exe`; subsequent releases follow `MobileResearchSetup_v<version>.exe`.

The validated Android runtime is unchanged: hidden Emulator, gRPC/MMAP framebuffer, and persistent gRPC input.
