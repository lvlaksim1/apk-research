# Mobile Research v0.10.3

v0.10.3 removes the visible «свернулось → развернулось» effect from the embedded operator view during a verified clean launch without changing the Android research environment or hiding evidence from the Research ZIP.

## Changes

- Keeps the same true clean start: collectors are armed first and Android must report `LaunchState: COLD`.
- The gRPC/MMAP operator preview temporarily holds the last published frame only while the target package is being force-stopped and cold-started.
- The underlying framebuffer stream continues running; fresh frames are retained and the preview resumes immediately after `package_launched`.
- Raw Android `screenrecord` is not frozen or edited. It still records the real stop/task transition, splash screen and cold-start sequence.
- Logcat, PCAP, socket attribution and Timeline capture remain continuous.
- Android animation scales are not modified.
- Continue-current-state mode is unchanged.
- Installer asset: `MobileResearchSetup_v0.10.3.exe`.

This establishes a strict separation between forensic evidence and the operator presentation surface.
