# DEC-20261007 — v0.26.0 release baseline

Status: accepted.

## Decision

`apk-research v0.26.0` at commit `cbf6d177e67cd56e980319ab654da2f27a73176a` is the verified product baseline.

Release asset:
- `apk-research-setup_v0.26.0.exe`
- size: 36,409,960 bytes
- SHA-256: `f5ce59d8c51263fd61d425422ee4e3f5a471592c35d1a19f9a1317161e8affb6`
- published: 2026-10-07T03:32:51Z

Main pipeline #135 ran on the exact release SHA. CI, real AVD Research ZIP acceptance, Windows standalone/self-test/GUI smoke, installer build/install/smoke and clean-Windows managed Android provisioning passed before publication.

## Product result

v0.26.0 completes the owner-agreed consolidated roadmap `v0.24 → v0.25 → v0.26`.

Investigator Workspace adds search/filtering, stable EV navigation references, bookmarks, named evidence sets, reverse navigation and Markdown/JSON report export over the existing evidence model.

Workspace state and reports do not alter source evidence or raise evidence strength. RAW PCAP remains authoritative; Action/Flow and Packet/Action remain temporal-only; screen links remain time-aligned navigation; protocol analysis remains captured-packets-only.

## Next state

No v0.27 or other feature stage is active. Further product development requires a new owner direction.
