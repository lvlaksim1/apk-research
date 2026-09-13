# Refactoring and Architecture Log

Файл фиксирует архитектурные решения, границы и будущие крупные изменения Mobile Research. Это не журнал каждого мелкого коммита.

## Текущее состояние

**Этап:** v0.1 — Research Session Core  
**Реализовано:** ADB Target Manager, Session Manager, Device/System Metadata Collector.  
**Следующий модуль:** Logcat Collector.

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

## Порядок реализации v0.1

1. **ADB Target Manager — реализован.**
2. **Session Manager и state machine — реализован.**
3. **Device/system metadata collector — реализован.**
4. Logcat collector.
5. Screen recording collector.
6. Raw network collector.
7. Export/checksum subsystem.
8. End-to-end acceptance test.

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
