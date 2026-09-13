# Mobile Research

Mobile Research — Windows-система для воспроизводимого исследования сетевой активности Android-приложений в управляемой исследовательской среде.

## Статус

Проект находится на этапе **v0.1 — Research Session Core**.

Реализован первый функциональный модуль: **ADB Target Manager**.

Первая end-to-end цель проекта: провести одну воспроизводимую исследовательскую сессию на Android target и получить архив с исходными диагностическими данными.

## Архитектурные принципы

- Главный управляющий компонент работает на Windows.
- Android рассматривается как заменяемый **Research Target**.
- Первичный target для v0.1 — исследовательский Android Emulator.
- Исходные данные исследования сохраняются отдельно от производных результатов.
- Raw network capture является обязательным источником данных; HTTP/MITM в будущем дополняет его, но не заменяет.
- Android Research Agent не является обязательной частью архитектуры и в v0.1 отсутствует.
- GUI, MITM, статический анализ APK, AVD-PLAY и Physical Device не входят в v0.1.

## Реализовано

### ADB Target Manager

Умеет:

- находить ADB через явный путь, PATH, ANDROID_SDK_ROOT, ANDROID_HOME или стандартный Windows Android SDK path;
- перечислять targets из `adb devices -l`;
- сохранять состояния `device`, `offline`, `unauthorized`;
- определять emulator/physical для готового target;
- получать Android release, SDK level, manufacturer, model, ABI, build fingerprint и текущий root status;
- проверять наличие package на target;
- выдавать данные в обычном или JSON-формате.

Примеры:

```powershell
mobile-research targets
mobile-research targets --json
mobile-research target-info emulator-5554 --json
mobile-research package-check emulator-5554 com.example.app
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

## Структура

```text
src/mobile_research/
├── targets/
├── session/
├── collectors/
└── export/
```

## Среда разработки

- Windows — целевая host-платформа.
- Python >= 3.11.
- Android Debug Bridge (ADB) — внешняя runtime-зависимость.
- На первом этапе интерфейс — CLI.

Установка для разработки:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Следующий этап

**Session Manager**: session ID, state machine, runtime layout, manifest и безопасное завершение/сохранение partial session.

## CI

CI автоматически запускается на push и pull request. Ручной запуск workflow не используется.
