# Mobile Research v0.10.2

v0.10.2 fixes the visible minimize/reopen transition reported on real Windows hardware when starting research in «Чистый запуск» mode.

## Changes

- Clean mode no longer performs separate host-side `force-stop`, process polling and later Activity launch commands.
- The stop and cold start are issued in one Android shell transaction immediately after all collectors are armed.
- The launched Activity carries `FLAG_ACTIVITY_NO_ANIMATION`, suppressing the redundant task entrance animation without changing application-internal animations.
- Clean launch is accepted only when Android `am start -W` reports `LaunchState: COLD`; reuse or WARM/HOT launch fails the invariant.
- Real AVD acceptance first prewarms the target package and then verifies that the exported Research ZIP records a COLD launch.
- «Продолжить текущее состояние» behavior is unchanged.
- Package-aware PID/socket attribution from v0.10.1 is unchanged.
- Installer asset: `MobileResearchSetup_v0.10.2.exe`.

The clean-launch boundary remains after collector startup, so raw screen/logcat/PCAP evidence still covers the cold-start itself.
