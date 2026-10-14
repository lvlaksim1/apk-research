# Manager plans

## План после выпуска v0.38.1 (2026-10-14; поколение 39)

1. При восстановлении менеджера сверить печать целостности поколения 39 в `context`, свежие `main`, latest Release и основные CI-гейты.
2. Предложить обновление v0.38.1 владельцу и получить полевую приёмку: однократная отправка без второй формы подтверждения, появление ↻-строки, изменение её статуса/ответа, возможность свободно переключать основное окно при открытом редакторе и несколько редакторов одновременно.
3. Убедиться, что архив после ручной отправки остался побайтно прежним, что ручная строка не переживает закрытие сеанса, и что исходная сохранённая запись не перезаписывается.
4. При сбое получить конкретный воспроизводимый пример, лог/скриншот (без токенов), отделить ограничение TLS/подписи/сетевого адреса от дефекта UI.
5. Для будущих согласованных обновлений — рабочая ветка от текущего `main`, автоматические и Windows GUI/обновление/чистая установка + Android 15 тесты, публикация лишь после успеха pipeline, затем пересохранение капсулы.
6. Отдельную проверку WHPX #38587459003 повторно уточнять при необходимости: при последней проверке её результат не получен.

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

1. В новом чате проверить sealed `context` generation 38 и фактический main/release.
2. Дать ссылку на обновление v0.38.0, запросить проверку форматирования компактных JSON, редактора и нового ответа на безвредном запросе к разрешённому серверу.
3. Перед повторной отправкой предупредить о побочных эффектах POST/PATCH/DELETE; учитывать различие ПК и Android-авторизации. Исходные запросы с токенами не публиковать.
4. По дефекту сначала получить симптомы, провести воспроизведение, согласовать изменение; CI, Android 15, Windows UI/Setup/Update/чистая установка и публикация только после проверок.

## Действующее состояние — поколение 38, 2026-10-14

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

## План после опубликованной v0.37.1

1. Восстановить поколение 37 из ветки `context` с проверкой контрольных сумм; сверить main/Release.
2. Предложить владельцу установщик обновления v0.37.1 и проверить переключение фрагментов на фактическом ответе 49 433 байта.
3. При сохранении бинарного формата после zlib попросить исходный образец приватно, без загрузки в публичный GitHub, и определить фактическую структуру без догадок.
4. Новое исправление только по воспроизводимой ошибке и с разрешения владельца, затем CI, Android 15, Windows Setup/Update, чистая установка, выпуск, обновление капсулы.

**Текущая опубликованная версия: v0.37.1** (2026-10-14), `main` и Release tag `41b3105aa4e2335a975eb6d126e61ed771e32b59`. Полный выпуск GitHub Actions #38553459909 завершился SUCCESS: CI, Android 15 AVD, Windows сборка, обновление с v0.37.0, чистая Windows и публикация.
- Выпуск: https://github.com/lvlaksim1/apk-research/releases/tag/v0.37.1
- Обновление: https://github.com/lvlaksim1/apk-research/releases/download/v0.37.1/apk-research-update_v0.37.1.exe (47 549 287 байт; SHA256 `32203fd8ec1777f6b1ca29c6d02fcf5463d77022bc0f95867343c17a33654dda` — значение GitHub Release API).
- Полный установщик: https://github.com/lvlaksim1/apk-research/releases/download/v0.37.1/apk-research-setup_v0.37.1.exe (47 548 907 байт; SHA256 `11f984a40e7f3dbb9a7b8d46cba335ea3eb75c277c58ad77fcf25c03efb03125`).
- Причина обновления: в v0.37.0 корректный ответ application/zlib с исходным телом 49 433 байта вызывал `Ошибка распаковки вложенного zlib: Размер распакованных данных превышает 128 КиБ`. Предел 128 КиБ ошибочно применялся к полной распаковке вместо видимого фрагмента, выводя HEX и скрывая доступный распакованный текст.
- Исправление: `desktop/body_display.py` разделяет размер выводимого фрагмента 128 КиБ и безопасный предел распаковки 8 МиБ. Читаемые ответы отображаются по фрагментам 1–64 в режиме «Текст (авто)», выбор фрагмента добавлен в живой просмотр и сохранённые ZIP. Превышение 8 МиБ показывает доступное начало и предупреждает, что полная целостность потока не подтверждена, без ложной ошибки сервера. `HEX` и все оригинальные сохранённые байты не меняются. Неподтверждённые бинарные форматы не объявляются текстом.
- PR #40 объединён; кандидат прошёл CI #38552638511 и Windows #38552638799, затем основной цикл #38553459909. Ранее PR #39 выпустил v0.37.0, PR #38 — независимый HTTPS/ZIP интерфейс v0.36.0.
- **Открытая проверка владельцем:** установить v0.37.1 и попробовать исходный ответ `ch.pala.resources` (49 433 байта): определится ли текст после zlib или остаётся собственный двоичный формат. Конкретный результат этого ответа на ПК владельца пока неизвестен. Нет открытого препятствия для релиза.
- Все ранее согласованные элементы сохранены: один HTTPS-анализатор с отдельной записью ZIP, 18 кнопок эмулятора, фильтры метода/домена, обновление в меню «Программа» и **отсутствие** вкладки «Настройки» по отказу владельца. Research ZIP, тела, токены и прочие приватные данные нельзя размещать в публичном GitHub.

---

## Предыдущие поколения (история)

## Plan after v0.37.0 release, 2026-10-14

1. Restore and check capsule generation 36, reconcile GitHub main and release.
2. Base any future changes on aa2cb71ab637c203810174a521e62aa1cf05c5df; obtain owner field feedback for HTTP body display on `ch.pala.resources` and compare original HEX with derived text.
3. When a real compressed body decodes to an unknown binary structure, request a sanitized/privately supplied body or ZIP, investigate actual binary schema without inventing text.
4. Preserve all v0.36 controls, independent HTTPS/ZIP and actual source evidence. Changes require user approval plus CI/AVD/Windows setup/update/provisioning and verified release gates.
5. Never introduce an unrequested Settings tab.

---

## Исторический контекст предыдущих поколений

## Next-stage plan after published v0.36.0 — 2026-10-14

1. Restore sealed `context` and reconcile current main and release before future work.
2. Use v0.36.0 exact main `5f66b1940acd6b867d569d8a62faae4c338bde4f` as baseline. Ask owner to update then report actual independent HTTPS/ZIP workflow, filters, toolbar, Android top bar and ZIP correctness.
3. On specific reported defects: reproduce, branch off verified main, run CI + real Android 15 AVD + Windows GUI/Setup/Update/clean provisioning and ARM64 where applicable; merge after success, release only through main workflow.
4. Preserve no-ZIP during HTTPS-only mode, single persistent HTTPS analyzer, bounded recordings, privacy, full Research ZIP integrity and no added Settings tab. WHPX #38439063246 not confirmed completed.

---

## Archived previous-generation notes — superseded where inconsistent

## Default change/release plan

1. Reinstate from `context` and reconcile live `main`, latest release and CI.
2. Use a dedicated feature/fix branch from the verified baseline.
3. Make the minimum coherent change.
4. Run unit/compile plus relevant real AVD and Windows verification.
5. For updater changes, prove a real previous-release → candidate update with the dedicated Update installer.
6. Publish stable releases only through the main pipeline.
7. Persist verified state and reseal manager integrity.

## Current release architecture

Stable releases publish:
- `apk-research-setup_v<version>.exe`;
- `apk-research-update_v<version>.exe`;
- `SHA256SUMS.txt` covering both.

The application updater uses only the dedicated Update asset.

## HTTPS traffic analysis

The v0.30 implementation stage is complete and released.

Verified delivered scope:
- local application-managed HTTPS proxy;
- Android routing through `adb reverse`;
- temporary research CA trust in the managed rooted Android 15 environment;
- HTTP transaction metadata and bodies in Research ZIP;
- dedicated HTTP/HTTPS desktop viewer;
- passive RAW PCAP preserved as an independent evidence source;
- real Android 15 end-to-end acceptance.

Do not claim universal HTTPS decryption. Certificate pinning/custom trust and HTTP/3/QUIC remain separate bounded follow-up areas.

## Current product plan

The owner subsequently authorized a bounded HTTPS routing correction for applications that bypass the Android system proxy. Begin with the reported `com.evrasia` evidence from `20261008T020126.928669Z-e336ad57.research.zip`, independently re-check archive evidence and then inspect the current routing/proxy implementation. Develop and verify a robust automatic routing path without weakening protected Android runtime or forensic invariants. Preserve explicit technical boundaries (application-controlled trust and QUIC/HTTP3 remain unclaimed unless separately verified).

The previous "no further stage is authorized" assertion was true at the v0.30.0 seal but is superseded by the later 2026-10-08 owner directive. v0.31.0 delivered the separate ARM64 XAPK requirement, but did **not** implement the active direct HTTPS routing requirement.

The Android home-screen shortcut requirement remains cancelled.

## ARM64 compatibility maintenance

Preserve the separate default and Google APIs Android 15 AVD userdata, verify real ARM64 execution (not just installation) and use target-specific diagnosis for owner-supplied APK/XAPK. Avoid breaking the proven root/gRPC-MMAP research runtime. Direct TCP/443 routing is now delivered in v0.32.0; next action is field validation on the owner's `com.evrasia` APK.

## Follow-up plan after v0.32.0

Obtain a real v0.32.0 session on the owner's target app, compare route log (actual direct target IP/port) with readable transactions, count HTTP responses and inspect TLS trust errors if any. Keep RAW PCAP independent. Do not infer decrypted HTTPS from TCP/443 connectivity alone; acknowledge custom certificate trust or QUIC/UDP443 limitations where supported by evidence. Develop further only from verified owner artifacts. Owner-visible terminology: neutral HTTPS routing and analysis terms.

## v0.32.0 owner target field verification — closed

The owner supplied a v0.32.0 session of com.evrasia. Its HTTP records, route journal, session status and 99/99 checksum verification establish that selected-app direct HTTPS analysis now works for the previously problematic target. Historic notes instructing a future field validation are superseded by this observation.

Next possible investigation: packet loss (615 kernel drops), unassigned ownership (73 of 93 flow entries), and optional per-transaction route source labels. Do not assume these are equivalent to lost HTTP transactions. Do not change implementation without agreeing on scope. Never commit the private Research ZIP or any authentication contents.

## v0.33.0 field usability and completeness follow-up

The simplification is complete and published. Request the owner's field confirmation that precisely two tabs appear, the current HTTPS list updates while interacting with the Android screen, ZIP is created, and existing studies remain accessible. If a new archive is supplied, measure actual packet drops after the new 16-MiB kernel buffer instead of asserting the issue is fixed. Technical workspace tabs remain out of the main window by explicit owner decision; do not restore them without permission.

## v0.34.0 delivery plan

All source in PR #32, branch feature/v0.34-emulator-controls-network-evidence. Await required latest commit tests. Optional six derived ZIP artifacts cannot replace RAW PCAP or HTTP bodies. Avoid false claims from null TLS/DNS fields and temporal correlation. Full update installer must update from published v0.33.0 without deleting app data. Publish only through main pipeline; then user should validate panel controls and target real APK and provide new ZIP to assess DNS/TLS and packet drop results.

## Plan after published v0.34.0 (generation 32)

1. Resume from release v0.34.0 at `2efec386cff0b204ee56d8bee365f3c52caefcb5` and the sealed manager `context` generation 32. PR #32 is merged and PR #33 is closed without merge; no current v0.34.0 implementation work remains pending in those branches.
2. Obtain owner's first practical feedback on the sidebar's buttons, direct HTTPS view and Research ZIP data from the installed release. Check the actual target APK rather than drawing conclusions from synthetic acceptance.
3. If owner supplies a Research ZIP, measure source-data completeness, tcpdump drops, attribution ambiguity, DNS/TLS availability and temporal-action matches without inventing data; handle authentication and personal content privately, never commit the archive.
4. Retain release policy: dedicated code branch, tests, Android 15 AVD, Windows GUI/install/update/clean-provisioning, merge, main pipeline, verified published Setup/Update assets and re-sealed context.
5. Keep postponed network-recovery concept unmerged unless the loading issue recurs with diagnostics or the owner explicitly reauthorizes implementation. No automatic modification of emulator data on speculation.
