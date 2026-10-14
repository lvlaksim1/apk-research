# Semantic Memory

## Proven runtime architecture

The reliable Windows runtime is hidden Emulator → gRPC/MMAP framebuffer → AndroidView with gRPC input; v0.10.5 is the startup/clean-launch sequencing baseline.

- source: apk-research release history and repository documentation through v0.17.0
- authority: verified-repository

## QUIC false-positive lesson

v0.16.0 showed that arbitrary DNS UDP payload bytes can resemble QUIC long headers. v0.16.1 changed the classifier so a supported QUIC v1/v2 flow is established only from authenticated/decrypted Initial evidence, and the observed real DNS prefixes became regressions.

- source: owner-provided real Research ZIP plus v0.16.1 repository fix/tests
- authority: verified-project-evidence

## Unified Evidence Explorer boundary

v0.17.0 Unified Evidence Explorer is presentation-only. It navigates existing Timeline, normalized flows, socket attribution and raw locators; it does not create a new forensic source of truth or upgrade temporal correlation into causality.

- source: v0.17.0 repository implementation and release notes
- authority: verified-repository

## 2026-10-14 — Mail.ru Android authorization fails during live HTTPS analysis (diagnosed, not fixed)

- Evidence: owner-provided private Research ZIP `20261014T154140.312362Z-81d7ef81.research.zip`, captured by apk-research **v0.38.0**, target `ru.mail.mailapp` on Android 15. **Do not commit the private ZIP or credentials.** Session completed, 9,383 packets captured, kernel drops 0.
- `logcat` at 15:41:45–15:41:47 UTC: DNS probes successful, plain HTTP probes to connectivitycheck.gstatic.com and play.googleapis.com returned 204, **HTTPS network validation failed** with `SSLHandshakeException: CertPathValidatorException: Trust anchor for certification path not found`; Android marked Wi-Fi as `isPartialConnectivity=true` and `validation failed`.
- Following Mail.ru `AUTH_START`, packet evidence shows several `CONNECT api.vk.ru:443` through local analyzer `127.0.0.1:38887`, proxy returned `HTTP/1.1 200 Connection established`, TLS ClientHello/ServerHello occurred and client closed the TLS connections immediately after receiving server flight. No HTTP request body from those HTTPS connections was decoded. VK SDK emitted `Loading error. Please check your internet connection and try again`. This supports failure of the HTTPS path, **not** proof that Mail.ru has certificate pinning specifically; Android's system validation failure is directly proven.
- `http-interception.json` reported CA injection succeeded, but this is not an application/process trust verification. Only two recorded HTTP transactions were cleartext connectivity probes; zero application HTTPS transactions were decoded. `direct_route_cleanup_confirmed=false` was observed with `stopped_utc=null` while the shared live analyzer remained running; do not classify that datum alone as failed cleanup.
- The product's current collector `src/apk_research/collectors/https_interception.py` sets Android **global** `settings put global http_proxy 127.0.0.1:38887` even though direct TCP/443 route is UID-scoped; this exposes system connectivity probes to the analysis CA and contradicts interpreting `other_android_apps_unmodified` as complete network isolation. This is verified source behavior; causality to the observed HTTPS probe failure is strongly supported, not yet corrected.
- Next diagnostic step: test Mail.ru authorization with HTTPS analyzer fully stopped and route/proxy restored, then with analysis enabled. For remediation, distinguish system-wide proxy contamination from target app CA/custom trust/pinning; prefer target-only routing and preserve functional authentication via justified per-host TLS passthrough (with no claimed decrypted bodies) when necessary. Do not disable certificate validation globally or invent decrypted evidence. No implementation/change/release has been authorized in this diagnostic exchange.

- source: private owner-supplied Research ZIP inspected 2026-10-14 and verified main source at `be63ad0e00894da424660cbb1a6da91ed69dd0ce`
- authority: owner evidence plus inspected repository source; hypotheses explicitly qualified

## 2026-10-14 — Retained Android global proxy after HTTPS analysis stop (verified defect, not fixed)

- Owner field test reports **the same Mail.ru “no internet” authentication error with network analysis turned off**. This supersedes the earlier assumption that the error requires an actively running HTTPS analyzer. No off-mode Research ZIP or new log has yet been captured, so identical root cause of the app error is not independently proven.
- Concrete archive evidence: private v0.38.0 Research ZIP `20261014T154140.312362Z-81d7ef81.research.zip`, `02_normalized/http-interception.json`, records `previous_android_proxy: "127.0.0.1:38887"`, exactly equal to `device_proxy`. Thus the **global Android proxy was already set to the application's own analyzer address before that analyzer's start at 15:40:11 UTC**; this is positive evidence of a stale or pre-existing setting, not an inference that the recording caused it.
- Verified main code at `be63ad0e00894da424660cbb1a6da91ed69dd0ce`: `HttpsInterceptionCollector._configure_proxy` saves whatever is in `settings get global http_proxy` into `_previous_proxy`, then writes `127.0.0.1:38887`. On stop, `_cleanup_device_best_effort` blindly restores `_previous_proxy` even if identical to its own address, and removes the ADB reverse mapping. **When the recorded pre-existing value is identical to the analyzer address, a normal stop therefore leaves a now-dead proxy address configured**. This is a reproducible logic defect that can cause the network failure to persist when analysis is turned off.
- Next safe diagnostic: after the analyzer has fully stopped, read `adb shell settings get global http_proxy`; if it reads `127.0.0.1:38887`, reset it to `:0` and verify again. Also verify the routing chain is removed; repeat Mail.ru authentication. A clean per-app route design and explicit proxy-state restore verification are candidate product corrections, but no code/release was authorized by this owner observation alone.
- Do not claim the Mail.ru app's TLS behavior is resolved until a new off/on controlled test confirms it. Do not commit user-supplied private ZIP, account information, or credentials.

- provenance: owner follow-up statement (2026-10-14), private Research ZIP metadata, GitHub collector implementation verified 2026-10-14
- authority: verified source logic plus owner field observation; root cause of remaining Mail.ru error still under test

## 2026-10-14 — v0.38.2 Android network recovery fix merged (release pipeline pending at time of record)

- Supersedes both preceding "not fixed" diagnostic sections as to **implementation status**, but does NOT prove Mail.ru login now succeeds on the owner's computer.
- Owner requested direct implementation without further manual experiments. PR #43 `fix/v0.38.2-android-network-recovery` merged to product `main`, commit `ce09a1ec1a0086ad797c667a2d2ca59351747708`. Changes: normalize stale `127.0.0.1:38887` proxy when starting, verified proxy cleanup on stop, selective stale route/proxy/ADB reverse restoration from "Подготовить Android" and new "Восстановить сеть Android" button, preserve unrelated proxy, report cleanup failure.
- PR verification on head `34c71b4c67ecf1ad31c233a49b2cbf547e7efb9f`: core CI #38601002524, Android AVD #38601002729, ARM64 #38601003020, Windows build/provisioning/setup/update #38601002938 and storage #38601002895 all **success**.
- Main release workflow #38602120990 was **in progress** at record time; do not claim v0.38.2 published without checking its final result and GitHub Release artifacts. Secondary WHPX may remain queued and is non-gating.
- The fix addresses the proven stale proxy defect; independent TLS app trust/pinning has not been modified. Keep the prior private Research ZIP out of the repository.
- provenance: GitHub PR/Actions/main commit verified during user-directed implementation 2026-10-14
- authority: verified product repository / CI; owner field acceptance still pending

