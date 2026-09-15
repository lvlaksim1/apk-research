# Mobile Research

## v0.8.2 — Correct gRPC/MMAP display orientation

Исправлена единственная проблема, обнаруженная реальным тестом v0.8.1: raw-кадр `streamScreenshot` больше не переворачивается повторно по вертикали. Для кадров введён явный `row_order`; gRPC/MMAP помечается как `top-down`, поэтому изображение совпадает с реальными координатами Android. Потоковый touch DOWN/MOVE/UP не изменён. Безоконный `-qt-hide-window` startup и отсутствие вспышек сохранены.

## v0.8.1 — Native embedded Emulator path

Release-ready сборка новой архитектуры: основной Windows startup использует `-qt-hide-window + gRPC/MMAP`; DWM остаётся только последним compatibility fallback. Runtime соответствует v0.8.0, исправлен только release test gate.

## v0.8.0 — Native embedded Emulator path

Основной Windows display path больше не использует видимое standalone-окно Emulator. Emulator стартует через `-qt-hide-window`, изображение идёт напрямую через Emulator gRPC/MMAP в `AndroidView`, ввод — через persistent gRPC DOWN/MOVE/UP. DWM сохранён только как последний compatibility fallback. В нормальном embedded-path отдельному окну Emulator нечему мигать на рабочем столе.

## v0.7.11 — Self-healing Android boot

Release-ready сборка механизма v0.7.10. Runtime не изменён: один soft restart зависшего AVD, затем при повторном stall один штатный `-wipe-data`. Исправлен только release test gate.

## v0.7.10 — Self-healing Android boot

Поверх v0.7.9 добавлено только восстановление зависшей загрузки Android. Если Emulator жив, но Android не достигает `sys.boot_completed=1`, Mobile Research один раз мягко перезапускает тот же AVD с сохранением userdata. Если повторная загрузка тоже зависает — один раз выполняется штатный Emulator `-wipe-data` и чистая загрузка. После успеха подготовка APK продолжается автоматически. DWM и real-time swipe не изменены.

## v0.7.9 — Automatic stale-Emulator cleanup

Поверх стабильной базы v0.7.8 добавлена только стартовая очистка private Android runtime. До создания GUI программа ищет зависшие `emulator.exe` / `qemu-system-*.exe`, относящиеся строго к `mobile_research_api35`, корректно завершает их и удаляет оставшиеся AVD `*.lock` только после исчезновения процессов. Сторонние Emulator и общий `adb.exe` не затрагиваются. DWM, загрузка Android, reset и real-time swipe не изменены.

## v0.7.8 — v0.7.4 baseline + real-time swipe only

Полный функциональный baseline возвращён к v0.7.4. Единственное изменение поведения: свайп мышью передаётся как настоящий touch lifecycle DOWN → MOVE → UP и поэтому Android реагирует во время движения, а не после отпускания кнопки. Изменения v0.7.5–v0.7.7 в запуске Emulator, DWM, reset/AVD lifecycle и orphan cleanup не входят в этот релиз.

## v0.7.4 — Covered DWM source window

После теста v0.7.3 source Emulator больше не уводится за virtual desktop: это обнуляло его DWM/GPU surface. Вместо этого настоящее standalone GPU-окно постоянно располагается полностью внутри границ Mobile Research и непосредственно за ним по Z-order. Пользователь видит только DWM live внутри вкладки Исследование. При переключении на другие вкладки DWM thumbnail явно скрывается; при возврате включается снова.

## v0.7.3 — Single-window DWM live

DWM live теперь работает как единое пользовательское окно: standalone Emulator остаётся техническим top-level GPU source для Windows, но постоянно удерживается за пределами всего virtual desktop и исключается из taskbar/Alt+Tab. Mobile Research поддерживает это состояние на протяжении всей загрузки и работы, поэтому Qt Emulator не может вернуть окно на экран. При закрытии сначала завершается Emulator, затем отключается DWM — без вспышки второго окна.

## v0.7.2 — DWM live Emulator composition

Итоговый DWM live release. Помимо display-path исправлена release-candidate логика: временный installer artifact создаётся только для commit-driven релизов и удаляется после публикации GitHub Release.

## v0.7.1 — DWM live Emulator composition

Финальный release DWM live path: Android Emulator остаётся самостоятельным GPU/top-level окном, DWM композитит его в Android-панель Mobile Research без `SetParent`; дополнительно исправлена обработка Win32 thumbnail handle.

## v0.7.0 — DWM live Emulator composition

Основной Windows display path больше не использует cross-process `SetParent`. Android Emulator остаётся обычным standalone GPU-окном, а Windows Desktop Window Manager композитит его live-содержимое прямо в Android-панель Mobile Research. Исходное окно после успешного DWM attach перемещается за пределы видимого рабочего стола, не скрывается и не минимизируется. Управление остаётся через gRPC. gRPC/MMAP сохраняется как автоматический fallback.

## v0.6.0 — Real standalone Emulator HWND

Основной Windows display path теперь использует настоящее видимое standalone Qt/GPU-окно Android Emulator и встраивает именно его top-level HWND. `-qt-hide-window` больше не используется как источник native HWND. gRPC/MMAP framebuffer остаётся страховкой до подтверждённого native attach и автоматическим fallback. Также восстановлена коррекция reverse rotation, исправляющая перевёрнутый первый framebuffer-кадр.

## v0.5.2 — Reliable embedded Android display

Реальный тест v0.5.1 выявил ложный native attach: скрытый Qt HWND, созданный `-qt-hide-window`, успешно переподчинялся через Win32, но не являлся пригодной видеоповерхностью, поэтому GUI показывал пустой Android-контейнер. В v0.5.2 stable Windows path исправлен: `-qt-hide-window` используется только как штатный embedded-режим Emulator, а изображение передаётся через gRPC/MMAP framebuffer. Native HWND/SetParent отключён в стабильном runtime. GPU fallback: host → auto → SwiftShader/headless.

## v0.5.1 — Windows Emulator startup fallback

После реального теста v0.5.0 Windows startup получил многоступенчатый fallback. Mobile Research сначала пытается запустить native HWND + host GPU, затем при сбое автоматически переходит на headless + host GPU и, при необходимости, на headless + SwiftShader. В headless-режиме интерфейс автоматически возвращается к MMAP/gRPC framebuffer, поэтому сбой native Qt/GPU path больше не блокирует исследование. Внутренний Android Emulator crash reporter для managed-запуска отключён, а все попытки старта сохраняются в диагностике.

## v0.5.0 — Native Emulator Window

Windows-версия больше не использует screenshot/framebuffer mirroring как основной способ показа Android. Mobile Research запускает managed Android Emulator в скрытом Qt-режиме, находит его настоящее native HWND после загрузки и переподчиняет это окно непосредственно центральному Android-контейнеру программы. Рендеринг и ввод остаются внутри самого Android Emulator; MMAP/gRPC и ADB используются только как fallback и research/control transport.

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
Mobile Research сама управляет Android-компонентами, устанавливает APK, показывает Android внутри GUI и запускает существующее research core кнопками START/STOP.

Desktop Build собирает автономный MobileResearchSetup.exe. Android SDK/Emulator/system image загружаются самой программой в %LOCALAPPDATA%\MobileResearch\components после одноразового принятия Android SDK License Agreement.

Подробный desktop contract: docs/V0.2_DESKTOP.md.

## v0.2.2 — Windows hypervisor compatibility hotfix

В v0.2.2 исправлена регрессия v0.2.1: рабочий AEHD/GVM снова является допустимым пользовательским fallback, при этом WHPX остаётся предпочтительным и обязательным для dedicated Windows hardware acceptance. WHPX остаётся предпочтительным Windows hypervisor и обязательным hardware release-acceptance path, но пользовательский runtime снова принимает уже установленный и рабочий AEHD/GVM как совместимый fallback до завершения его официального переходного периода. Это разделяет две разные задачи: release должен доказать современный WHPX path, а приложение не должно ломать уже рабочий компьютер пользователя только из-за наличия поддерживаемого legacy hypervisor.

При отсутствии любого usable hypervisor Mobile Research включает только Windows Hypervisor Platform одним UAC-запросом, выставляет `hypervisorlaunchtype=Auto` и явно сообщает о необходимости перезагрузки, если она требуется.


## v0.2.1 — hardening пользовательского Windows-сценария

v0.2.1 исправляет обнаруженный на реальном приложении `com.evrasia` отказ preflight: зависший полный Package Manager dump больше не уничтожает всё исследование. Mobile Research ожидает завершения pending Package Manager operations, использует ограниченные по времени основной и резервный способы получения package dump, а при их отказе продолжает logcat/screen/PCAP и завершает сессию как `partial`.

Также release contract усилен отдельным `Windows WHPX Acceptance`: он использует именно собранный `MobileResearchSetup.exe` того же commit SHA, устанавливает приложение на выделенный Windows x64 runner, начинает с чистого `%LOCALAPPDATA%\MobileResearch`, требует реальный WHPX, загружает managed Android, через установленный EXE определяет package и устанавливает фиксированный проверяемый APK Appium ApiDemos, запускает его и завершает полноценную research-сессию с проверкой и semantic audit Research ZIP.

Обычный GitHub-hosted `windows-latest` сохраняется для build/provisioning checks, но не считается доказательством реального Windows/WHPX boot.

## Stable core baseline

Mobile Research — Windows-система для воспроизводимого исследования сетевой активности Android-приложений в управляемой исследовательской среде.

## Статус

**v0.8.2 — Desktop Application** — primary Windows architecture остаётся `-qt-hide-window + gRPC/MMAP`; исправлена display-only инверсия raw framebuffer через явный top-down row-order contract. Потоковый touch и evidence pipeline не изменены.

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

Первый реальный evidence collector сохраняет:

- полный raw `getprop`;
- raw `dumpsys package <package>`; для больших package dumps Android сначала пишет полный вывод во временный session-файл на target, после чего Mobile Research переносит его через `adb pull`;
- raw пути APK из `pm path`;
- системный snapshot: `id`, `uname -a`, SELinux, размер и плотность экрана;
- target/host clock markers вокруг snapshot;
- производный `02_normalized/target.json` с базовыми характеристиками target и package.

Обязательные команды приводят collector к `failed`, а сбой дополнительной системной команды фиксируется внутри snapshot и не уничтожает остальные данные.

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
- `02_normalized/screen.json` содержит хронологию chunks, команды, return codes, remote PID, timestamps и размеры;
- если Android `screenrecord` содержит Winscope-v2 metadata track, collector извлекает frame count и абсолютные UTC timestamps первого/последнего кадра без изменения raw MP4.

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
mobile-research targets
mobile-research targets --json
mobile-research target-info emulator-5554 --json
mobile-research package-check emulator-5554 com.example.app

mobile-research session-create emulator-5554 com.example.app --json
mobile-research metadata-collect "C:\path\to\session" --json
mobile-research session-status "C:\path\to\session" --json
mobile-research session-export "C:\path\to\session" --json
mobile-research research-zip-verify "C:\path\to\session.research.zip" --json
mobile-research research-zip-audit "C:\path\to\session.research.zip" --json

mobile-research run emulator-5554 com.example.app
```

То же без установленного entry point:

```powershell
python -m mobile_research targets --json
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
- Python >= 3.11.
- Android Debug Bridge (ADB) — внешняя runtime-зависимость.
- На первом этапе интерфейс — CLI.

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Следующий этап

После v0.1.0 развитие идёт как **v0.2**. Приоритеты: AVD lifecycle/snapshots, normalized timeline, расширение target abstraction для AVD-PLAY/Physical Device и только затем дополнительные decoder/instrumentation слои. Raw evidence contract v0.1.0 остаётся совместимой базой.

## CI и release gate

- `CI` автоматически запускается на push/pull request на Windows;
- `AVD Research Acceptance` автоматически запускает настоящий Android Emulator на Ubuntu/KVM;
- `Release` запускается по release-prep commit, ждёт успешные CI + AVD acceptance **того же commit SHA**, затем собирает wheel/sdist, создаёт `SHA256SUMS.txt` и публикует tag/GitHub Release;
- ручной `workflow_dispatch` не используется.

Release `v0.1.0` не считается готовым, пока exact release commit не пройдёт оба обязательных gate.
