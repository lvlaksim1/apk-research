# Current Blockers and Unknowns

Status as of 2026-10-14, manager generation 35; verified published v0.36.0 main `5f66b1940acd6b867d569d8a62faae4c338bde4f`.

**No open v0.36.0 release blocker:** successful main pipeline #38439063318 and published Setup, Update and SHA256SUMS. Older v0.35 and intermediate candidate issues are historical.

**Pending field verification:** owner has not yet tested v0.36.0 in this conversation. Confirm independent HTTPS without ZIP, app autostart after analyzer readiness, ZIP start/stop without interrupting analysis, persisted settings, filter behavior, all 18 emulator controls, and full ZIP contents. Android status-bar visual appearance on actual target still requires screenshot.

**Unverified separate workflow:** WHPX #38439063246 was queued at inspection; do not claim success. This is distinct from published main release pipeline.

**Known technical scope:** app-specific TLS pinning/custom trust, QUIC/UDP443, IPv6, missing DNS/TLS metadata, packet drops and incomplete attribution must be measured from actual captures. Earlier com.evrasia restart resolved a loading incident without proven root cause; no speculative recovery code was shipped. No new Settings tab (explicitly cancelled), no unsafe public upload of research archives or credentials.
