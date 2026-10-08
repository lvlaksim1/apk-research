# apk-research v0.30.1 — Direct HTTPS Routing

v0.30.1 extends HTTPS traffic analysis to applications that create direct TCP/443 connections and do not use Android's system proxy setting.

## Direct package routing

During a research session apk-research now:
- keeps the existing application-managed local HTTPS analyzer and research CA;
- identifies the UID of the researched package;
- applies temporary routing only to that package's direct TCP/443 connections;
- supports both IPv4 and IPv6 routing inside the managed Android environment;
- reads the TLS ClientHello and uses SNI when available so the analyzer retains the intended server name;
- sends those direct TLS connections into the same HTTP/HTTPS analysis path already used by v0.30.0;
- removes the temporary routing rules and Android helper process during cleanup.

Applications that already honor the Android proxy continue using the existing path.

## Verification

The Android 15 release test creates a direct TLS socket to Android loopback `127.0.0.1:443` and supplies SNI/Host `example.com`. It does not rely on Android DNS or direct Internet routing and does not use the Android system proxy.

Release acceptance requires:
- the direct package-routing mode to be enabled;
- the exact URL `https://example.com/` to appear in the exported HTTP/HTTPS evidence;
- HTTP status 200;
- a non-empty response body;
- the full existing AVD research acceptance to remain valid afterward.

The verified branch run returned HTTP/1.1 200 with a 577-byte response body.

## Evidence

The Research ZIP keeps:
- `02_normalized/http-transactions.jsonl`;
- `02_normalized/http-bodies/*`;
- `02_normalized/http-interception.json`;
- `01_raw/network/https-proxy.stderr.txt`;
- `01_raw/network/https-direct-router.stderr.txt`.

The HTTPS metadata records whether direct routing was successfully enabled during the session, the target package UID, IPv4/IPv6 helper ports and rule diagnostics.

Passive RAW PCAP remains an independent record of traffic observed in the configured research environment.

## Boundaries

v0.30.1 targets TCP/443. HTTP/3/QUIC remains outside this release contract.

Applications that reject the research CA because of certificate pinning or application-owned trust rules remain a separate bounded case.
