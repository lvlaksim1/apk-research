# apk-research v0.25.0 — Transport and Protocol Analysis

v0.25.0 extends Packet Inspector with capture-bounded transport and protocol analysis while preserving the v0.24 unified evidence model and the raw-PCAP authority boundary.

## TCP capture evidence

- Reports whether a plain SYN and FIN/RST are actually present in the selected capture.
- Adds per-direction observations for sequence ranges, ACK values and advertised windows.
- Flags repeated and overlapping observed sequence ranges, observed sequence gaps, repeated ACK values and zero-window packets.
- Explicitly distinguishes observation from inference: a gap is not automatically packet loss, a repeated range is not automatically a network retransmission, and missing start/end markers mean only “not observed in this capture”.

## DNS, TLS and QUIC

- Decodes complete DNS questions and supported resource records directly from captured bytes.
- Groups a DNS query/response transaction only when one selected flow contains one unambiguous query and one response with the same transaction identifier.
- Parses observed TLS ClientHello/ServerHello metadata, including SNI, ALPN, supported/selected version and selected cipher suite when the bytes are available.
- Performs bounded contiguous TCP-payload reconstruction so a TLS hello split across captured segments can be recognized when no observed sequence gap intervenes.
- Aggregates the existing QUIC v1/v2 Initial evidence, SNI and ALPN; HTTP/3 is reported only when `h3` is actually observed in ALPN.

## Observable HTTP

- Recognizes complete cleartext HTTP/1.0 and HTTP/1.1 request/response headers and the cleartext HTTP/2 connection preface.
- Forms a request/response transaction only for one unambiguous complete request and one complete response in opposite directions.
- Encrypted application bytes are never represented as plaintext.

## Packet Inspector integration

- Each inspected flow now contains a structured `protocol_analysis` report with `evidence_basis=captured-packets-only` and `causal_claim=false`.
- The Packets view includes a dedicated v0.25 analysis pane and richer per-packet protocol evidence.
- Search covers observed HTTP/TLS/ACK/sequence evidence in addition to the existing DNS/SNI/QUIC fields.

## Evidence boundaries

- Raw `01_raw/network/traffic.pcap` remains authoritative network evidence.
- Packet/action links remain temporal-only and never claim causality.
- Absence from the analysis means only “not observed in the selected capture”.
- Missing packets, missing protocol messages, plaintext and causality are never synthesized.
- v0.10.5 startup/clean-launch sequencing and the hidden Emulator → gRPC/MMAP → AndroidView live display path remain unchanged.
- Audio Evidence and user-facing Virtual Display remain out of scope.
