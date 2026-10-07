# Next Actions

1. Treat v0.29.2 / `0f9d949e5158860a51d4e83624fa1cbf3db121cc` as the verified baseline.
2. Preserve the separate Setup/Update installer contract and Inno-owned Windows shortcuts.
3. Keep the Android home-screen shortcut task cancelled.
4. Begin the HTTPS inspection stage from a clean feature branch.
5. Integrate an application-managed intercepting HTTP(S) proxy into the standalone Windows package.
6. Automate managed-emulator proxy routing and research CA trust provisioning.
7. Add a first-class HTTPS transactions model and UI showing request URL/method/headers/body and response status/headers/body where decryption succeeds.
8. Store interception evidence separately from passive RAW PCAP with explicit provenance and transport/interception state.
9. Real-AVD acceptance must prove decrypted HTTP/1.1 and HTTP/2 request/response display end to end.
10. Detect certificate-pinning/custom-trust failures explicitly; do not claim universal HTTPS decryption until an enhanced interception tier is separately implemented and verified.
11. Evaluate HTTP/3/QUIC interception separately and record any forced fallback/downgrade as an intervention.
