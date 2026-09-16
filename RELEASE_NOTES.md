# apk-research v0.16.0

v0.16.0 adds passive **QUIC v1/v2 and HTTP/3 network intelligence** to post-capture analysis.

## Added

- recognizes QUIC v1 and QUIC v2 long-header traffic from captured UDP payloads;
- derives standards-defined public QUIC Initial protection material and decrypts Initial packets only;
- reassembles client Initial CRYPTO evidence and extracts TLS ClientHello SNI and ALPN;
- classifies ALPN `h3` / `h3-*` as HTTP/3;
- upgrades `02_normalized/network-flows.json` to schema `0.3`;
- records application protocols, QUIC versions, packet types, SNI, ALPN and Initial-decode status per normalized flow;
- adds QUIC/HTTP3 summary counters;
- extends Network Analyzer host selection, search and readable details with QUIC evidence;
- adds RFC 9001 (QUIC v1) and RFC 9369 (QUIC v2) key-vector tests and protected synthetic Client Initial tests.

## Evidence boundary

UDP/443 alone is not treated as proof of QUIC. Initial packet analysis is passive and does not use MITM. Handshake and 1-RTT application payloads remain encrypted and are not claimed as decoded.

Raw PCAP, socket/package ownership attribution, canonical flow IDs, Timeline temporal-only action correlation and the validated v0.10.5 Android runtime/clean-launch path are unchanged.
