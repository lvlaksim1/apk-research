# Latest Handoff

Generation: **35**
Date: 2026-10-14
Manager: apk-research-project-manager
Product authority: `main`
Manager-state authority: `context`

## Current verified checkpoint

- Product: published **v0.36.0**, main/Release commit `5f66b1940acd6b867d569d8a62faae4c338bde4f`; PR #38 merged.
- Final main GitHub Actions #38439063318 **SUCCESS**: CI, Android 15, Windows build, clean Windows provisioning, publish and cleanup. PR final tests CI #38438091809, Windows #38438091746, Android #38438092086, ARM64 #38438091891 all passed.
- Release https://github.com/lvlaksim1/apk-research/releases/tag/v0.36.0; Setup https://github.com/lvlaksim1/apk-research/releases/download/v0.36.0/apk-research-setup_v0.36.0.exe; Update https://github.com/lvlaksim1/apk-research/releases/download/v0.36.0/apk-research-update_v0.36.0.exe; `SHA256SUMS.txt` published.
- Owner cancelled new `Настройки` tab; updater remains under `Программа` → `Обновление и обслуживание…`.
- Left workflow: prepare Android → select APK/XAPK → install → choose installed app, start/stop HTTPS analysis → separate ZIP start/stop → open ZIP folder.
- HTTPS analysis is started **before** automatic app launch; no ZIP is generated until the user starts recording. A single HTTPS analyzer/route persists during ZIP; the ZIP captures HTTPS and other materials for its bounded recording interval. Stopping ZIP does not stop HTTPS analysis or relaunch the app.
- One main Research tab with Android + right-side HTTPS list and request details; all 18 emulator actions placed on slim strip (scroll when necessary); Method and Address headers filter by HTTP method/domain with multi-select/search; other headers sort.
- No hands-on owner confirmation yet for installed v0.36.0. Android 15 status-bar overlap on actual owner's app not independently verified. Never invent per-app success; private Research ZIP and its tokens must not be made public.
- Separate post-merge WHPX #38439063246 was queued when inspected on 2026-10-14; no assertion of success. It is not a failed gate of the fully successful main publication.

## Downloads and published SHA256

- Setup: https://github.com/lvlaksim1/apk-research/releases/download/v0.36.0/apk-research-setup_v0.36.0.exe — `f471c13f2efd72f6f7f3eac6d273cb84f43505c81f8ed9e2bcb34f127cd706b8`.
- Update: https://github.com/lvlaksim1/apk-research/releases/download/v0.36.0/apk-research-update_v0.36.0.exe — `0965e99d22e91a1005fca80d3d7dbf3b4618adf274b29272e741162d205df1f5`.
- Checksums at https://github.com/lvlaksim1/apk-research/releases/tag/v0.36.0; main pipeline https://github.com/lvlaksim1/apk-research/actions/runs/38439063318 verified SUCCESS. Hashes from GitHub asset digest.

## Continuation

No release blocker and no user field acceptance for installed v0.36.0 yet. Ask for observed behavior of the six-button workflow, continuous HTTPS during/after ZIP recording, live table filters and right emulator toolbar, plus app screenshot for Android system bar. New developer work only after specific owner scope. Maintain single HTTPS analyzer, bounded ZIP, confidential evidence, previous user cancellation of Settings tab and mandatory gates. v0.35 release-pending notes and prior v0.34/current assumptions are obsolete.