# Next Actions

1. v0.32.0 at `a2f0bbbca364714d37f7697ffa5ccb8204bc94b1` is the verified product baseline. Preserve separate Setup/Update assets, integrity checks and both Default/Google APIs Android 15 profiles.
2. The owner has not yet tested direct HTTPS routing on the previously problematic `com.evrasia` application. Request/inspect a v0.32.0 Research ZIP produced by a real user session; do not assume success from the synthetic `Proxy.NO_PROXY` test.
3. Examine `01_raw/network/https-direct-route.log` for `CONNECTION_ROUTED` entries, `02_normalized/http-transactions.jsonl` for actual readable HTTP(S) request/response data, and `02_normalized/http-interception.json` for verified route cleanup and Android UID. Keep independent RAW PCAP evidence.
4. If the target still has zero readable transactions, use logged destination and specific proxy/TLS errors to determine whether additional application trust, IPv6, QUIC/UDP443 or other runtime conditions matter. Do not invent unsupported causes or change other apps' routes.
5. Maintain v0.31 ARM64 APK/XAPK capability, native JNI proof gate, root and gRPC/MMAP, trustworthy session provenance, and normal in-place update architecture.
6. The Android home-screen shortcut task remains cancelled. Use neutral terms for HTTPS routing/analysis in all owner-visible reporting.
