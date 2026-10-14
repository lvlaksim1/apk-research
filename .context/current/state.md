# Current Project State

Last reconciled: **2026-10-14**. Sealed manager generation **35**. This replaces all older v0.34/v0.35 current-state snapshots.

## Authority and release

- Product: published **v0.36.0**, main/Release commit `5f66b1940acd6b867d569d8a62faae4c338bde4f`; PR #38 merged.
- Final main GitHub Actions #38439063318 **SUCCESS**: CI, Android 15, Windows build, clean Windows provisioning, publish and cleanup. PR final tests CI #38438091809, Windows #38438091746, Android #38438092086, ARM64 #38438091891 all passed.
- Release https://github.com/lvlaksim1/apk-research/releases/tag/v0.36.0; Setup https://github.com/lvlaksim1/apk-research/releases/download/v0.36.0/apk-research-setup_v0.36.0.exe; Update https://github.com/lvlaksim1/apk-research/releases/download/v0.36.0/apk-research-update_v0.36.0.exe; `SHA256SUMS.txt` published.
- Owner cancelled new `Настройки` tab; updater remains under `Программа` → `Обновление и обслуживание…`.
- Left workflow: prepare Android → select APK/XAPK → install → choose installed app, start/stop HTTPS analysis → separate ZIP start/stop → open ZIP folder.
- HTTPS analysis is started **before** automatic app launch; no ZIP is generated until the user starts recording. A single HTTPS analyzer/route persists during ZIP; the ZIP captures HTTPS and other materials for its bounded recording interval. Stopping ZIP does not stop HTTPS analysis or relaunch the app.
- One main Research tab with Android + right-side HTTPS list and request details; all 18 emulator actions placed on slim strip (scroll when necessary); Method and Address headers filter by HTTP method/domain with multi-select/search; other headers sort.
- No hands-on owner confirmation yet for installed v0.36.0. Android 15 status-bar overlap on actual owner's app not independently verified. Never invent per-app success; private Research ZIP and its tokens must not be made public.
- Separate post-merge WHPX #38439063246 was queued when inspected on 2026-10-14; no assertion of success. It is not a failed gate of the fully successful main publication.

## Verified assets and digests

- `apk-research-setup_v0.36.0.exe` 47,545,075 bytes, GitHub Release asset SHA256 `f471c13f2efd72f6f7f3eac6d273cb84f43505c81f8ed9e2bcb34f127cd706b8`.
- `apk-research-update_v0.36.0.exe` 47,545,451 bytes, GitHub Release asset SHA256 `0965e99d22e91a1005fca80d3d7dbf3b4618adf274b29272e741162d205df1f5`.
- `SHA256SUMS.txt` published. These hashes come from GitHub Release API digest metadata, not a separately downloaded local binary.
- Product source authority: `main`; manager-state authority: `context`. Product changes must not be made by editing `context`.

## Historical correction and boundaries

The prior generation 34 falsely remained on the superseded v0.35 release-pending checkpoint. v0.35.0 was published, then PR #38 delivered the approved redesign, and v0.36.0 was fully published. A candidate Android baseline acceptance initially reported empty flow inventory after an extra independent HTTPS scenario; tests were reordered and final exact candidate acceptance succeeded. No such interim failure is a current release blocker. Separate WHPX #38439063246 was queued at last inspection, without a success claim.

RAW PCAP, HTTPS request/response contents, recording, video, logs, checksums and ARM64/XAPK remain supported. Decryption has specific rooted Android IPv4 TCP/443, certificate trust, QUIC/IPv6 and app-dependent limits. A field ZIP may include sensitive data and must never be committed to public GitHub.
