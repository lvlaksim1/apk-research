# Refactoring and Architecture Log

Файл фиксирует архитектурные решения, границы и будущие крупные изменения Mobile Research. Это не журнал каждого мелкого коммита.

## Текущее состояние

**Этап:** v0.3.0.dev0 — low-latency embedded Android interaction.  
**Stable baseline:** v0.2.2 Desktop Application.  
**Core evidence baseline:** v0.1.0 Research Session Core.  
**Реализовано:** GUI, self-contained Windows distribution, managed Android runtime/AVD, APK install, embedded Android view, Windows provisioning gate и desktop release gates.  
**Принцип:** v0.1.0 raw evidence contract не ослабляется.

## Зафиксированные решения

### ADR-001 — Отдельный проект от Web Research
Mobile Research предназначен для Android-приложений. Web Research остаётся отдельным инструментом для browser/web-исследований.

### ADR-002 — Windows является control plane
Главная программа работает на Windows и отвечает за orchestration, хранение evidence, ADB, collectors и export.

### ADR-003 — Android является заменяемым Research Target
Архитектура не привязана исключительно к emulator. Планируются AVD-RESEARCH, AVD-PLAY и Physical Device.

### ADR-004 — Research Agent не является фундаментом
Android Research Agent может появиться позже только для конкретной функции, которую нецелесообразно реализовать через ADB, host collectors или системные средства.

### ADR-005 — RAW first
Raw evidence сохраняется до интерпретации. Для сети raw packet capture — первичный источник; MITM и protocol decoders только дополняют его.

### ADR-006 — Неизменяемость evidence
После capture raw-файлы не переписываются ради нормализации или отчётов. Производные данные хранятся отдельно.

### ADR-007 — v0.1 без GUI
Первый end-to-end сценарий реализуется через CLI.

### ADR-008 — v0.1 без MITM
Сначала доказывается надёжный сбор raw traffic, logcat, screen recording и metadata.

### ADR-009 — ADB вызывается без локального shell
Target Manager передаёт аргументы ADB напрямую в subprocess. Package name валидируется до remote shell command.

### ADR-010 — Degraded не является отдельным runtime state
Collector failure во время ACTIVE не переводит state machine сразу в терминальный `partial`. Session Manager сохраняет `status=active` и `degraded=true`, чтобы остальные collectors продолжали работу. После STOP деградированная сессия завершается как `partial`.

### ADR-011 — Manifest записывается атомарно
Каждое изменение session metadata записывается через временный файл и `os.replace`, чтобы аварийное завершение процесса не оставляло наполовину записанный JSON.

### ADR-012 — Metadata сохраняется одновременно как RAW и normalized
Device/System Metadata Collector сохраняет оригинальные ответы ADB в `01_raw/device/`. Удобный JSON в `02_normalized/target.json` является производным представлением и не заменяет исходные ответы Android.

### ADR-013 — Необязательные metadata-команды не рушат snapshot
Обязательные источники (`getprop`, package dump, package paths, clock) должны быть получены полностью. Сбой дополнительной команды (`uname`, SELinux, display metadata и т. п.) фиксируется в raw/normalized данных, но сам collector остаётся успешным.

### ADR-014 — Logcat buffer не очищается
Logcat Collector не использует `logcat -c`, поскольку очистка уничтожает состояние Android и особенно нежелательна для будущего Physical Device backend. Collector использует минимальный pre-roll `-T 1`; точные временные границы задаются host timestamps, а raw поток сохраняется без необратимой фильтрации.

### ADR-015 — STOP collector является двухступенчатым
Непрерывный collector сначала получает graceful terminate и grace period. Только если процесс не завершился, выполняется kill. Forced kill фиксируется в metadata, но сам по себе не делает уже записанный evidence невалидным.

### ADR-016 — Screen recording хранится независимыми chunks
Screen Recording Collector не создаёт один монолитный файл. Каждый MP4 chunk после завершения сразу переносится с Android на Windows и регистрируется как отдельный raw artifact. Поэтому повреждение следующего chunk не уничтожает уже полученную видеохронологию.

### ADR-017 — Screenrecord chunk duration = 170 seconds
Для широкой совместимости v0.1 не использует потенциально различающееся между Android-ветками поведение unlimited screenrecord. Chunk ограничен 170 секундами, то есть ниже документированного 180-секундного предела.

### ADR-018 — Screenrecord STOP сначала адресный
Если удаётся однозначно определить новый PID `screenrecord`, STOP посылает ему SIGINT. Если PID недоступен или процесс не завершается, используется host-side terminate и затем kill после grace period.

### ADR-019 — Raw network v0.1 использует adb-tcpdump
Динамическая emulator-console packet capture не является фундаментом v0.1: на современных Emulator 36.5+ console capture не покрывает весь Wi-Fi/netsim traffic. Reference backend запускает tcpdump внутри rooted AVD-RESEARCH и передаёт PCAP напрямую на host через `adb exec-out`.

### ADR-020 — Raw PCAP пишется напрямую на Windows
`tcpdump -w -` + `adb exec-out` исключает обязательный промежуточный capture-файл на Android. `-U` включает packet-buffered output, поэтому уже переданные пакеты сохраняются даже при аварийном завершении. Диагностический stderr самого `tcpdump` перенаправляется в отдельный remote-файл и забирается после остановки; это необходимо, потому что реальный Android `adb exec-out` может смешивать stderr remote-процесса с бинарным stdout.

### ADR-021 — Network backend является target-specific
`adb-tcpdump` — backend только для AVD-RESEARCH. AVD-PLAY и Physical Device не должны искусственно наследовать требование root/tcpdump; для них будут отдельные backend implementations за общей collector abstraction.

### ADR-022 — Checksums покрывают весь экспортируемый payload
`checksums.sha256` хеширует все файлы Research ZIP, кроме самого checksum-файла. В scope входят manifest, raw, normalized и сохранившиеся незарегистрированные partial artifacts. Это позволяет проверять архив независимо от исходной runtime-папки.

### ADR-023 — Complete и partial имеют разную строгость export validation
`complete` не экспортируется при отсутствии обязательного collector/evidence. `partial` и `failed` экспортируются с validation warnings, поскольку сохранение неполных evidence важнее формальной полноты.

### ADR-024 — Research ZIP проверяется после упаковки
Успех export означает не факт закрытия ZipFile, а успешную повторную проверку CRC, entry safety, checksum coverage и SHA-256 непосредственно из временного ZIP. Только после этого temporary archive атомарно заменяет destination.

### ADR-025 — Orchestrator не поглощает collectors
End-to-end слой отвечает только за порядок lifecycle, health checks, package launch, failure propagation и export. Capture-логика остаётся внутри самостоятельных collectors и может тестироваться независимо.

### ADR-026 — Collector failure во время ACTIVE не останавливает исследование
Health-check фиксирует деградацию, но остальные sources продолжают capture. Пользователь завершает эксперимент явно; итоговый session status становится `partial`.

### ADR-027 — Startup failure после создания session также является evidence
Если preflight/start/package launch падает после создания runtime session, orchestrator переводит её в `failed`, best-effort останавливает уже запущенные collectors и пытается сформировать failed Research ZIP вместо удаления данных.

## Порядок реализации v0.1

1. **ADB Target Manager — реализован.**
2. **Session Manager и state machine — реализован.**
3. **Device/system metadata collector — реализован.**
4. **Logcat collector — реализован.**
5. **Screen recording collector — реализован.**
6. **Raw network collector — реализован.**
7. **Export/checksum subsystem — реализован.**
8. **End-to-end Session Orchestrator + synthetic acceptance test — реализованы.**
9. **Real AVD-RESEARCH acceptance run — реализован и автоматизирован.**
10. **Semantic Research ZIP release audit — реализован.**
11. **v0.1.0 release gate — реализован.**

## Будущие направления

- AVD lifecycle manager и snapshots;
- AVD-PLAY;
- Physical Device backend;
- MITM;
- protocol parsing;
- static APK analyzer;
- normalized timeline;
- screen/input correlation;
- optional Android Research Agent;
- GUI.

## Правило изменения архитектуры

Изменения RAW evidence contract, target abstraction, session state machine или Research ZIP сначала фиксируются здесь или в отдельной спецификации, затем реализуются.


### ADR-030 — Крупные Android dumps не идут через capture_output
Полный `dumpsys package` может быть достаточно большим, чтобы текстовый ADB transport завершился нестабильно. Collector направляет stdout команды во временный файл под `/data/local/tmp/mobile-research/<session-id>/`, переносит его через `adb pull`, затем удаляет remote-файл best-effort. Это сохраняет полный raw dump и избегает зависимости от объёма stdout.


### ADR-031 — Screen timing берётся из встроенного Winscope metadata, а не из MP4 duration
Современный Android `screenrecord` пишет data-track `#VV1NSC0PET1ME2#` с elapsed frame timestamps и realtime-to-elapsed offset. Статичный экран может не генерировать новые frames, поэтому playback duration MP4 не обязан совпадать с wall-clock длительностью collector process. Mobile Research сохраняет raw MP4 без изменений и извлекает только summary первого/последнего frame UTC и frame count в `screen.json`.

### ADR-032 — Первый релиз требует semantic audit, а не только ZIP integrity
CRC/SHA-256 доказывают целостность архива, но не достаточность evidence. Release acceptance дополнительно проверяет lifecycle order, collector statuses, clock skew, временное покрытие logcat/PCAP, package launch и screen frame timing. Формально валидный, но семантически неполный Research ZIP не проходит release gate.


### ADR-033 — Release публикуется только после gates exact commit SHA
Release workflow не доверяет предыдущим успешным runs. Он ждёт завершения workflow `CI` и `AVD Research Acceptance` для собственного `GITHUB_SHA`. Только после двух `success` разрешены build/tag/GitHub Release. Это предотвращает публикацию версии, отличающейся от реально протестированного кода.

### ADR-034 — Release assets являются воспроизводимыми Python artifacts
v0.1.0 публикует wheel и sdist, собранные из release commit, плюс `SHA256SUMS.txt`. Research ZIP из acceptance остаётся краткоживущим CI evidence и не превращается в release artifact, поскольку это результат синтетического исследования, а не дистрибутив программы.

### ADR-035 — Release docs являются обязательной частью release commit
Release workflow проверяет, что `README.md`, `REFACTORING.md`, `CHANGELOG.md` и `RELEASE_NOTES.md` содержат выпускаемую версию. Публикация блокируется, если release documentation не синхронизирована с `pyproject.toml`.


### ADR-036 — Desktop GUI является основной границей продукта
Начиная с v0.2 штатный пользовательский интерфейс — `MobileResearch.exe`. CLI сохраняется только для разработки и диагностики. GUI вызывает core classes напрямую и не является текстовой оболочкой над CLI.

### ADR-037 — Пользователь не устанавливает Python
Desktop distribution собирается PyInstaller и устанавливается через Inno Setup. Python runtime и Qt входят в Mobile Research. Пользовательский компьютер не требует Python/pip/venv.

### ADR-038 — Android runtime принадлежит Mobile Research
ADB, Android Emulator, build-tools и system image не считаются внешними пользовательскими зависимостями. Mobile Research загружает официальные Google packages и хранит их в собственном каталоге `%LOCALAPPDATA%\MobileResearch\components`.

### ADR-039 — Android Studio не является зависимостью
Private AVD создаётся программой напрямую из managed system image/config. Android Studio и ручной AVD Manager пользователю не нужны.

### ADR-040 — Android отображается внутри GUI
Google Emulator запускается headless. Mobile Research получает framebuffer через ADB и передаёт input обратно через `input tap/swipe/text/keyevent`. Это отделяет UX от внешнего окна emulator и позволяет позже заменить framebuffer transport без изменения пользовательского контракта.

### ADR-041 — Stable desktop release публикует installer
Начиная с v0.2 основным release asset является `MobileResearchSetup.exe` + SHA-256. Stable publication требует exact-SHA Windows CI, real AVD acceptance и Desktop Build.


### ADR-042 — Managed Android использует только stable repository channel
Desktop provisioning выбирает Android SDK packages только из Google repository `channel-0`. Более новые beta/dev/canary revisions не имеют права автоматически попадать в пользовательский runtime. Это решение принято после того, как выбор не-stable Emulator привёл к отдельному crash на Windows.

### ADR-043 — Windows hosted CI проверяет provisioning, а не неподдерживаемый software boot
GitHub-hosted Windows runner без аппаратной виртуализации не является надёжным Android boot target. Windows gate обязан доказать download/checksum/extraction, executable versions и private AVD creation. Настоящий Android boot/root/tcpdump/Research ZIP остаётся обязательным real AVD gate на KVM. Пользовательский Windows runtime использует аппаратное ускорение/WHPX, а не `-accel off` как штатный fallback.

### ADR-044 — GUI авария не должна бросать уже собранные evidence
Если после старта research session GUI получает неожиданное исключение, controller best-effort вызывает штатный stop/export и публикует partial/failed Research ZIP. Если startup failure уже сформировал failed archive внутри orchestrator, GUI повторно его не экспортирует, а использует существующий архив.

### ADR-045 — Managed Android можно полностью восстановить без ручного удаления файлов
Настройки Mobile Research содержат repair action для удаления только managed Android SDK/Emulator/system image/AVD. Research sessions хранятся отдельно и не удаляются. Следующая подготовка заново скачивает официальные компоненты и проверяет checksums.


### ADR-046 — Stable Windows release требует installed-EXE WHPX hardware acceptance
GitHub-hosted Windows CI остаётся обязательным для сборки, unit/GUI smoke и чистого provisioning, но не считается доказательством пользовательского Android boot: nested virtualization на hosted runner не является гарантированным контрактом. Для следующего stable release обязателен отдельный workflow `Windows WHPX Acceptance` на выделенном self-hosted Windows x64 runner с аппаратной виртуализацией и меткой `mobile-research-whpx`. Workflow скачивает `MobileResearchSetup.exe` из `Desktop Build` того же commit SHA, выполняет чистую установку, запускает acceptance через установленный frozen `MobileResearch.exe`, требует именно WHPX по `emulator -accel-check`, загружает private AVD, скачивает зафиксированный Appium ApiDemos v6.0.17 по immutable release URL и проверяет SHA-256 `90cc1041c063a7fb68889143250fefa3139ef0c81e4208f67dbaafe8f15c8be9`, затем именно установленный MobileResearch.exe определяет package через managed aapt2, устанавливает APK через managed ADB и исследует `io.appium.android.apis`. Gate также доказывает root ADB, tcpdump/raw PCAP, framebuffer, logcat, screen recording, complete Research ZIP, checksum verification и semantic audit. Release workflow обязан ждать этот exact-SHA gate и не публикует stable version без его success.


### ADR-047 — Package Manager dump failure degrades evidence instead of aborting capture
A full raw package-manager dump remains required for a `complete` session, but it is not allowed to prevent collection of unrelated high-value evidence. Before the dump, Mobile Research best-effort waits for Package Manager main/background handlers. The primary transport uses bounded `dumpsys -t 30 package <package>`; a bounded `cmd package dump-package` path is the fallback. If neither produces a complete dump, `device_metadata` still writes explicit diagnostic package evidence and normalized metadata, records a non-fatal degradation, and orchestration proceeds to logcat, screen recording and raw PCAP. The final session therefore becomes `partial`, preserving the evidence contract without turning a metadata timeout into a 1–2 KB failed archive.


### ADR-048 — Release acceptance и пользовательская hypervisor-совместимость разделены
WHPX остаётся предпочтительным Microsoft-backed Windows hypervisor и обязательным target dedicated Windows hardware acceptance. Это не означает, что пользовательский runtime должен отвергать уже установленный и usable AEHD/GVM, пока текущий Android Emulator официально поддерживает этот fallback. Если `emulator -accel-check` подтверждает WHPX или AEHD/GVM, Mobile Research продолжает работу без UAC. Автоматическая настройка Windows выполняется только при отсутствии usable hypervisor. Она включает только `HypervisorPlatform` и `hypervisorlaunchtype=Auto` через один elevated PowerShell process; `VirtualMachinePlatform` для Android Emulator не включается. Если изменение Windows требует reboot, приложение обязано сообщить об этом явно, поскольку `/NoRestart`/NoRestart semantics могут не показывать системный prompt.


### ADR-049 — Интерактивный Android использует Emulator gRPC
Штатный desktop path получает непрерывный RGB framebuffer из локального managed Emulator через gRPC и отправляет touch/key input тем же control plane. GUI хранит только последний кадр и публикует его примерно каждые 33 ms, поэтому устаревшие frames не образуют очередь. ADB screenshot/input остаётся compatibility fallback; research collectors по-прежнему независимы от GUI transport.

### ADR-050 — GPU rendering выбирает Emulator
При аппаратном CPU-ускорении managed Emulator использует GPU mode auto. Принудительный SwiftShader удалён из штатного hardware path и сохраняется только для software-only fallback.

### ADR-051 — Clean launch является отдельным research mode
Режим clean останавливает текущий экземпляр target package до preflight, затем запускает collectors и только после перехода capture в ACTIVE запускает APK. Режим continue сохраняет уже существующее состояние приложения. Выбранный режим фиксируется в session event log.
