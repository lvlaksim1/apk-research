# Next Actions

1. Treat v0.30.0 / `1d75ec32d80cdea2af172035d43d12d3284978fa` as the verified baseline.
2. Deliver/use `apk-research-update_v0.30.0.exe` for an existing installation.
3. Preserve the separate Setup/Update installer contract and SHA-256 verification.
4. Preserve the new HTTP/HTTPS transaction evidence and dedicated viewer.
5. Preserve passive RAW PCAP as an independent evidence source.
6. Keep the Android home-screen shortcut task cancelled.
7. Validate v0.30.0 on representative owner-selected real APK/XAPK applications.
8. If readable HTTPS transactions are missing for a target, diagnose the concrete cause first: certificate pinning, custom trust, QUIC/HTTP3, proxy avoidance, or another target-specific mechanism.
9. Do not start a broader follow-up feature stage until the owner explicitly defines it.
