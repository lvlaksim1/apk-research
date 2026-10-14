# Current Blockers and Unknowns

2026-10-14 generation36. v0.37.0 published, main workflow #38539863949 passed. **No release blockers.**

- Owner v0.37 hands-on acceptance for actual `ch.pala.resources` data remains unverified; without the saved body cannot know whether zlib yields JSON or proprietary binary.
- Compact UI text preview is intentionally limited to 128KiB; HEX view to 4096 bytes, underlying body stored unchanged.
- Format guessing beyond confirmed gzip/zlib/multipart is prohibited.
- Previous Android status bar on owner's third-party APK remains a per-app field question, not a proven current defect.
- TLS custom trust, pinned certificates, QUIC/HTTP3 and non-IPv4 paths remain outside guaranteed read scope.
- No Settings tab; privacy and no public research ZIP/credentials remain mandatory.
