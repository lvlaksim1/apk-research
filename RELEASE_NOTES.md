# apk-research v0.16.1

v0.16.1 hardens passive QUIC evidence classification after a real v0.16.0 Research ZIP exposed false positives in ordinary DNS UDP/53 traffic.

## Fixed

- unknown/unsupported QUIC-looking long-header version values are no longer treated as confirmed QUIC;
- QUIC v1/v2 flow context is established only after a supported Initial packet is successfully authenticated/decrypted;
- Version Negotiation, Handshake/0-RTT/Retry and short-header 1-RTT packets require an already confirmed QUIC flow before they are labelled as QUIC;
- outbound client Initial packets below the RFC 9000 1200-byte minimum cannot establish confirmed QUIC context;
- eight real DNS request/response byte prefixes from the failing v0.16.0 archive are covered by permanent regression tests.

## Validation

- full Windows dev suite passes with the new regressions;
- the affected real archive contains no UDP/443 flow, so its previous QUIC count was false evidence;
- the corrected classifier maps those captured DNS prefixes to non-QUIC.

## Evidence boundary

The release remains passive post-capture analysis. Raw PCAP is unchanged and remains the source of truth. QUIC Initial analysis uses only standards-defined public Initial protection material; apk-research does not perform MITM and does not decrypt QUIC Handshake or 1-RTT application content.

Android runtime, v0.10.5 clean-launch sequencing, collectors, socket/package attribution, canonical bidirectional flow identity and Timeline temporal-only correlation are unchanged.
