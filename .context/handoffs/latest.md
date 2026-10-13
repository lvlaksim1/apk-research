# Latest Handoff

Generation: 32
Date: 2026-10-13
Manager: apk-research-project-manager
Product authority: main
Manager-state authority: context

## LIVE RECONCILIATION — VERIFIED

- Current published release: **v0.34.0**, exact main/release commit `2efec386cff0b204ee56d8bee365f3c52caefcb5`.
- Published release: https://github.com/lvlaksim1/apk-research/releases/tag/v0.34.0, 2026-10-13.
- Successful final release workflow **#38375309755**: CI, real Android 15 AVD research, standalone Windows build/test, upgrade using dedicated Update installer, clean Windows Android provisioning, release publication and cleanup all SUCCESS.
- Prior initial main workflow #38023468111 FAILED the Windows update gate. The publication required an additional release-gating fix and a successful full rerun. Do not erase that history or treat the earlier failed run as final.
- Full installer: `apk-research-setup_v0.34.0.exe`, SHA256 `7ba45c3d5fb4a91d5df8bc3d8431928b135b76251470c0b41f458e778711d233`.
- Update installer: `apk-research-update_v0.34.0.exe`, SHA256 `1df62f8a39c1efbabe201eafaeaaa93e8dd2b4e597bce7364249fafff252e779`.
- `SHA256SUMS.txt` also published.

## FEATURE DELIVERY

Owner approved development of a standard Android emulator side toolbar and richer Research ZIP. **PR #32 merged** in `e9240f05e620b1cee4f2d1d4ee0c14f1d36a111d`, shipping right-side emulator controls (navigation, volume, rotation, screenshot, fullscreen, install/reboot, file transfer, application operations, simulated location/motion, clipboard text input), while preserving only two principal Research and HTTPS Online tabs.

Six additional Research ZIP artifacts: `02_normalized/dns.jsonl`, `tls-sessions.jsonl`, `network-timings.jsonl`, `action-network-links.jsonl`, `screen-timing.jsonl`, `network-enrichment.json`. Their contents derive only from actually observed packets, HTTPS requests/responses, actions, and video timing. No false completeness, causal claims or invented TLS/DNS values. Original RAW PCAP, full HTTP(S) bodies, logs, screen video and manifest integrity are preserved.

**Different draft PR #33** (`feature/v0.34-emulator-controls-evidence`, head `18a0e6fa1b30da9eef8b8ed32ffec0ddca48035d`) was CLOSED WITHOUT MERGE. Older assistant claims about this branch being the final release source are obsolete. Do not resume it as active work or merge its unverified implementation into main.

## USER INCIDENT / RISK

The owner experienced a transient v0.33.0 failure to load com.evrasia data, which resolved following emulator restart. Cause unproven. Proposed separate Android network-recovery changes were deferred, NOT merged or shipped. Avoid speculative resets. Earlier verified direct HTTPS on com.evrasia applies to the tested v0.32 session, not universal guarantees.

Private Research ZIP files can expose session tokens and authentication content; never place them in public repo.

## NEXT CHAT

Restore this capsule generation 32 from `context`, reconcile live main/releases, then await owner field-test feedback or explicit task. Start from v0.34.0 stable. Use neutral Russian terms and conservative status. Preserve owner's cancelled launcher-icon request.


## Current handoff for active v0.35 implementation

13 October 2026: Owner explicitly directed integrated HTTPS list/details to the right of the Android view, click sorting, a non-obscuring Android status line, and immediate right-side emulator controls. Active PR #35, branch feature/v0.35-unified-https-workspace, final candidate 51050663f68516ce0dddec6dfe157f8a931fcab9, version 0.35.0. CI, real Android 15 AVD and ARM64 tests passed. Windows desktop build passed; clean Windows provisioning is in progress. Product main/latest release still 0.34.0 until full verification/merge/main pipeline. The app-specific Android 15 enforced edge-to-edge opt-out is a best-effort compatibility command, recorded in session events; owner app screenshot must confirm visual effect. Do not claim field acceptance without evidence.
