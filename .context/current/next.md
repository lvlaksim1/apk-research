# Next Actions

1. Treat v0.30.0 / `1d75ec32d80cdea2af172035d43d12d3284978fa` as the last verified product release and preserve its independent Setup/Update installers and SHA-256 verification.
2. Carry forward the owner-authorized 2026-10-08 follow-up: automatically route appropriate HTTPS traffic from applications that ignore the Android system proxy to the local analyzer.
3. Re-examine the owner-supplied `20261008T020126.928669Z-e336ad57.research.zip` when accessible. Prior chat reported 23 remote :443 connections (21 to `evrasia.spb.ru`) and zero normalized HTTP transactions; revalidate these findings before root-cause commitments.
4. Inspect `main` HTTPS routing and analyzer code, select the smallest reliable application-targeted routing correction, and preserve accurate provenance/diagnostics.
5. Implement and verify through tests, real Android 15 AVD and a representative affected application. Generic `example.com` success is insufficient for this target-specific acceptance.
6. Preserve passive RAW PCAP independently of derived readable HTTP/HTTPS evidence. Do not overclaim behavior under application-defined TLS trust, certificate pinning or QUIC/HTTP3.
7. Deliver via established commit-triggered CI/release and separate Setup/Update installer architecture when the work passes the required gates.
8. Keep the Android home-screen shortcut task cancelled.
9. In owner-visible messages use neutral technical terms ("HTTPS traffic analysis"/"routing") and avoid the language explicitly prohibited by the owner.
