# apk-research v0.30.1 — Direct HTTPS Routing

v0.30.1 extends HTTPS traffic analysis for applications that open TLS sockets directly and ignore Android's system proxy setting.

## Direct package routing

During a research session apk-research now:
- keeps the existing application-managed local HTTPS analyzer and research CA;
- identifies the UID of the researched package;
- applies routing only to that package's direct TCP/443 connections;
- preserves the original remote destination inside the managed Android environment;
- forwards those connections into the same HTTP/HTTPS analysis path already used in v0.30.0;
- removes the temporary routing rules and Android helper process during cleanup.

Applications that already honor the Android proxy continue using the existing path.

## Verification target

The Android 15 acceptance APK now opens `https://example.com/` with `Proxy.NO_PROXY`, explicitly bypassing the Android system proxy.

The release gate therefore requires the direct-routing path itself to produce a readable HTTPS transaction with:
- the exact target URL;
- HTTP status 200;
- a non-empty response body;
- `direct_https_routing.enabled = true` in the Research ZIP metadata.

## Evidence

The Research ZIP keeps the existing HTTP/HTTPS transaction files and adds diagnostics for the Android direct-routing helper.

Passive RAW PCAP remains an independent record of traffic observed in the configured research environment.

## Boundaries

v0.30.1 targets TCP/443. HTTP/3/QUIC remains outside this release contract.

Applications that use certificate pinning or their own trust store may still reject the research CA; this release does not claim otherwise.
