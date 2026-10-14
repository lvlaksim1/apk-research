# Current Project State

**Sealed generation 36 — 2026-10-14**. Published product authority main SHA `aa2cb71ab637c203810174a521e62aa1cf05c5df`; latest release **v0.37.0**, https://github.com/lvlaksim1/apk-research/releases/tag/v0.37.0. PR #39 merged.

- Version **v0.37.0** is PUBLISHED, release target/main SHA `aa2cb71ab637c203810174a521e62aa1cf05c5df`, published 2026-10-14, https://github.com/lvlaksim1/apk-research/releases/tag/v0.37.0.
- Full main GitHub Actions run #38539863949 **SUCCESS**, including CI, Android 15 AVD, Windows build, v0.36-to-v0.37 Update, clean Windows provisioning, publishing and cleanup.
- PR #39 implemented a **display-only** HTTP-body reader. No changes to source PCAP, HTTPS body bytes, collectors, packet routing, Research ZIP format, or checksums.
- `desktop/body_display.py` renders `multipart/form-data` by MIME fields (also accepts real-world `, boundary=` headers); formats text and JSON; inflates gzip/zlib only if saved byte signatures confirm compression. The HTTPS recorder's `get_content(strict=False)` may already decompress the HTTP layer, so no redundant decompression from `Content-Encoding: gzip` alone.
- `Текст (авто)` is default; `HEX` shows **original saved bytes**. Works in live `LiveHttpsView` and ZIP viewers, including `HttpTransactionsWindow`. Max raw preview 128 KiB, max decompressed 128 KiB, HEX 4096 bytes; malformed/unknown data remains binary with explanatory message.
- Unit tests include 0x78da zlib with Content-Encoding gzip, multipart/form-data with comma-boundary, gzip, JSON, binary, damaged/truncated/zip-bomb data and original HEX. Windows GUI tests include switching modes in both live and archive. All release gates passed.
- SHA256 (GitHub Release asset digest) Setup: `5c83dddc5a18dd2cc180bfc53048801eee7b34eb694fce1e7ef9545491556eeb`; Update: `dfa8b7854c50408a188d3376af3d5daa60809c1b90f50392a084984820fcf6c4`. Setup https://github.com/lvlaksim1/apk-research/releases/download/v0.37.0/apk-research-setup_v0.37.0.exe; Update https://github.com/lvlaksim1/apk-research/releases/download/v0.37.0/apk-research-update_v0.37.0.exe. `SHA256SUMS.txt` published.
- Prior owner v0.36 report was generally working. NEW v0.37 behavior on `ch.pala.resources` still needs owner field acceptance: actual sample may contain an undocumented binary format after zlib. Never fabricate decoded fields or guarantee readable content.
- Preserve owner-approved v0.36 workflow, separate HTTPS analysis and ZIP start/stop, 18 toolbar controls, filters by method/domain, updater under the Program menu. No new Settings tab (explicitly cancelled).

**Status:** no development or release blocker. Owner testing on the concrete observed `ch.pala.resources` 664-byte multipart and 1190-byte zlib response is outstanding. A general gzip/zlib decoder cannot guarantee that decompressed bytes are ordinary text; retain original HEX for accurate diagnostics.

**Authority:** manager `context` and product `main` are separate. Older generation35/v0.36-as-latest notes are archived in manager historical documents.
