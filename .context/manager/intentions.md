# Manager intentions and commitments

## Выполнено по последнему запросу владельца — v0.38.1 (поколение 39)

Все три задачи реализации выполнены и опубликованы. Никакого нового релиза для них не ожидается. Не следует утверждать, что пользователь уже проверил версию v0.38.1 на своём компьютере.

- **Текущая опубликованная версия: v0.38.1**, релиз опубликован 2026-10-14. Точный `main` SHA и release target `be63ad0e00894da424660cbb1a6da91ed69dd0ce`, PR #42 `fix/v0.38.1-modeless-replay-in-list` объединён. https://github.com/lvlaksim1/apk-research/releases/tag/v0.38.1
- **Основная сборка и публикация #38587459121 — SUCCESS**: Resolve changed areas, CI/test, Android 15 AVD, Desktop Windows build, clean Windows provisioning, Publish Release, Cleanup — все этапы завершились успешно. Отдельный Repository Storage Policy #38587459055 — SUCCESS.
- Отдельная WHPX проверка #38587459003 при последнем чтении имела состояние **queued**, результат неизвестен; не путать с успешной основной публикацией.
- Релиз содержит Setup `apk-research-setup_v0.38.1.exe` (47 585 439 байт, GitHub Release API SHA256 `4fdf3a762372adad0533f72468d014766af3e0d4e4db8a65639de84d8d959dc0`), https://github.com/lvlaksim1/apk-research/releases/download/v0.38.1/apk-research-setup_v0.38.1.exe; Update `apk-research-update_v0.38.1.exe` (47 585 819 байт, SHA256 `8509acf89aa4cd6ac4738377fb9605d3b0beb6d11fa61f1f9361822599b4c804`), https://github.com/lvlaksim1/apk-research/releases/download/v0.38.1/apk-research-update_v0.38.1.exe; `SHA256SUMS.txt` также опубликован. SHA берутся из метаданных GitHub Release, а не из скачанного локально установщика.
- **Требование 1 выполнено:** один клик `Отправить запрос` запускает изменённый HTTPS-запрос, дополнительный вопрос `Подтвердить отправку` удалён. Предварительная проверка URL, заголовков, тела и TLS **сохранена**. Запрос может изменить состояние сервера; автоматических повторов и переходов по перенаправлениям нет.
- **Требование 2 выполнено:** ручной повтор виден в том же списке HTTPS с `↻` и этапами `Выполняется`, затем код HTTP-ответа или `Ошибка`; доступен просмотр его метода, URL, заголовков и тела нового ответа, можно снова редактировать копию ручной строки. В `desktop/replay_records.py` результат и исходные байты ручной отправки представлены как `capture_mode=manual_replay` / `_inline_bytes`. Строки эфемерные: хранятся в памяти соответствующего окна, **не записываются в Research ZIP, исходный журнал и не сохраняются после перезапуска**. Архив остаётся неизменным. Отдельная сохранённая история ручных отправок не реализована и не запрашивалась.
- **Требование 3 выполнено:** редактор `ReplayDialog` теперь `NonModal`, открывается через `.show()` вместо `.exec()`. Можно взаимодействовать с основной таблицей, выбирать другие запросы и держать несколько редакторов открытыми. Окно с действующим запросом не закрывается до его завершения; сеть выполняется в рабочем потоке.
- Эти изменения касаются как текущей HTTPS-таблицы `LiveHttpsView`, так и просмотра сохранённого ZIP `HttpTransactionsWindow`. Не меняют исходные ZIP, raw PCAP, байты HTTPS и контрольные суммы. Реальное одновременное поведение на ПК владельца после установки v0.38.1 пока **не проверено пользовательским отчётом**.
- Сохранена v0.38.0: красивое форматирование JSON, редактор метода/URL/заголовков/тела JSON/HEX, ответ отдельно; неизменность исходных байтов до ручного редактирования; ограничение назначения исходным HTTPS-хостом/зафиксированным Host и портом; стандартная проверка TLS. Отправка производится с компьютера, не от имени Android, поэтому подписи/авторизация могут не сработать.
- Сохранены v0.37.1: страницы распакованного gzip/zlib-тела по 128 КиБ с защитным пределом 8 МиБ; v0.36.0: независимые HTTPS-анализ и запись ZIP, 18 кнопок эмулятора, фильтры HTTP-метода/домена, редактор данных справа; обновление по-прежнему в меню `Программа` → `Обновление и обслуживание…`. Новую вкладку `Настройки` **не создавать**, пользователь её отменил.
- Технические границы: TLS pinning/дополнительное доверие, QUIC/HTTP3/IPv6, собственный формат данных внутри zlib. Не угадывать содержимое или результат запросов. Не хранить реальные ZIP, cookies, токены и секреты в публичном репозитории.

---

## Исторические записи (предыдущие поколения; не использовать как текущие)

Выполнена и опубликована v0.38.0; нет согласованной незавершённой программной работы по этому запросу. Следующий шаг — проверить новую функцию в установленном приложении и выявлять только воспроизводимые отклонения. ## Действующее состояние — поколение 38, 2026-10-14

- **Опубликована v0.38.0**: main / release-tag commit `5dc804027a112cef6a4c697fbd2b167537fca470`, merged PR #41, GitHub Release https://github.com/lvlaksim1/apk-research/releases/tag/v0.38.0.
- Основной выпуск #38575479333 — **SUCCESS**: CI, Android 15 AVD, Windows GUI и сборка, обновление с v0.37.1, чистая установка/подготовка Windows, публикация и очистка. Проверенный PR-кандидат: CI #38574548724, Windows #38574548671 — SUCCESS.
- Published Update https://github.com/lvlaksim1/apk-research/releases/download/v0.38.0/apk-research-update_v0.38.0.exe, 47 568 524 bytes, GitHub Release digest SHA256 `29239f99cd959860bdf61ffe78529777ee21ec2b88807e556152ad83f769127f`.
- Published Setup https://github.com/lvlaksim1/apk-research/releases/download/v0.38.0/apk-research-setup_v0.38.0.exe, 47 568 148 bytes, GitHub Release digest SHA256 `2ea08d9aed39b6135307d4ec1637644366a77a5cfb08a194e85003d6fb3540b0`. SHA256SUMS.txt published.
- В v0.38.0 просмотр живых и архивных запросов/ответов автоматически форматирует целый корректный JSON с отступами (`body_display.py`); исходные сохранённые байты и HEX неизменны. В редакторе копии запроса JSON форматируется при открытии; во время ввода самопроизвольных изменений нет, доступна кнопка `Форматировать JSON`.
- Кнопка `Изменить и отправить…` в живой HTTPS-таблице и архивном просмотре открывает новый диалог с HTTP-методом, URL, заголовками, телом (текст/JSON или HEX). Пока пользователь не менял тело, повторно отправляются его оригинальные сохранённые байты; редактирование делает новое тело. Повтор — только после подтверждения, вручную, без автоповтора/перенаправлений.
- Запрос отправляется **с компьютера**, а не от имени Android-приложения. Разрешены только исходный HTTPS-сервер либо доверенный ему `Host`, записанный в исходной записи, исходный порт обязателен. Проверяется TLS-сертификат. Служебные заголовки (Host, Content-Length, Content-Encoding и др.) формируются/очищаются автоматически. 8 МиБ на тело запроса/ответа, отдельный рабочий поток, новый результат показывается в диалоге и **не записывается** в исходный ZIP или журнал.
- Серверные запросы могут иметь побочные эффекты или быть отвергнутыми из-за подписи, cookies, авторизации, адреса ПК либо требований Android-среды. Тесты не выполняли реальную повторную отправку на `ch.pala.resources`: проверялись подставным соединением. Нет пользовательского подтверждения воспроизведения реального запроса v0.38.0.
- Сохранены отдельные HTTPS-анализ/запись полного ZIP, 18 команд эмулятора, фильтры метода/домена, просмотр multipart/zlib/gzip по 128-КиБ фрагментам до 8 МиБ, исходная запись и целостность доказательств, обновление через меню `Программа`; **вкладку Настройки не добавлять** (явно отменена владельцем).
- Источники и контекст: продукт `main`; менеджер и капсула `context`. Содержимое реальных ZIP, cookies, токены и другие секреты не публиковать в GitHub.
- Дополнительный WHPX workflow #38575479268 был в очереди при проверке; его нельзя объявлять завершённым без повторной проверки. Успешную публикацию подтвердил основной выпуск #38575479333.


---

## История предыдущих поколений (состояния, заменённые выше)

## Выполнено — публикация v0.37.1

**Текущая опубликованная версия: v0.37.1** (2026-10-14), `main` и Release tag `41b3105aa4e2335a975eb6d126e61ed771e32b59`. Полный выпуск GitHub Actions #38553459909 завершился SUCCESS: CI, Android 15 AVD, Windows сборка, обновление с v0.37.0, чистая Windows и публикация.
- Выпуск: https://github.com/lvlaksim1/apk-research/releases/tag/v0.37.1
- Обновление: https://github.com/lvlaksim1/apk-research/releases/download/v0.37.1/apk-research-update_v0.37.1.exe (47 549 287 байт; SHA256 `32203fd8ec1777f6b1ca29c6d02fcf5463d77022bc0f95867343c17a33654dda` — значение GitHub Release API).
- Полный установщик: https://github.com/lvlaksim1/apk-research/releases/download/v0.37.1/apk-research-setup_v0.37.1.exe (47 548 907 байт; SHA256 `11f984a40e7f3dbb9a7b8d46cba335ea3eb75c277c58ad77fcf25c03efb03125`).
- Причина обновления: в v0.37.0 корректный ответ application/zlib с исходным телом 49 433 байта вызывал `Ошибка распаковки вложенного zlib: Размер распакованных данных превышает 128 КиБ`. Предел 128 КиБ ошибочно применялся к полной распаковке вместо видимого фрагмента, выводя HEX и скрывая доступный распакованный текст.
- Исправление: `desktop/body_display.py` разделяет размер выводимого фрагмента 128 КиБ и безопасный предел распаковки 8 МиБ. Читаемые ответы отображаются по фрагментам 1–64 в режиме «Текст (авто)», выбор фрагмента добавлен в живой просмотр и сохранённые ZIP. Превышение 8 МиБ показывает доступное начало и предупреждает, что полная целостность потока не подтверждена, без ложной ошибки сервера. `HEX` и все оригинальные сохранённые байты не меняются. Неподтверждённые бинарные форматы не объявляются текстом.
- PR #40 объединён; кандидат прошёл CI #38552638511 и Windows #38552638799, затем основной цикл #38553459909. Ранее PR #39 выпустил v0.37.0, PR #38 — независимый HTTPS/ZIP интерфейс v0.36.0.
- **Открытая проверка владельцем:** установить v0.37.1 и попробовать исходный ответ `ch.pala.resources` (49 433 байта): определится ли текст после zlib или остаётся собственный двоичный формат. Конкретный результат этого ответа на ПК владельца пока неизвестен. Нет открытого препятствия для релиза.
- Все ранее согласованные элементы сохранены: один HTTPS-анализатор с отдельной записью ZIP, 18 кнопок эмулятора, фильтры метода/домена, обновление в меню «Программа» и **отсутствие** вкладки «Настройки» по отказу владельца. Research ZIP, тела, токены и прочие приватные данные нельзя размещать в публичном GitHub.

Следующее действие — только проверка фактического `ch.pala.resources` владельцем или новая согласованная задача.

---

## Предыдущие поколения (история)

## Completed owner-directed v0.37.0 delivery

- Version **v0.37.0** is PUBLISHED, release target/main SHA `aa2cb71ab637c203810174a521e62aa1cf05c5df`, published 2026-10-14, https://github.com/lvlaksim1/apk-research/releases/tag/v0.37.0.
- Full main GitHub Actions run #38539863949 **SUCCESS**, including CI, Android 15 AVD, Windows build, v0.36-to-v0.37 Update, clean Windows provisioning, publishing and cleanup.
- PR #39 implemented a **display-only** HTTP-body reader. No changes to source PCAP, HTTPS body bytes, collectors, packet routing, Research ZIP format, or checksums.
- `desktop/body_display.py` renders `multipart/form-data` by MIME fields (also accepts real-world `, boundary=` headers); formats text and JSON; inflates gzip/zlib only if saved byte signatures confirm compression. The HTTPS recorder's `get_content(strict=False)` may already decompress the HTTP layer, so no redundant decompression from `Content-Encoding: gzip` alone.
- `Текст (авто)` is default; `HEX` shows **original saved bytes**. Works in live `LiveHttpsView` and ZIP viewers, including `HttpTransactionsWindow`. Max raw preview 128 KiB, max decompressed 128 KiB, HEX 4096 bytes; malformed/unknown data remains binary with explanatory message.
- Unit tests include 0x78da zlib with Content-Encoding gzip, multipart/form-data with comma-boundary, gzip, JSON, binary, damaged/truncated/zip-bomb data and original HEX. Windows GUI tests include switching modes in both live and archive. All release gates passed.
- SHA256 (GitHub Release asset digest) Setup: `5c83dddc5a18dd2cc180bfc53048801eee7b34eb694fce1e7ef9545491556eeb`; Update: `dfa8b7854c50408a188d3376af3d5daa60809c1b90f50392a084984820fcf6c4`. Setup https://github.com/lvlaksim1/apk-research/releases/download/v0.37.0/apk-research-setup_v0.37.0.exe; Update https://github.com/lvlaksim1/apk-research/releases/download/v0.37.0/apk-research-update_v0.37.0.exe. `SHA256SUMS.txt` published.
- Prior owner v0.36 report was generally working. NEW v0.37 behavior on `ch.pala.resources` still needs owner field acceptance: actual sample may contain an undocumented binary format after zlib. Never fabricate decoded fields or guarantee readable content.
- Preserve owner-approved v0.36 workflow, separate HTTPS analysis and ZIP start/stop, 18 toolbar controls, filters by method/domain, updater under the Program menu. No new Settings tab (explicitly cancelled).

**Active**: owner acceptance on actual HTTPS requests, especially request multipart fields and response `application/zlib`. No unpublished release blocker or authorized new coding task.

---

## Исторический контекст предыдущих поколений

## Completed delivery: owner-approved v0.36.0

- Product: published **v0.36.0**, main/Release commit `5f66b1940acd6b867d569d8a62faae4c338bde4f`; PR #38 merged.
- Final main GitHub Actions #38439063318 **SUCCESS**: CI, Android 15, Windows build, clean Windows provisioning, publish and cleanup. PR final tests CI #38438091809, Windows #38438091746, Android #38438092086, ARM64 #38438091891 all passed.
- Release https://github.com/lvlaksim1/apk-research/releases/tag/v0.36.0; Setup https://github.com/lvlaksim1/apk-research/releases/download/v0.36.0/apk-research-setup_v0.36.0.exe; Update https://github.com/lvlaksim1/apk-research/releases/download/v0.36.0/apk-research-update_v0.36.0.exe; `SHA256SUMS.txt` published.
- Owner cancelled new `Настройки` tab; updater remains under `Программа` → `Обновление и обслуживание…`.
- Left workflow: prepare Android → select APK/XAPK → install → choose installed app, start/stop HTTPS analysis → separate ZIP start/stop → open ZIP folder.
- HTTPS analysis is started **before** automatic app launch; no ZIP is generated until the user starts recording. A single HTTPS analyzer/route persists during ZIP; the ZIP captures HTTPS and other materials for its bounded recording interval. Stopping ZIP does not stop HTTPS analysis or relaunch the app.
- One main Research tab with Android + right-side HTTPS list and request details; all 18 emulator actions placed on slim strip (scroll when necessary); Method and Address headers filter by HTTP method/domain with multi-select/search; other headers sort.
- No hands-on owner confirmation yet for installed v0.36.0. Android 15 status-bar overlap on actual owner's app not independently verified. Never invent per-app success; private Research ZIP and its tokens must not be made public.
- Separate post-merge WHPX #38439063246 was queued when inspected on 2026-10-14; no assertion of success. It is not a failed gate of the fully successful main publication.

**Active:** obtain owner field feedback or new explicit task. No unfinished v0.36 release work; all older active v0.35/pending release notes below are archived.

---

## Archived previous-generation notes — superseded where inconsistent

## Completed — v0.30.0 HTTPS traffic display
Status: completed and released.

Owner requirement: display actual decrypted HTTPS application traffic in apk-research, not only TLS/QUIC metadata.

Delivered:
- application-managed local HTTPS proxy bundled with the Windows application;
- automatic managed-emulator routing through `adb reverse`;
- temporary trusted research CA for the rooted Android 15 environment;
- HTTP transaction evidence in Research ZIP;
- request/response headers and bodies where decryption succeeds;
- dedicated HTTP/HTTPS viewer with search and readable bodies;
- explicit provenance preserving the distinction from passive RAW PCAP;
- real Android 15 acceptance proving `https://example.com/` with status 200 and non-empty response body;
- successful v0.29.2 → v0.30.0 dedicated update verification.

Completion evidence: PR #26 merged; main pipeline #143 passed mandatory CI, real AVD, Windows build/update/install and release gates; GitHub Release v0.30.0 published.

Known bounded limitations:
- certificate pinning or application-owned trust stores may reject the research CA;
- HTTP/3/QUIC content decryption is not claimed.

## Completed — v0.29.2 MailRu-style installer model
Status: completed and preserved in v0.30.0.

Separate Setup and Update installers, Update-only discovery, SHA-256 verification, direct Windows-shell launch and Inno-owned shortcut refresh remain the release architecture.

## Cancelled — Android home-screen shortcut after APK/XAPK install
Status: cancelled by owner on 2026-10-08.

Do not resume this work unless explicitly reopened.

## Active — continuity and release integrity
Status: active.

Reconcile live product/release/CI before consequential changes and preserve all verified evidence/runtime boundaries.

## Active — HTTPS traffic of applications that bypass the Android system proxy

Status: **generic routing implemented/released in v0.32.0; owner-specific application verification pending**.

Following the owner archive analysis on 2026-10-08, the owner directed the manager to implement automatic handling/routing of HTTPS traffic emitted by target Android applications that do not use the system proxy, beginning with `com.evrasia`.

Acceptance objective: in a controlled research session, applicable target HTTPS requests and responses should be available in the desktop HTTP/HTTPS viewer and Research ZIP where the technical trust and protocol conditions allow. Preserve independent RAW PCAP provenance, explicit session routing diagnostics, previous installation/update behavior and the known restrictions from v0.30.0.

Next action: re-read the supplied archive (if accessible) and relevant code, establish a narrow viable routing design, implement on a dedicated branch, verify on real Android 15 AVD and affected APK, then deliver via the accepted Setup/Update release process after required acceptance gates. Do not mark this commitment complete merely because the v0.30.0 generic HTTPS test passed.

- source: Owner instruction following analysis of `20261008T020126.928669Z-e336ad57.research.zip`.

## Completed — v0.31.0 ARM64-only APK/XAPK support

Status: **completed and released 2026-10-10**. Owner required support for ARM64-only XAPK rejected by original x86_64-only AVD. Delivered automatic package ABI preflight, separate official Android 15 Google APIs x86_64 image with native ARM translation, original AVD/userdata isolation, root/gRPC/MMAP/ABI validation, and normal XAPK split/OBB handling. Acceptance proved actual ARM64 JNI library execution in an Android 15 test XAPK (`ARM64_NATIVE_LOADED: PASS`), legacy AVD and Windows acceptance, main pipeline #144 attempt 2 and published v0.31.0 assets tied to main `5aab54adc807aff401b59d4c1018795246303b89`.

Owner's actual rejected XAPK still needs field validation. The separate owner HTTPS routing commitment remains ACTIVE.

## Completed — v0.32.0 direct TCP/443 routing to HTTPS analyzer

Owner's 2026-10-10 request was implemented and published. PR #30, main `a2f0bbbca364714d37f7697ffa5ccb8204bc94b1`, pipeline #145 attempt 1 success. A separate Android-local module uses Android's true package UID and original destination to direct only selected-app IPv4 TCP/443 data to the existing HTTPS analyzer; archived route diagnostics and verified cleanup are part of the session. Android 15 live acceptance required both system-proxy and `Proxy.NO_PROXY` HTTPS with nonempty HTTP 200 response bodies (577 bytes each). Windows build, prior-release update and clean provisioning passed. Published Setup and Update assets are available for v0.32.0.

## Active — owner-specific `com.evrasia` verification

The original owner Research ZIP `20261008T020126.928669Z-e336ad57.research.zip` previously showed direct TLS connections and zero readable HTTP records under v0.30.0. User must test their actual APK using published v0.32.0; inspect newly generated `02_normalized/http-transactions.jsonl`, `01_raw/network/https-direct-route.log`, and `02_normalized/http-interception.json`. Do not claim success of this specific APK without real new evidence. App-specific TLS trust and QUIC restrictions remain.

## Completed — com.evrasia field validation on v0.32.0

Status: **completed and proven by the owner's uploaded v0.32.0 session archive on 2026-10-10**.

The user's actual com.evrasia app produced 32 readable HTTP/HTTPS responses (23 on evrasia.spb.ru), with 21 direct target TCP/443 route entries and confirmed cleanup. Session complete with 99/99 archive checksum matches. The former zero-HTTP-transaction problem is solved for the tested session. Do not conflate this with universal TLS compatibility.

Private evidence: owner Research ZIP 20261010T021552.574206Z-3e8e2043.research.zip, NOT to be stored publicly. Its JSON responses include authentication credential fields. No credential values should be entered into any project report, commit, issue or release.

## Observation only — capture completeness and attribution

tcpdump reported 615 kernel-dropped packets out of a session with 22,525 captured packets; flow inventory 93, of which 73 have UNKNOWN ownership attribution. The user has not separately authorized changes to these subsystems; first propose measurable, scoped improvements if requested.

## Completed — simplified Research + live HTTPS user interface (v0.33.0)

Owner requested to remove the other complicated result/analysis tabs and focus on maximum Research ZIP completeness plus live HTTPS requests for the studied application. Implemented only two visible tabs via actual Windows entrypoint, one-click HTTPS access and counter, automatic JSONL updating every 500 ms and completed ZIP viewing; removed technical UI navigation but retained all collectors and data, updater and maintenance in Program menu. Full-length RAW PCAP capture buffer raised to 16 MiB, with no unsupported guarantee of zero packet drops. PR #31, main `3f3f1144e0ea8944a065e7d5950fd07fd1e17abf`, pipeline #146 attempt 1 SUCCESS; versioned standalone setup and update installers released.

## ACTIVE — deliver tested v0.34.0 panel + network ZIP extensions

Source implemented in draft PR #32; v0.34.0 is not yet published. Required remaining steps: latest exact candidate SHA 8c1dbcc full Windows GUI/build/setup/update, Android AVD ZIP verification, full CI. Only then merge to main and wait for main release pipeline to publish two verified installers. Record user-requested UI shape and neutral HTTPS terminology.

## Completed — v0.34.0 emulator controls and expanded ZIP (reconciled 2026-10-13)

Status: **published and passed all required release checks**, exact main `2efec386cff0b204ee56d8bee365f3c52caefcb5`. Owner approved a conventional right-side emulator control strip and greater network/session evidence without restoring the technical navigation tabs. Implemented through PR #32, not unmerged/closed PR #33. Retain two user tabs, RAW PCAP, HTTPS request/response bodies, independent screen recording, ARM64 APK/XAPK, installed Android data and dedicated Windows Update installer. Six normalized JSON/JSONL evidence files are supplied; data provenance remains explicit.

Owner has not yet provided post-release field acceptance. Next work is practical v0.34.0 usage validation; any new task or bug fix should be scoped from observed behavior. Owner explicitly chose not to release speculative Android network recovery because reboot resolved that transient issue.


## ACTIVE — v0.35 UI delivery, 2026-10-13

13 October 2026: Owner explicitly directed integrated HTTPS list/details to the right of the Android view, click sorting, a non-obscuring Android status line, and immediate right-side emulator controls. Active PR #35, branch feature/v0.35-unified-https-workspace, final candidate 51050663f68516ce0dddec6dfe157f8a931fcab9, version 0.35.0. CI, real Android 15 AVD and ARM64 tests passed. Windows desktop build passed; clean Windows provisioning is in progress. Product main/latest release still 0.34.0 until full verification/merge/main pipeline. The app-specific Android 15 enforced edge-to-edge opt-out is a best-effort compatibility command, recorded in session events; owner app screenshot must confirm visual effect. Do not claim field acceptance without evidence.


## ACTIVE — main v0.35 release publication and owner field check

On 2026-10-13, PR #35 was merged into product main by verified merge commit 2076cb8c2fa4d5fead39e2b4edb5829fab8e4cbd after final PR CI, real AVD, ARM64, Windows build, previous-version Update and clean provisioning all succeeded. main now contains 0.35.0 source. GitHub Release v0.35.0 remains NOT YET PUBLISHED pending main workflow run 38416539695. Within that run CI, Windows build, actual 0.34.0 to 0.35.0 Update and clean Windows provisioning passed; main AVD test is still installing Google Android SDK components at this checkpoint. Continue monitoring the exact main run and retry its failed mandatory gates if SDK distribution fails; NEVER bypass AVD or claim release prematurely. Confirm published version, commit and SHA256 assets before terminalizing work. Android insets per-app effect needs a user screenshot.
