# apk-research

## v0.16.0 — QUIC / HTTP/3 Network Intelligence

v0.16.0 расширяет post-capture Network Analyzer поддержкой QUIC v1/v2 и HTTP/3. Для UDP-трафика parser распознаёт QUIC long headers, а для Initial-пакетов использует публично выводимые Initial secrets стандарта QUIC, чтобы извлечь TLS ClientHello metadata: SNI и ALPN. ALPN `h3` / `h3-*` маркируется как HTTP/3.

`02_normalized/network-flows.json` обновлён до schema `0.3` и хранит `application_protocols`, `quic_versions`, `quic_packet_types`, `quic_sni`, `quic_alpn` и признак успешного Initial decode. Network Analyzer показывает эту evidence отдельно и использует QUIC SNI как наиболее прямое имя host для такого flow.

Граница доказательств строгая: UDP/443 сам по себе не считается QUIC; Initial decode не является MITM и не даёт ключей Handshake/1-RTT. Raw PCAP, socket attribution, Timeline temporal-only semantics и проверенный v0.10.5 runtime/clean-launch path не меняются.

## v0.15.0 — Product rename to apk-research

Начиная с v0.15.0 программа, репозиторий, Python distribution/namespace, GUI, CLI, EXE, installer, release assets, каталоги установки и техническая документация используют единое имя `apk-research`.

Это rename-only release: validated hidden Emulator → gRPC/MMAP runtime, v0.10.5 clean-launch sequencing, collectors, Research ZIP schemas, raw PCAP, attribution, Timeline и Network Analyzer semantics не меняются.

## v0.14.0 — Host Intelligence: Service vs DNS

v0.14.0 уточняет host-oriented Network Analyzer по результату реального v0.13.0 Research ZIP. DNS-resolution flows больше не смешиваются с service endpoints в host-сводке: DNS resolver показывается отдельно, а owner/confidence хоста вычисляются по service flows, если они существуют.

Для каждого host теперь отдельно отображаются service IP/ports, DNS resolver IP, количество service/DNS flows, период активности, суммарный трафик и связанные Timeline actions. Для DNS-only имени интерфейс явно сообщает, что наблюдалось разрешение имени, но отдельный service flow с этим hostname не подтверждён.

Изменение presentation-only: исходные normalized flows, flow_id, raw PCAP, socket attribution, Timeline schema 0.4, Research ZIP и подтверждённый v0.10.5 runtime/clean-launch path не меняются.

## v0.13.0 — Host-oriented Network Analyzer

v0.13.0 переводит Network Analyzer с плоского списка соединений на исследовательскую модель `Host → Flow → Timeline`. Верхний уровень дерева группирует normalized flows по лучшему доступному имени узла: TLS SNI, затем DNS query, затем remote IP.

Для каждого host отображается агрегированная сводка: число соединений и пакетов, TCP/UDP, owner, confidence breakdown, remote IP, суммарный входящий/исходящий трафик и связанные user actions. Раскрытие host показывает исходные normalized flows без изменения evidence.

Для выбранного flow вместо сырого JSON показывается человекочитаемая карточка с endpoint, временем, длительностью, трафиком, package/process/PID/socket inode evidence, DNS/SNI и связанными Timeline actions. Поиск также учитывает action ID. Переход Network → Timeline поддерживает выбор конкретного связанного действия; обратная навигация Timeline → Network сохраняется.

Формат Research ZIP, raw PCAP, schema `network-flows.json 0.2`, Timeline schema `0.4` и подтверждённый v0.10.5 clean-launch/runtime path не изменяются.

## v0.12.0 — Unified Timeline ↔ Network flow model

v0.12.0 переводит Research Timeline на ту же нормализованную модель соединений, которую использует Network Analyzer. Timeline schema теперь `0.4`: события `network_flow_started` создаются по `flow_id` из `network-flows.json`, а не по старым directional packet-flow ключам.

Каждое user action correlation теперь содержит `flow_ids` и `new_flow_ids`. В самом `network-flows.json` каждый flow получает `correlated_action_ids`, поэтому связь работает в обе стороны без изменения исходного PCAP и без заявления причинности.

GUI поддерживает навигацию двойным кликом:
- Timeline action / network flow → соответствующий flow в Network Analyzer;
- Network Analyzer flow → первое связанное user action в Timeline.

Timeline summary также явно показывает количество normalized flows и число пакетов, не входящих в TCP/UDP inventory (`network_non_tcp_udp_packets`).

## v0.11.0 — Bidirectional Network Flows + Network Analyzer

v0.11.0 переводит `network-flows.json` на schema 0.2 и добавляет первый рабочий Network Analyzer в GUI.

Главное изменение модели: один TCP/UDP bidirectional 5-tuple теперь является одним normalized flow независимо от направления пакета и от того, в какой момент socket sampler впервые смог доказать владельца. Ранние `UNKNOWN` пакеты больше не создают отдельный raw-flow рядом с позднее подтверждённым package-owned flow. В каждом flow сохраняются packet/byte counters отдельно для outbound/inbound, confidence breakdown, лучший owner, DNS и TLS SNI.

В GUI появляется вкладка `Network` и кнопка `Network Analyzer` для выбранного Research ZIP. Доступны фильтры по owner и protocol, поиск по host/IP/process/DNS/SNI, таблица local/remote endpoint, трафик ↑/↓ и confidence, а также полный JSON выбранного flow.

## v0.10.5 — v0.10.3 startup baseline + deferred optional package dump

Реальный Windows-тест v0.10.4 показал регрессию: изменение порядка startup привело к `LaunchState=None` на `com.evrasia`. v0.10.5 откатывает clean-launch path, collector ordering, clock calibration и `LaunchState: COLD` invariant к подтверждённой v0.10.3.

Исправление исходной задержки сделано локально. Device Metadata по-прежнему собирается до arm collectors, но тяжёлый и необязательный full Package Manager dump больше не блокирует старт. До запуска сохраняются getprop, lightweight package summary, package paths, system metadata и clock markers. Полный `cmd package dump` выполняется при завершении исследования, после остановки continuous collectors, и затем обновляет `package.txt` и `target.json` перед экспортом ZIP.

## v0.10.4 — Immediate clean-start boundary

Реальный v0.10.3 архив показал, что визуальный task transition уже скрыт корректно, но сам verified clean restart начинался слишком поздно: примерно через 7 секунд после создания сессии. Из них около 5.3 секунды занимал полный Device/Package Metadata snapshot до arm collectors. Из-за этого пользователь видел неожиданную «перезагрузку» уже через несколько секунд после нажатия «Начать исследование».

v0.10.4 меняет порядок без ослабления evidence. Быстрые network/socket preflight выполняются первыми, затем сразу arm'ятся logcat/screen/PCAP/socket attribution и выполняется verified clean restart. Только после `package_launched` собирается тяжёлый Device/Package Metadata snapshot и выполняется clock calibration. RAW collectors уже работают до cold start и непрерывно покрывают весь запуск; metadata остаётся обязательным evidence, но больше не задерживает сам clean-start boundary.

## v0.10.3 — Stable operator preview during verified cold start

Реальный Windows-тест v0.10.2 подтвердил `LaunchState: COLD`, но raw screen-video показал оставшийся системный close-transition старой Activity. Это неизбежная часть настоящего `force-stop`: после уничтожения окна исследуемого процесса Android физически не может продолжать показывать его как live surface. `FLAG_ACTIVITY_NO_ANIMATION` относится к запуску новой Activity и не отменяет уже инициированный stop/task transition.

v0.10.3 разделяет две плоскости. Forensic evidence остаётся полностью честным: Android `screenrecord`, logcat и PCAP непрерывно фиксируют stop → splash → cold start. Операторский gRPC/MMAP preview во время короткой clean-restart границы удерживает последний опубликованный кадр и сразу после подтверждённого `package_launched` переключается на свежий framebuffer. Android animation scales не меняются, приложение/AVD не модифицируются и evidence не фильтруется.

## v0.10.2 — Seamless clean launch

Реальный Windows-тест выявил видимый Android task transition в режиме «Чистый запуск»: после arm collectors apk-research выполняла отдельные host round-trips `force-stop → pidof verification → am start`, поэтому на встроенном экране успевал появиться Launcher и проигрывались close/open-анимации.

v0.10.2 сохраняет forensic-границу после arm collectors, но выполняет clean restart одной Android shell-транзакцией: `am force-stop <package> && am start -W --activity-no-animation ...`. Отдельная пауза/poll между stop и start удалена. Clean invariant теперь подтверждается самим `am start -W`: релиз требует `LaunchState: COLD` и запрещает reuse уже работающего Activity. Режим «Продолжить текущее состояние» не меняется.

## v0.10.1 — Process attribution hardening

Реальный Windows Research ZIP v0.10.0 выявил, что socket sampler корректно собирал target-UID sockets, но не фиксировал процессы/PID: в Android `/proc/<pid>/status` поле `Uid:` разделено TAB, а sampler задавал строковый `IFS=" \\t"`, который не содержит настоящий TAB. v0.10.1 использует штатный shell IFS, поэтому снова работает цепочка `package → UID → PID/process → FD → socket inode → 5-tuple → PCAP`.

Real AVD release gate теперь требует не только socket snapshots, но и фактически наблюдавшийся process исследуемого package. Это предотвращает публикацию релиза, если PID/process-слой attribution снова перестанет работать. Raw PCAP и validated hidden Emulator + gRPC/MMAP runtime не меняются.

## v0.10.0 — Package-aware Network Attribution

apk-research теперь сопоставляет сетевой трафик с исследуемым Android package по цепочке `package → UID → PID/process → socket inode → 5-tuple → PCAP flow`. Во время исследования отдельный collector снимает временные snapshots `/proc/net/tcp*` / `/proc/net/udp*` и socket-FD процессов целевого UID. Производные evidence сохраняются в `02_normalized/socket-attribution.jsonl`, `02_normalized/socket-attribution.json` и `02_normalized/network-flows.json`.

Для каждого flow/packet ownership имеет доказательный уровень `EXACT`, `HIGH`, `MEDIUM` или `UNKNOWN`. `EXACT` требует socket inode, точного 5-tuple, попадания пакета в непосредственно наблюдавшийся интервал жизни сокета и однозначного owner evidence: либо UID принадлежит только исследуемому package, либо при shared UID имеется прямая цепочка target-package process/PID → FD → inode. Shared UID без такой process/socket-связи остаётся `UNKNOWN`; sampling margin и wildcard endpoints явно понижают confidence. Raw `traffic.pcap` остаётся первичным источником истины. При этом связь user action → network по-прежнему маркируется отдельно как `temporal-only` с `causal_claim=false`: доказанная принадлежность сокета приложению не означает доказанную причинность конкретного tap/swipe.

## v0.9.2 — Refined Timeline is canonical in Research ZIP

v0.9.2 исправляет разрыв между GUI-анализом и forensic archive: `ResearchOrchestrator` теперь записывает в итоговый `.research.zip` тот же refined Timeline schema 0.2, который использует GUI. Экспортируемый Timeline использует high-resolution `adb-ntp-midpoint` calibration, неперекрывающиеся action windows и явно маркирует корреляцию как `temporal-only` без ложного утверждения причинности. Real AVD acceptance теперь проверяет именно Timeline внутри готового ZIP. Windows installer начиная с этого релиза всегда содержит версию в имени: `apk-research-setup_v<version>.exe`.

## v0.9.1 / v0.9.0 — User Actions + Research Timeline

apk-research теперь фиксирует действия пользователя во время активного исследования и строит производный `02_normalized/research-timeline.json`, объединяющий lifecycle, пользовательские действия и сетевые маркеры. Pointer gesture сохраняется как один `tap` или `swipe`, wheel — как swipe, клавиши и текстовый ввод — как user actions; последовательные символы группируются в timeline. Для каждого action рассчитывается временное окно и привязываются packet/flow statistics, новые network flows, DNS queries, best-effort TLS SNI и релевантный logcat sample. Host action clock переводится в target clock по сохранённым clock markers, поэтому correlation не предполагает, что Windows и Android имеют нулевой clock skew. В GUI вкладки «Результаты» добавлена кнопка **Research Timeline**.

> Важно: введённый через встроенный Android текст сохраняется в локальном Research ZIP как research evidence. Архив следует считать потенциально чувствительным.

## v0.8.9 — Evidence sequencing and timing hardening

Релиз исправляет три проблемы, обнаруженные при разборе реального Research ZIP v0.8.8. Package metadata больше не может превращать качественную сессию в `partial` только из-за необязательного полного Package Manager dump: исправлена remote `sh -c` quoting, используется валидный bounded `cmd package dump` с коротким `dumpsys` fallback, а versionCode дополнительно фиксируется лёгким package summary. Режим clean теперь выполняет проверенный `force-stop` только после запуска collectors и непосредственно перед launch, поэтому preflight больше не может разрушить clean-launch invariant. Screen evidence теперь явно разделяет wall-clock capture interval процесса `screenrecord` и Winscope frame/presentation span; raw MP4 не переписывается.

## v0.8.8 — Final technical cleanup

Финальный cleanup стабильного v0.8.7 runtime без изменения пользовательского поведения. Удалены подтверждённо мёртвые desktop state/helpers, package-level monkeypatch выбора Android repository archive заменён прямым стабильным policy-вызовом, а regression contract теперь запрещает возврат удалённых DWM/native/fallback путей и ручных workflow triggers. Рабочая цепочка hidden Emulator → gRPC/MMAP → AndroidView и persistent streamInputEvent не изменена.

## v0.8.7 — Frame readiness sequencing fix

Исправлена гонка v0.8.6, обнаруженная на реальном Windows-ПК: framebuffer worker запускался сразу после поднятия gRPC и одновременно требовал первый кадр в течение 15 секунд, то есть ещё до завершения Android boot. Теперь worker по-прежнему стартует рано и может показывать boot-кадры, но обязательный first-frame gate выполняется только после завершения Android boot/root preparation. Архитектура single required path не меняется и fallback не возвращается.

## v0.8.6 — Single required runtime path

apk-research больше не имеет пользовательской страховочной display/input-архитектуры. Штатный Windows runtime теперь один: скрытый Android Emulator `-qt-hide-window` → Emulator gRPC → MMAP framebuffer → `AndroidView`; ввод — только через постоянный gRPC `streamInputEvent`. DWM, visible Emulator, gRPC byte-frame fallback, ADB screencap и ADB input fallback удалены. Если обязательный transport не работает, подготовка завершается диагностической ошибкой вместо перехода в другой режим. Startup cleanup и один `-wipe-data` при guest boot stall сохранены как recovery, а не как альтернативный runtime.

## v0.8.5 — GUI smoke correction

Release-candidate v0.8.4 не был опубликован: Desktop Build выявил оставшуюся старую ссылку `detach_native()` в `MainWindow.closeEvent` после DWM-переименования. v0.8.5 исправляет shutdown path на `detach_dwm()` и дочищает последние legacy native-имена в runtime-тестах. Архитектура и поведение v0.8.4 не меняются.

## v0.8.4 — Legacy display cleanup

Второй этап technical cleanup. Активный DWM fallback сохранён без изменения поведения, но полностью отделён от отвергнутой native HWND/SetParent терминологии: модуль переименован в `dwm_emulator.py`, presentation-класс и сигналы получили DWM-имена, удалены неиспользуемые Win32 helpers и старый dead tap signal path. `AndroidView` больше не требует собственного native HWND только ради старой SetParent-архитектуры. Основной gRPC/MMAP display/input baseline v0.8.2 не изменён.

## v0.8.3 — Technical cleanup

Технический cleanup после подтверждённого реального теста v0.8.2. Display/input baseline не меняется. Удалён бесполезный soft-restart из boot recovery: guest boot stall теперь получает ровно один официальный `-wipe-data`, а при повторном stall запуск останавливается без перехода к новым 150-секундным graphics cycles. Desktop contract и release-gate документация приведены в соответствие с фактической архитектурой.

## v0.8.2 — Correct gRPC/MMAP display orientation

Исправлена единственная проблема, обнаруженная реальным тестом v0.8.1: raw-кадр `streamScreenshot` больше не переворачивается повторно по вертикали. Для кадров введён явный `row_order`; gRPC/MMAP помечается как `top-down`, поэтому изображение совпадает с реальными координатами Android. Потоковый touch DOWN/MOVE/UP не изменён. Безоконный `-qt-hide-window` startup и отсутствие вспышек сохранены.

## v0.8.1 — Native embedded Emulator path

Release-ready сборка новой архитектуры: основной Windows startup использует `-qt-hide-window + gRPC/MMAP`; DWM остаётся только последним compatibility fallback. Runtime соответствует v0.8.0, исправлен только release test gate.

## v0.8.0 — Native embedded Emulator path

Основной Windows display path больше не использует видимое standalone-окно Emulator. Emulator стартует через `-qt-hide-window`, изображение идёт напрямую через Emulator gRPC/MMAP в `AndroidView`, ввод — через persistent gRPC DOWN/MOVE/UP. DWM сохранён только как последний compatibility fallback. В нормальном embedded-path отдельному окну Emulator нечему мигать на рабочем столе.

## v0.7.11 — Self-healing Android boot

Release-ready сборка механизма v0.7.10. Runtime не изменён: один soft restart зависшего AVD, затем при повторном stall один штатный `-wipe-data`. Исправлен только release test gate.

## v0.7.10 — Self-healing Android boot

Поверх v0.7.9 добавлено только восстановление зависшей загрузки Android. Если Emulator жив, но Android не достигает `sys.boot_completed=1`, apk-research один раз мягко перезапускает тот же AVD с сохранением userdata. Если повторная загрузка тоже зависает — один раз выполняется штатный Emulator `-wipe-data` и чистая загрузка. После успеха подготовка APK продолжается автоматически. DWM и real-time swipe не изменены.

## v0.7.9 — Automatic stale-Emulator cleanup

Поверх стабильной базы v0.7.8 добавлена только стартовая очистка private Android runtime. До создания GUI программа ищет зависшие `emulator.exe` / `qemu-system-*.exe`, относящиеся строго к `apk_research_api35`, корректно завершает их и удаляет оставшиеся AVD `*.lock` только после исчезновения процессов. Сторонние Emulator и общий `adb.exe` не затрагиваются. DWM, загрузка Android, reset и real-time swipe не изменены.

## v0.7.8 — v0.7.4 baseline + real-time swipe only

Полный функциональный baseline возвращён к v0.7.4. Единственное изменение поведения: свайп мышью передаётся как настоящий touch lifecycle DOWN → MOVE → UP и поэтому Android реагирует во время движения, а не после отпускания кнопки. Изменения v0.7.5–v0.7.7 в запуске Emulator, DWM, reset/AVD lifecycle и orphan cleanup не входят в этот релиз.

## v0.7.4 — Covered DWM source window

После теста v0.7.3 source Emulator больше не уводится за virtual desktop: это обнуляло его DWM/GPU surface. Вместо этого настоящее standalone GPU-окно постоянно располагается полностью внутри границ apk-research и непосредственно за ним по Z-order. Пользователь видит только DWM live внутри вкладки Исследование. При переключении на другие вкладки DWM thumbnail явно скрывается; при возврате включается снова.

## v0.7.3 — Single-window DWM live

DWM live теперь работает как единое пользовательское окно: standalone Emulator остаётся техническим top-level GPU source для Windows, но постоянно удерживается за пределами всего virtual desktop и исключается из taskbar/Alt+Tab. apk-research поддерживает это состояние на протяжении всей загрузки и работы, поэтому Qt Emulator не может вернуть окно на экран. При закрытии сначала завершается Emulator, затем отключается DWM — без вспышки второго окна.

## v0.7.2 — DWM live Emulator composition

Итоговый DWM live release. Помимо display-path исправлена release-candidate логика: временный installer artifact создаётся только для commit-driven релизов и удаляется после публикации GitHub Release.

## v0.7.1 — DWM live Emulator composition

Финальный release DWM live path: Android Emulator остаётся самостоятельным GPU/top-level окном, DWM композитит его в Android-панель apk-research без `SetParent`; дополнительно исправлена обработка Win32 thumbnail handle.

## v0.7.0 — DWM live Emulator composition

Основной Windows display path больше не использует cross-process `SetParent`. Android Emulator остаётся обычным standalone GPU-окном, а Windows Desktop Window Manager композитит его live-содержимое прямо в Android-панель apk-research. Исходное окно после успешного DWM attach перемещается за пределы видимого рабочего стола, не скрывается и не минимизируется. Управление остаётся через gRPC. gRPC/MMAP сохраняется как автоматический fallback.

## v0.6.0 — Real standalone Emulator HWND

Основной Windows display path теперь использует настоящее видимое standalone Qt/GPU-окно Android Emulator и встраивает именно его top-level HWND. `-qt-hide-window` больше не используется как источник native HWND. gRPC/MMAP framebuffer остаётся страховкой до подтверждённого native attach и автоматическим fallback. Также восстановлена коррекция reverse rotation, исправляющая перевёрнутый первый framebuffer-кадр.

## v0.5.2 — Reliable embedded Android display

Реальный тест v0.5.1 выявил ложный native attach: скрытый Qt HWND, созданный `-qt-hide-window`, успешно переподчинялся через Win32, но не являлся пригодной видеоповерхностью, поэтому GUI показывал пустой Android-контейнер. В v0.5.2 stable Windows path исправлен: `-qt-hide-window` используется только как штатный embedded-режим Emulator, а изображение передаётся через gRPC/MMAP framebuffer. Native HWND/SetParent отключён в стабильном runtime. GPU fallback: host → auto → SwiftShader/headless.

## v0.5.1 — Windows Emulator startup fallback

После реального теста v0.5.0 Windows startup получил многоступенчатый fallback. apk-research сначала пытается запустить native HWND + host GPU, затем при сбое автоматически переходит на headless + host GPU и, при необходимости, на headless + SwiftShader. В headless-режиме интерфейс автоматически возвращается к MMAP/gRPC framebuffer, поэтому сбой native Qt/GPU path больше не блокирует исследование. Внутренний Android Emulator crash reporter для managed-запуска отключён, а все попытки старта сохраняются в диагностике.

## v0.5.0 — Native Emulator Window

Windows-версия больше не использует screenshot/framebuffer mirroring как основной способ показа Android. apk-research запускает managed Android Emulator в скрытом Qt-режиме, находит его настоящее native HWND после загрузки и переподчиняет это окно непосредственно центральному Android-контейнеру программы. Рендеринг и ввод остаются внутри самого Android Emulator; MMAP/gRPC и ADB используются только как fallback и research/control transport.

## v0.4.0 — 60 Hz shared-memory embedded Android

Интерактивный Android переводится на тот же класс embedded transport, для которого сам Android Emulator предусматривает side-channel framebuffer: gRPC уведомляет о новых кадрах, а pixel data передаются через MMAP/shared memory без упаковки полного кадра в protobuf. GUI работает с целевой частотой ~60 Hz. Input передаётся через постоянный `streamInputEvent`, а Windows Emulator запускается через `-qt-hide-window`, как embedded Emulator в Android Studio. gRPC byte-stream и ADB остаются fallback.


## v0.3.1 — Emulator rendering and latency hotfix

v0.3.1 исправляет обнаруженные на реальном Windows-ПК проблемы v0.3.0: reverse-orientation framebuffer теперь нормализуется, а embedded Android rendering переведён на более лёгкий 360×640 RGBA stream и прямой QPainter без цепочки QImage copy → mirror → QPixmap → scaled pixmap. Windows hardware path сначала использует GPU host с автоматическим fallback на GPU auto.

## v0.3.0 — Live Emulator Interaction

Встроенный Android переведён с периодических ADB/PNG screenshots на постоянный локальный Android Emulator gRPC stream. Кадры передаются как RGB, GUI показывает только самый свежий кадр с частотой до ~30 fps, а touch/key input отправляется напрямую в Emulator. ADB сохраняется как fallback и как независимый research transport для collectors.

Для исследования доступны два режима запуска APK: **чистый запуск** и **продолжить текущее состояние**.


## v0.2.2 — Desktop Application

После стабильного v0.1.0 проект перешёл к полноценному Windows-приложению.
Штатный пользовательский сценарий v0.2 не требует Python, PowerShell, Android Studio, отдельного ADB или ручного AVD.
apk-research сама управляет Android-компонентами, устанавливает APK, показывает Android внутри GUI и запускает существующее research core кнопками START/STOP.

Desktop Build собирает автономный apk-research-setup.exe. Android SDK/Emulator/system image загружаются самой программой в %LOCALAPPDATA%\apk-research\components после одноразового принятия Android SDK License Agreement.

Подробный desktop contract: docs/V0.2_DESKTOP.md.

## v0.2.2 — Windows hypervisor compatibility hotfix

В v0.2.2 исправлена регрессия v0.2.1: рабочий AEHD/GVM снова является допустимым пользовательским fallback, при этом WHPX остаётся предпочтительным и обязательным для dedicated Windows hardware acceptance. WHPX остаётся предпочтительным Windows hypervisor и обязательным hardware release-acceptance path, но пользовательский runtime снова принимает уже установленный и рабочий AEHD/GVM как совместимый fallback до завершения его официального переходного периода. Это разделяет две разные задачи: release должен доказать современный WHPX path, а приложение не должно ломать уже рабочий компьютер пользователя только из-за наличия поддерживаемого legacy hypervisor.

При отсутствии любого usable hypervisor apk-research включает только Windows Hypervisor Platform одним UAC-запросом, выставляет `hypervisorlaunchtype=Auto` и явно сообщает о необходимости перезагрузки, если она требуется.


## v0.2.1 — hardening пользовательского Windows-сценария

v0.2.1 исправляет обнаруженный на реальном приложении `com.evrasia` отказ preflight: зависший полный Package Manager dump больше не уничтожает всё исследование. apk-research ожидает завершения pending Package Manager operations, использует ограниченные по времени основной и резервный способы получения package dump, а при их отказе продолжает logcat/screen/PCAP и завершает сессию как `partial`.

Также release contract усилен отдельным `Windows WHPX Acceptance`: он использует именно собранный `apk-research-setup.exe` того же commit SHA, устанавливает приложение на выделенный Windows x64 runner, начинает с чистого `%LOCALAPPDATA%\apk-research`, требует реальный WHPX, загружает managed Android, через установленный EXE определяет package и устанавливает фиксированный проверяемый APK Appium ApiDemos, запускает его и завершает полноценную research-сессию с проверкой и semantic audit Research ZIP.

Обычный GitHub-hosted `windows-latest` сохраняется для build/provisioning checks, но не считается доказательством реального Windows/WHPX boot.

## Stable core baseline

apk-research — Windows-система для воспроизводимого исследования сетевой активности Android-приложений в управляемой исследовательской среде.

## Статус

**v0.9.0 — Desktop Application** — validated single-path runtime сохранён; добавлены User Actions и unified Research Timeline с clock-aligned correlation к PCAP/network flows и logcat.

**v0.1.0 — Research Session Core** остаётся базовым evidence contract: RAW-first capture, complete/partial/failed semantics, Research ZIP и semantic audit.

Release gate включает Windows CI, реальный AVD-RESEARCH acceptance и semantic audit итогового Research ZIP. Перед release freeze получены два последовательных реальных `complete` результата на Android 15 / API 35.

Реализованы:

- **ADB Target Manager**
- **Session Manager**
- **Device/System Metadata Collector**
- **Logcat Collector**
- **Screen Recording Collector**
- **Raw Network Collector**
- **Export / Checksums / Research ZIP**
- **End-to-end Session Orchestrator**

v0.1.0 доказывает полный вертикальный цикл: реальный Android target → обязательные collectors → запуск package → STOP → проверенный Research ZIP → semantic timeline/evidence audit.

## Архитектурные принципы

- Главный управляющий компонент работает на Windows.
- Android рассматривается как заменяемый **Research Target**.
- Первичный target для v0.1 — исследовательский Android Emulator.
- Исходные данные исследования сохраняются отдельно от производных результатов.
- Raw network capture является обязательным источником данных; HTTP/MITM в будущем дополняет его, но не заменяет.
- Android Research Agent не является обязательной частью архитектуры и в v0.1 отсутствует.
- GUI, MITM, статический анализ APK, AVD-PLAY и Physical Device не входят в v0.1.

## ADB Target Manager

Умеет:

- находить ADB через явный путь, PATH, ANDROID_SDK_ROOT, ANDROID_HOME или стандартный Windows Android SDK path;
- перечислять targets из `adb devices -l`;
- сохранять состояния `device`, `offline`, `unauthorized`;
- определять emulator/physical;
- получать Android release, SDK level, manufacturer, model, ABI, build fingerprint и текущий root status;
- проверять наличие package;
- отдавать данные как текст или JSON.

## Session Manager

Умеет:

- создавать уникальную runtime-сессию;
- создавать стабильную структуру каталогов `00_manifest/01_raw/02_normalized`;
- вести атомарно записываемый `session.json`;
- контролировать допустимые переходы state machine;
- сохранять историю переходов с UTC timestamps;
- регистрировать collectors и artifacts;
- запрещать artifact paths, выходящие за пределы session root;
- сохранять non-fatal ошибки без остановки активной записи;
- завершать degraded-сессию как `partial`;
- завершать fatal-сессию как `failed`;
- загружать уже существующую сессию после перезапуска процесса.

Важное правило: non-fatal collector failure во время `active` помечает сессию как degraded, но не уничтожает уже собираемые evidence. После штатного STOP итог становится `partial`.

## Device/System Metadata Collector

Device/System Metadata Collector сохраняет:

- полный raw `getprop`;
- lightweight package summary через `cmd package list packages --show-versioncode`;
- best-effort полный Package Manager dump: сначала bounded `cmd package dump <package>`, затем короткий `dumpsys -t 5 package <package>`; вывод переносится через session-scoped remote file + `adb pull`;
- raw пути APK из `pm path`;
- системный snapshot: `id`, `uname -a`, SELinux, размер и плотность экрана;
- target/host clock markers вокруг snapshot;
- производный `02_normalized/target.json` с базовыми характеристиками target и package.

Полный verbose package dump является дополнительным raw evidence и сам по себе больше не переводит корректную сессию в `partial`. Если он недоступен, collector сохраняет явный diagnostic artifact и продолжает; versionCode при этом извлекается из lightweight summary. Отказ действительно обязательного metadata-source по-прежнему приводит collector к `failed`.

## Logcat Collector

Первый непрерывный collector:

- стартует только в состоянии session `starting`, то есть до запуска исследуемого package;
- пишет полный доступный `adb logcat -b all` без tag/package-фильтра;
- использует формат `epoch` с timestamps;
- не выполняет разрушительный `logcat -c`;
- использует минимальный pre-roll `-T 1`, а точные границы capture фиксирует host timestamps;
- сохраняет stdout и stderr раздельно;
- при STOP сначала делает graceful terminate, затем kill только после grace period;
- сохраняет уже записанный raw log даже при неожиданном завершении процесса;
- неожиданное завершение или пустой raw log переводят collector в `failed` и помечают session как degraded.

Служебная информация процесса сохраняется в `02_normalized/logcat.json`.

## Screen Recording Collector

Записывает экран последовательными MP4 chunks:

- штатный chunk — 170 секунд при совместимом диапазоне 1–180 секунд;
- каждый chunk сначала создаётся на Android, затем сразу переносится на Windows;
- уже перенесённые chunks не зависят от последующих ошибок;
- каждый video chunk и diagnostic log регистрируются в Session Manager;
- завершившийся по time limit chunk автоматически заменяется следующим при очередной health-check;
- STOP пытается послать адресный SIGINT PID нашего `screenrecord`;
- затем используется terminate → grace period → kill как fallback;
- пустой, неперенесённый или аварийно завершившийся chunk делает collector `failed`, сохраняя предыдущие chunks;
- `02_normalized/screen.json` содержит хронологию chunks, команды, return codes, remote PID, host/target timestamps, wall-clock `capture_span_seconds` и размеры;
- если Android `screenrecord` содержит Winscope-v2 metadata track, collector извлекает frame count, elapsed timestamps, realtime offset и абсолютные UTC timestamps первого/последнего кадра без изменения raw MP4;
- MP4 presentation/frame span и recorder capture interval считаются разными величинами: при статичном экране Android может не выдавать новые frames, поэтому authoritative coverage определяется жизнью recorder process, а frame timing — фактическими кадрами.

## Raw Network Collector

Для reference target **AVD-RESEARCH** реализован backend `adb-tcpdump`:

- требует AOSP research image с root ADB;
- preflight проверяет `uid=0` и наличие usable `tcpdump`;
- запускает `tcpdump -i any -p -s 0 -U -w -`;
- бинарный PCAP идёт напрямую через `adb exec-out` в Windows;
- stderr `tcpdump` на Android перенаправляется в отдельный temporary-файл и после STOP переносится в `tcpdump.stderr.txt`, чтобы диагностический текст не мог загрязнить бинарный PCAP;
- proxy/MITM не участвуют в capture;
- STOP сначала пытается послать SIGINT remote PID `tcpdump`, затем использует terminate/kill fallback;
- итоговый `traffic.pcap` проверяется по PCAP magic/version;
- неожиданное завершение процесса или невалидный PCAP делают session degraded, но уже записанные bytes сохраняются.

Artifacts:

```text
01_raw/network/traffic.pcap
01_raw/network/tcpdump.stderr.txt
02_normalized/network.json
```

Этот backend намеренно относится только к AVD-RESEARCH v0.1. AVD-PLAY и Physical Device получат отдельные capture backends позднее.

## Export / Checksums / Research ZIP

Терминальная session (`complete`, `partial` или `failed`) может быть экспортирована в самопроверяемый Research ZIP.

Перед экспортом:

- `complete` session обязана иметь все 4 обязательных collectors в статусе `completed`;
- проверяются обязательные raw artifacts и хотя бы один MP4 chunk;
- `partial/failed` session экспортируется даже при недостающих evidence, а проблемы сохраняются в результате validation;
- все реально существующие файлы session, включая незарегистрированные partial tails, сохраняются в ZIP;
- временные `*.tmp` не экспортируются.

`00_manifest/checksums.sha256` содержит SHA-256 всех экспортируемых файлов, кроме самого checksum-файла, включая `session.json`.

После создания ZIP автоматически выполняются:

1. CRC-проверка ZIP;
2. проверка безопасных и уникальных entry paths;
3. проверка полного checksum coverage;
4. повторный SHA-256 каждого файла уже из ZIP;
5. проверка terminal status и session ID в архивном manifest.

Для `complete` архивов доступен дополнительный semantic audit:
- обязательные collectors действительно `completed`, session не degraded;
- lifecycle events присутствуют и идут в правильном порядке;
- host/target clock skew контролируется;
- PCAP и logcat по timestamps перекрывают запуск package;
- raw package launch содержит `Status: ok`;
- screen evidence использует встроенные Android screenrecord Winscope-v2 frame timestamps для привязки кадров к абсолютному UTC.

Архив сначала создаётся как temporary file и заменяет destination только после успешной проверки.

## End-to-end Session Orchestrator

Команда `run` связывает реализованные компоненты в один пользовательский сценарий:

```text
target/package validation
        ↓
create session
        ↓
preflight
        ├─ device metadata
        └─ raw network backend
        ↓
starting
        ├─ logcat
        ├─ screen recording
        └─ raw network
        ↓
active
        ↓
launch package
        ↓
health checks
        ↓
Ctrl+C
        ↓
STOP collectors
        ↓
complete / partial
        ↓
verified Research ZIP
```

Если startup уже создал session, но последующий шаг падает, orchestrator переводит session в `failed`, останавливает успевшие стартовать collectors и пытается экспортировать failed Research ZIP.

Дополнительно сохраняются:

- `02_normalized/session-events.jsonl` — фактические lifecycle markers с host/target timestamps;
- `01_raw/device/package-launch.txt` — raw результат запуска Activity.

Collector failure во время ACTIVE не останавливает остальные collectors: session становится degraded и после STOP завершается как `partial`.

## CLI

```powershell
apk-research targets
apk-research targets --json
apk-research target-info emulator-5554 --json
apk-research package-check emulator-5554 com.example.app

apk-research session-create emulator-5554 com.example.app --json
apk-research metadata-collect "C:\path\to\session" --json
apk-research session-status "C:\path\to\session" --json
apk-research session-export "C:\path\to\session" --json
apk-research research-zip-verify "C:\path\to\session.research.zip" --json
apk-research research-zip-audit "C:\path\to\session.research.zip" --json

apk-research run emulator-5554 com.example.app
```

То же без установленного entry point:

```powershell
python -m apk_research targets --json
```

## v0.1: целевой сценарий

```text
ADB target
   ↓
проверка target и package
   ↓
создание research session
   ↓
запуск обязательных collectors
   ├─ logcat
   ├─ screen recording
   ├─ raw network capture
   └─ device/system metadata
   ↓
запуск исследуемого package
   ↓
работа пользователя с приложением
   ↓
STOP
   ↓
остановка collectors
   ↓
проверка файлов + SHA-256
   ↓
Research ZIP
```

Полный контракт v0.1: [docs/V0.1_SPEC.md](docs/V0.1_SPEC.md).

Архитектурные решения: [REFACTORING.md](REFACTORING.md).

## Среда разработки

- Windows — целевая host-платформа.
- Для пользователя поставляется self-contained `apk-research-setup.exe`; Python, Android Studio и отдельный ADB не требуются.
- Python >= 3.11 и CLI используются только как development/test interfaces внутри репозитория.

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Следующий этап

После стабилизации desktop/runtime baseline v0.8.x следующий продуктовый этап — расширение research semantics: user-action timeline, network flow analysis и app attribution. AVD-PLAY/Physical Device, decoders и instrumentation добавляются поверх неизменного RAW-first evidence contract.

## CI и release gate

- `CI` автоматически запускается на push/pull request на Windows;
- `AVD Research Acceptance` проверяет Research Session Core на настоящем Android Emulator под Linux/KVM;
- `Desktop Build` собирает и smoke-тестирует standalone Windows application/installer и clean provisioning;
- `Release` для stable version ждёт успешные CI + AVD Research Acceptance + Desktop Build того же commit SHA и публикует проверенный `apk-research-setup.exe`;
- `Windows WHPX Acceptance` является дополнительной hardware-проверкой и сейчас advisory, а не блокирующим gate;
- ручной `workflow_dispatch` не используется.
