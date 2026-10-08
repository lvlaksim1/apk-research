# apk-research v0.30.0 — HTTPS Traffic Inspection

v0.30.0 adds first-class inspection of decrypted HTTPS traffic in the managed Android research environment.

## HTTPS interception

During a research session apk-research now:
- starts an isolated bundled HTTPS proxy worker;
- routes the managed Android emulator through it using `adb reverse`;
- injects the research CA into the rooted Android 15 system trust environment;
- records decrypted HTTP transactions where interception succeeds;
- restores Android proxy/routing state during teardown.

The private CA key remains in the proxy runtime configuration and is not exported into the Research ZIP.

## Research ZIP

New evidence includes:
- `02_normalized/http-transactions.jsonl`;
- `02_normalized/http-bodies/*`;
- `02_normalized/http-interception.json`;
- `01_raw/network/https-proxy.stderr.txt`.

Transactions retain URL, method, protocol, request/response headers, status, timing and body references.

## Desktop UI

The Results tab now has an **HTTP/HTTPS** viewer with search plus separate request/response header and body panes. JSON is formatted for reading; binary payloads are shown as bounded hexadecimal previews.

## Verification

The real Android 15 release gate installs a dedicated test APK and requires a genuine `https://example.com/` request to be decrypted and exported with HTTP status 200 and a non-empty response body.

## Boundaries

This is active interception, not passive observation. The Research ZIP records that the explicit Android proxy can change transport behavior. RAW PCAP remains the source of truth for traffic actually observed in that research environment.

Applications using certificate pinning or a custom trust store can still reject interception. v0.30.0 detects proxy errors but does not claim a universal pinning bypass.

HTTP/3/QUIC decryption is not claimed by this release.
