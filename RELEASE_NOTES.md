# Mobile Research v0.11.0

v0.11.0 adds normalized bidirectional network flows and the first integrated Network Analyzer GUI.

## Network flow model

- `network-flows.json` is now schema `0.2`.
- One TCP/UDP bidirectional 5-tuple is represented by one flow.
- Inbound and outbound packets no longer become separate records.
- Early packets that were initially `UNKNOWN` are retained in the same connection when later socket/PID evidence attributes that connection to the researched package.
- Each flow contains:
  - best package owner and confidence;
  - per-packet confidence breakdown;
  - outbound/inbound packet counts;
  - outbound/inbound captured bytes;
  - local and remote endpoints;
  - first/last timestamps and duration;
  - DNS queries and TLS SNI observed on the flow.

## Network Analyzer

- New `Network` tab in the desktop application.
- `Network Analyzer` button opens the selected Research ZIP directly from Results.
- Filters: researched application / unknown, TCP / UDP.
- Search: host, IP, process, DNS and SNI.
- Main table: time, owner, host, protocol, local endpoint, remote endpoint, upload, download and confidence.
- Full normalized flow JSON is shown for the selected row.

## Compatibility

- The validated v0.10.5 clean-launch mechanism is unchanged.
- Raw PCAP remains the source of truth; normalized flows are derived forensic evidence.
- Package/PID/socket attribution semantics remain additive and do not claim causality.
- Installer asset: `MobileResearchSetup_v0.11.0.exe`.
