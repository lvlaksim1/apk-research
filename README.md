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
- proxy/MITM не участвуют в capture;
- stderr `tcpdump` сохраняется отдельно;
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

## CLI

```powershell
mobile-research targets
mobile-research targets --json
mobile-research target-info emulator-5554 --json
mobile-research package-check emulator-5554 com.example.app

mobile-research session-create emulator-5554 com.example.app --json
mobile-research metadata-collect "C:\path\to\session" --json
mobile-research session-status "C:\path\to\session" --json
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

**Export/Checksum subsystem** — SHA-256 evidence, валидация обязательных artifacts и формирование Research ZIP.

## CI

CI автоматически запускается на push и pull request. Ручной запуск workflow не используется.
