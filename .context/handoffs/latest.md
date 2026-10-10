# Latest Handoff

Generation: 31
Date: 2026-10-10
Persistent manager: apk-research-project-manager
Product: main
Manager state: context

## Last PUBLISHED version

v0.33.0, main 3f3f1144e0ea8944a065e7d5950fd07fd1e17abf. Do not present v0.34.0 as already released.

## ACTIVE v0.34.0 development

Draft PR #32, branch feature/v0.34-emulator-controls-network-evidence, latest branch commit 8c1dbcc81fa3620ed96b30300211c90fb7872ec3. Adds right-hand Android emulator toolbar: Back/Home/Recent, volume, rotation, PNG screenshot, fullscreen, APK/XAPK, reboot; more menu: shared storage file send/receive, selected app stop/data clear/system settings, simulated position and movement, typing from PC clipboard. UI destructive actions are confirm-gated and mostly disallowed during research. No extra main tabs.

Research ZIP derivation includes six registered normalized files: dns.jsonl, tls-sessions.jsonl, network-timings.jsonl, action-network-links.jsonl, screen-timing.jsonl, network-enrichment.json. Uses available ordinary DNS packets, visible TLS Hello (including local routed TCP ports), HTTP times, temporal action candidate links and true video PTS values. Original PCAP, full HTTP bodies, video and integrity remain separate. Do not invent causal relationships or visual latency.

Earlier real AVD acceptance passed and verified 3660 packets plus 6 ZIP artifacts, and unit tests passed at SHA 8afe5c1d. Latest exact candidate still needs mandatory final CI, AVD and Windows tests. Some intermediate AVD runs had recurring transient Android Settings ADB 255; do not conceal or bypass a failed gate.

After full PR checks, merge, verify main pipeline, and release separate Setup/Update v0.34.0 installers. Only then mark complete.

Owner-specific previous com.evrasia direct HTTPS gap remains previously resolved, prior user's ZIP contains credentials and must not be posted publicly. Neutral terms only; preserve cancellation of launcher icon request.
