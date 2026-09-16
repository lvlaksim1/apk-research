# Mobile Research v0.14.0

v0.14.0 refines Host Intelligence using evidence from a real v0.13.0 Research ZIP. Network Analyzer now distinguishes service connections from DNS-resolution traffic instead of mixing both roles into one host summary.

## Service vs DNS

- DNS-resolution flow is identified only when a TCP/UDP flow contains DNS queries and uses port 53.
- Other flows remain service flows.
- Host owner/confidence is derived from service flows when present.
- DNS resolver traffic therefore no longer turns a proven app-owned host into package + Unknown merely because DNS itself could not be package-attributed.

## Host details

The host evidence card now shows separately:

- first and last observed activity;
- total, service and DNS flow counts;
- aggregate packets and captured bytes;
- service remote IP addresses and ports;
- service owner/confidence;
- DNS resolver IP addresses;
- linked Timeline actions.

For a DNS-only hostname the UI explicitly states that name resolution was observed but a service flow carrying that hostname was not confirmed.

## Real archive finding addressed

In the validation archive, evrasia.spb.ru contained app-owned HTTPS service flows to 217.197.238.66:443 and separate Unknown DNS flows to emulator resolver 10.0.2.3:53. v0.14.0 preserves both evidence classes but displays their roles separately.

## Forensic compatibility

- No Research ZIP schema change.
- Raw PCAP remains the source of truth.
- network-flows.json remains schema 0.2.
- Canonical flow_id and Timeline schema 0.4 remain unchanged.
- Package attribution evidence and temporal-only action correlation are unchanged.
- The validated hidden Emulator → gRPC/MMAP runtime and v0.10.5 clean-launch path are unchanged.
- Installer asset: MobileResearchSetup_v0.14.0.exe.
