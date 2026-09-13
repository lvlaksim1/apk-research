# Refactoring and Architecture Log

Файл фиксирует архитектурные решения, границы и будущие крупные изменения Mobile Research. Это не журнал каждого мелкого коммита.

## Текущее состояние

**Этап:** v0.1 — Research Session Core  
**Реализовано:** ADB Target Manager, Session Manager, Device/System Metadata Collector, Logcat Collector, Screen Recording Collector, Raw Network Collector, Export/Checksum subsystem, End-to-end Session Orchestrator.  
**Следующий этап:** реальный AVD-RESEARCH acceptance run.

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
9. Real AVD-RESEARCH acceptance run.

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
