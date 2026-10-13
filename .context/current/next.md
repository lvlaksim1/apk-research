# Next Actions

Status reconciled on 2026-10-13; authoritative manager generation 32.

1. Treat **apk-research v0.34.0** on `main` `2efec386cff0b204ee56d8bee365f3c52caefcb5` as current published baseline. GitHub Release https://github.com/lvlaksim1/apk-research/releases/tag/v0.34.0 has standalone Setup, dedicated Update and SHA256SUMS. Release pipeline #38375309755 passed all mandatory stages. PR #32 merged; PR #33 was closed unmerged.
2. Continue in a NEW CHAT only after loading sealed capsule from branch `context`. Ask for owner's first hands-on findings on v0.34.0: right Android toolbar, safe controls while recording, normal app network access and new ZIP evidence.
3. If a concrete bug is reported, reproduce using branch off this exact main commit; avoid changing emulator network state or data without evidence and approval. Previous loading issue after v0.33 was transient and cleared with restart, with no proven root cause.
4. Validate next owner Research ZIP for six normalized outputs: dns, tls-sessions, network-timings, action-network-links, screen-timing, network-enrichment, and retain existing raw PCAP, HTTPS bodies, video and checksums. State extraction limits and confidence; never fabricate unavailable data.
5. Maintain two main tabs, embedded Android gRPC/MMAP, ARM64/XAPK support, dedicated Windows updater, no unnecessary extra GUI sections, and the owner's cancellation of Android launcher shortcut.
6. Do not expose sensitive ZIP contents in public GitHub. Use neutral Russian terminology. All development/merges/installer releases need new explicit user scope and normal release gates.
