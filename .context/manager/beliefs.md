# Manager beliefs

## Product baseline and latest release

The product authority is `main`. The current verified product baseline and latest published release are `apk-research v0.26.0` at commit `cbf6d177e67cd56e980319ab654da2f27a73176a`.

Release asset `apk-research-setup_v0.26.0.exe` has SHA-256 `f5ce59d8c51263fd61d425422ee4e3f5a471592c35d1a19f9a1317161e8affb6` and size 36,409,960 bytes. GitHub Release v0.26.0 was published on 2026-10-07 for the exact release SHA after the commit-triggered main pipeline passed CI, real AVD Research ZIP acceptance, Windows standalone/self-test/GUI/installer checks and clean-Windows managed Android provisioning.

- source: GitHub repository main, main pipeline #135 and GitHub Release v0.26.0, reconciled 2026-10-07
- authority: verified-repository + verified-ci

## Completed roadmap through v0.26

- v0.18.0: Raw / Packet Inspector.
- v0.19.0: project-owned Android app_process sidecar foundation.
- v0.20.0: Continuous Screen foundation.
- v0.21.0: geometry-safe two-pointer interaction completeness.
- v0.22.0: Packet ↔ Action temporal evidence.
- v0.23.0: Transport Session Evidence.
- v0.23.1: Sidecar infrastructure isolation + idle stability correction.
- v0.24.0: Unified Session Evidence and cross-navigation.
- v0.25.0: capture-bounded Transport and Protocol Analysis.
- v0.26.0: Investigator Workspace.

The owner-agreed three-stage roadmap `v0.24 → v0.25 → v0.26` is complete.

## v0.26 Investigator Workspace

v0.26 adds an investigator workflow over the existing verified evidence model without replacing capture or source artifacts.

Delivered:
- global search and intersecting filters by time, event kind, protocol, process/PID/inode, endpoint, action and evidence class;
- reproducible `EV-...` navigation references for existing evidence rows;
- bookmarks and named evidence sets stored externally in `<research.zip>.investigator.json`;
- reverse navigation to Session Evidence, Timeline, Evidence Explorer, Packet Inspector and screen context;
- Markdown and JSON report export retaining source-navigation identifiers and original relation type/strength.

`EV-...` references are navigation keys, not new forensic evidence. Report inclusion is analyst selection, not a new observed fact.

## Evidence semantics

Raw PCAP remains authoritative network evidence. Action ↔ Flow and Packet ↔ Action remain temporal-only with `causal_claim=false`. Screen links remain time-aligned navigation and non-causal. v0.25 protocol analysis remains `captured-packets-only`. Missing traffic, plaintext, events or causality are never synthesized.

## Screen evidence role

The owner-approved dual-source model remains active:
- Continuous Screen is stable continuous/timeline screen evidence;
- Android screenrecord remains high-resolution screen evidence;
- sole-source replacement remains deferred until a separate quality uplift and revalidation.

The proven live display/input path remains hidden Emulator → gRPC/MMAP → AndroidView.

## Protected runtime baseline

v0.10.5 startup/clean-launch sequencing remains protected. Audio Evidence and user-facing Virtual Display remain out of scope.

## WHPX

WHPX acceptance remains advisory/non-publication-gating.
