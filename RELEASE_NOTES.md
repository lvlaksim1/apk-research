# apk-research v0.26.0 — Investigator Workspace

v0.26.0 turns the existing Unified Session Evidence and Packet Inspector layers into an investigator workflow while preserving the verified capture/runtime baseline and evidence authority boundaries.

## Investigator Workspace

- Adds a dedicated `Investigator` tab over the existing v0.24/v0.25 evidence model.
- Provides global search and intersecting filters by time, event kind, protocol, process/PID/inode, remote endpoint, action and evidence class.
- Assigns reproducible `EV-...` navigation references to existing evidence rows; these references are navigation keys, not new evidence.
- Preserves the original relation type/strength and never upgrades `causal_claim`.

## Bookmarks and evidence sets

- Adds bookmarks for interesting evidence rows.
- Adds named evidence sets for assembling a focused investigation subset.
- Stores user workspace state in a separate `<research.zip>.investigator.json` file next to the archive.
- Never opens or rewrites the immutable Research ZIP to store analyst organization state.
- Prunes stale references when a workspace state no longer resolves against the current evidence model.

## Reverse navigation

- Investigator rows can navigate back to Session Evidence, Timeline, Evidence Explorer, Packet Inspector and screen context using the existing action/flow/time identifiers.
- Evidence-set entries retain their exact `EV-...` reference and can return to the corresponding source evidence.
- Navigation remains presentation-only and does not increase attribution confidence or establish causality.

## Reports

- Generates a report from the active evidence set.
- Supports Markdown and JSON export.
- Every report item retains its EV reference, time, action/flow identifiers, protocols/endpoints/processes, relation type/strength and source-navigation identifiers.
- Inclusion in a report is explicitly analyst selection, not a new forensic fact.

## Evidence boundaries

- Raw `01_raw/network/traffic.pcap` remains authoritative network evidence.
- Action ↔ Flow and Packet ↔ Action remain temporal-only with `causal_claim=false`.
- Screen navigation remains time-aligned and non-causal.
- v0.25 protocol analysis remains `captured-packets-only`.
- Missing packets/events/plaintext/causality are never synthesized.
- Hidden Emulator → gRPC/MMAP → AndroidView, v0.10.5 startup/clean-launch sequencing and the accepted dual-source screen model remain unchanged.
- Audio Evidence and user-facing Virtual Display remain out of scope.
