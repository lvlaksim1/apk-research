# Manager goals

## Приоритет после выпуска v0.38.1 — поколение 39

Поддерживать модельный редактор и явно выполняемые ручные HTTPS-запросы. Не блокировать основную таблицу редактором, показывать все повторные отправки со значком ↻ и актуальным состоянием, не записывая их в исследовательские доказательства. Проверять v0.38.1 на ПК владельца и исправлять только воспроизводимые ошибки по согласованию. Текущая исходная база `be63ad0e00894da424660cbb1a6da91ed69dd0ce`. Основной выпуск #38587459121 SUCCESS.

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

Текущая цель: поддерживать v0.38.0 как опубликованную базу; подтверждать автоматическое форматирование JSON и явную повторную отправку только из разрешённой копии запроса. Не изменять оригинальный журнал/ZIP. Приоритет — полевая проверка на настоящем приложении, сохранение всех v0.37.1 и v0.36.0 функций. ## Действующее состояние — поколение 38, 2026-10-14

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

## Текущий ориентир — поколение 37

В v0.37.1 корректные большие zlib/gzip-ответы не должны ошибочно объявляться повреждёнными из-за размера 128 КиБ. Отображать до 8 МиБ распакованного содержимого по 128-КиБ фрагментам, неизменно сохранять исходный HEX/ZIP; не домысливать двоичные форматы. Базовый коммит `41b3105aa4e2335a975eb6d126e61ed771e32b59`. Сохранить независимый режим HTTPS/ZIP и отказ от вкладки настроек.

---

## Предыдущие поколения (история)

## Current goal — v0.37.0

Keep published text/HEX presentation reliable and non-destructive. Maintain bounded gzip/zlib/multipart decoding in live and saved ZIP; preserve RAW evidence and all v0.36 interaction semantics. Ask for owner field sample when a binary protocol remains after decompression; never guess missing content. Exact main aa2cb71ab637c203810174a521e62aa1cf05c5df.

---

## Исторический контекст предыдущих поколений

## Current v0.36 product goals — 2026-10-14

Preserve the independently controlled HTTPS/ZIP lifecycle, scope captured data to the explicit ZIP interval, and make all emulator controls and domain/method filters accessible. Preserve RAW PCAP, gRPC/MMAP, ARM64/XAPK, setup/update workflow and privacy. No new Settings tab without explicit approval. Published authority: main `5f66b1940acd6b867d569d8a62faae4c338bde4f`.

---

## Archived previous-generation notes — superseded where inconsistent

- Preserve continuity of apk-research across chats/runtimes without relying on conversational memory alone.
- Keep the Windows GUI and managed Android research workflow reliable and understandable for the owner.
- Preserve forensic correctness: RAW-first evidence, explicit provenance, exact packet/flow accounting and no causal overclaim.
- Evolve the product incrementally from the latest verified baseline, protecting the proven v0.10.5 startup/runtime path unless evidence justifies change.
- Keep releases reproducible through the repository's commit-triggered CI/AVD/Windows packaging gates.
- Maintain durable project decisions, verified lessons and active commitments on the authoritative `context` branch.
- Make decrypted HTTPS application traffic directly inspectable in apk-research: requests and responses, including URL, method/status, headers and available bodies, while preserving passive RAW PCAP as an independent source of truth and explicitly recording traffic-routing changes and their effects.
