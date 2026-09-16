# Mobile Research v0.12.0

v0.12.0 unifies Research Timeline and Network Analyzer around the same normalized network flow identity.

## Unified flow model

- Research Timeline schema is now `0.4`.
- Timeline no longer creates separate directional TCP/UDP flow markers.
- Every Timeline network event references the canonical `flow_id` from `02_normalized/network-flows.json`.
- User action correlations contain:
  - `flow_ids` — normalized flows that carried packets inside the temporal window;
  - `new_flow_ids` — normalized flows whose first packet appeared in that window.
- Every normalized flow contains `correlated_action_ids` for reverse lookup.
- Ownership remains evidence-based and correlation remains `temporal-only`; no causal claim is introduced.

## Network coverage accounting

`network-flows.json` summary now explicitly reports:

- total source packet count;
- packets represented in TCP/UDP normalized flows;
- non-TCP/UDP packet count and captured bytes;
- non-TCP/UDP protocol counts;
- unresolved TCP/UDP packet count.

Timeline summary exposes `network_flows` and `network_non_tcp_udp_packets`.

## GUI navigation

- Double-click a Timeline action or network-flow row to open the referenced flow in Network Analyzer.
- Double-click a Network Analyzer flow with linked actions to jump back to the first matching Timeline action.
- Network Analyzer summary shows non-TCP/UDP packets explicitly.

## Compatibility

- Raw PCAP remains the source of truth.
- v0.11 flow schema `0.2` remains the normalized connection format.
- The validated v0.10.5 clean-launch/runtime path is unchanged.
- Installer asset: `MobileResearchSetup_v0.12.0.exe`.
