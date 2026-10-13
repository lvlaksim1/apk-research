# Next Actions

Status reconciled on 2026-10-13; authoritative manager generation 32.

1. Treat **apk-research v0.34.0** on `main` `2efec386cff0b204ee56d8bee365f3c52caefcb5` as current published baseline. GitHub Release https://github.com/lvlaksim1/apk-research/releases/tag/v0.34.0 has standalone Setup, dedicated Update and SHA256SUMS. Release pipeline #38375309755 passed all mandatory stages. PR #32 merged; PR #33 was closed unmerged.
2. Continue in a NEW CHAT only after loading sealed capsule from branch `context`. Ask for owner's first hands-on findings on v0.34.0: right Android toolbar, safe controls while recording, normal app network access and new ZIP evidence.
3. If a concrete bug is reported, reproduce using branch off this exact main commit; avoid changing emulator network state or data without evidence and approval. Previous loading issue after v0.33 was transient and cleared with restart, with no proven root cause.
4. Validate next owner Research ZIP for six normalized outputs: dns, tls-sessions, network-timings, action-network-links, screen-timing, network-enrichment, and retain existing raw PCAP, HTTPS bodies, video and checksums. State extraction limits and confidence; never fabricate unavailable data.
5. Maintain two main tabs, embedded Android gRPC/MMAP, ARM64/XAPK support, dedicated Windows updater, no unnecessary extra GUI sections, and the owner's cancellation of Android launcher shortcut.
6. Do not expose sensitive ZIP contents in public GitHub. Use neutral Russian terminology. All development/merges/installer releases need new explicit user scope and normal release gates.


## Owner-directed active task, 2026-10-13

13 October 2026: Owner explicitly directed integrated HTTPS list/details to the right of the Android view, click sorting, a non-obscuring Android status line, and immediate right-side emulator controls. Active PR #35, branch feature/v0.35-unified-https-workspace, final candidate 51050663f68516ce0dddec6dfe157f8a931fcab9, version 0.35.0. CI, real Android 15 AVD and ARM64 tests passed. Windows desktop build passed; clean Windows provisioning is in progress. Product main/latest release still 0.34.0 until full verification/merge/main pipeline. The app-specific Android 15 enforced edge-to-edge opt-out is a best-effort compatibility command, recorded in session events; owner app screenshot must confirm visual effect. Do not claim field acceptance without evidence.
After the last Windows provisioning gate passes, promote draft PR #35, merge only verified final SHA, run main publication gates, verify actual v0.35.0 Setup/Update assets, update this capsule, request owner field screenshot and ZIP.
