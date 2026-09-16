# Mobile Research v0.13.0

v0.13.0 makes Network Analyzer host-oriented and turns the existing normalized flow evidence into a practical investigation view without changing capture semantics.

## Host → Flow analysis

- Network Analyzer now groups connections by host instead of presenting only a flat list of flows.
- Host identity uses TLS SNI first, DNS query second, and remote IP as a fallback.
- Each host row summarizes:
  - flow and packet counts;
  - TCP/UDP protocols;
  - owner/package state;
  - confidence breakdown;
  - remote IPs;
  - upload/download bytes;
  - linked Timeline actions.
- Expanding a host exposes the original normalized bidirectional flows.

## Human-readable flow evidence

Selecting a flow now shows a readable evidence card instead of raw JSON only:

- protocol and local/remote endpoints;
- first/last timestamps and duration;
- upload/download packet and byte counters;
- package owner and confidence;
- attribution evidence, process, PID and socket inode when available;
- packet-confidence breakdown;
- DNS and TLS SNI evidence;
- correlated Timeline actions.

## Timeline navigation

- Network Analyzer loads Timeline actions together with network flows.
- Linked actions are listed explicitly and can be selected.
- The **Открыть в Timeline** action jumps to the selected Timeline event.
- Double-clicking a flow opens its first linked action.
- Existing Timeline → Network navigation continues to use the same canonical `flow_id`.

## Search and filtering

- Existing owner and TCP/UDP filters are retained.
- Free-text search now covers host/IP/process/DNS/SNI/flow identity and correlated action IDs.
- Host grouping is presentation-only; filtering never rewrites evidence.

## Forensic compatibility

- Raw PCAP remains the source of truth.
- `network-flows.json` remains schema `0.2`.
- Research Timeline remains schema `0.4`.
- Ownership confidence and `temporal-only` correlation semantics are unchanged.
- The validated v0.10.5 clean-launch and hidden Emulator → gRPC/MMAP runtime path are unchanged.
- Installer asset: `MobileResearchSetup_v0.13.0.exe`.
