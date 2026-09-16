# apk-research v0.16.0

v0.16.0 adds protocol-aware QUIC / HTTP/3 analysis without changing the validated Android runtime or raw capture path.

## Added

- QUIC v1 and QUIC v2 long-header recognition on UDP/443.
- Public QUIC Initial key derivation according to RFC 9001 and RFC 9369.
- Client Initial decryption for forensic metadata extraction; no MITM is required.
- CRYPTO-frame reassembly across multiple client Initial packets.
- TLS ClientHello SNI and ALPN extraction from QUIC Initial traffic.
- HTTP/3 identification when ALPN confirms `h3` / `h3-*`.
- QUIC version, packet-type, ALPN and Initial-decryption evidence in Network Analyzer.
- Free-text search over QUIC/application-protocol metadata.

## Evidence schemas

- `02_normalized/network-flows.json`: schema **0.3**.
- `02_normalized/research-timeline.json`: schema **0.5**.

Raw PCAP remains the source of truth. Existing package/socket attribution and canonical flow IDs are preserved.

## Evidence boundary

apk-research does **not** treat every UDP/443 flow as QUIC. A recognizable QUIC long header must be observed.

Only QUIC Initial protection is decoded. QUIC 1-RTT application payloads remain encrypted. The release does not install a CA, perform TLS/QUIC MITM, hook the researched application or alter captured packet bytes.

## Runtime

The proven runtime remains unchanged:

`hidden Emulator → gRPC → MMAP → AndroidView`

v0.10.5 clean-launch sequencing and all existing collector boundaries remain intact.
