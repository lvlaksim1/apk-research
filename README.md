# Mobile Research

Mobile Research — Windows-система для воспроизводимого исследования сетевой активности Android-приложений в управляемой исследовательской среде.

## Статус

Проект находится на этапе **v0.1 — Research Session Core**.

Реализованы:

- **ADB Target Manager**
- **Session Manager**
- **Device/System Metadata Collector**
- **Logcat Collector**
- **Screen Recording Collector**
- **Raw Network Collector**
- **Export / Checksums / Research ZIP**
- **End-to-end Session Orchestrator**

Первая end-to-end цель: провести одну воспроизводимую исследовательскую сессию на Android target и получить архив с исходными диагностическими данными.

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
- raw `dumpsys package <package>`;
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
- `02_normalized/screen.json` содержит хронологию chunks, команды, return codes, remote PID, timestamps и размеры.

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

**Real AVD-RESEARCH acceptance run** — запуск полного цикла на настоящем Android Emulator с root/tcpdump и проверка полученного Research ZIP.

## CI

CI автоматически запускается на push и pull request. Ручной запуск workflow не используется.
