# Mobile Research

Mobile Research — Windows-система для воспроизводимого исследования сетевой активности Android-приложений в управляемой исследовательской среде.

## Статус

Проект находится на этапе **v0.1 — Research Session Core**. Функциональная версия ещё не реализована.

Первая цель проекта: провести одну воспроизводимую исследовательскую сессию на Android target и получить архив с исходными диагностическими данными.

## Архитектурные принципы

- Главный управляющий компонент работает на Windows.
- Android рассматривается как заменяемый **Research Target**.
- Первичный target для v0.1 — исследовательский Android Emulator.
- Исходные данные исследования сохраняются отдельно от производных результатов.
- Raw network capture является обязательным источником данных; HTTP/MITM в будущем дополняет его, но не заменяет.
- Android Research Agent не является обязательной частью архитектуры и в v0.1 отсутствует.
- GUI, MITM, статический анализ APK, AVD-PLAY и Physical Device не входят в v0.1.

## v0.1: минимальный рабочий сценарий

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

Архитектурные решения и границы проекта: [REFACTORING.md](REFACTORING.md).

## Структура исходного кода

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
- Android Debug Bridge (ADB) будет внешней runtime-зависимостью.
- На первом этапе интерфейс — CLI; GUI появится после стабилизации Research Session Core.

## Следующая реализация

Первый функциональный модуль — **ADB Target Manager**: обнаружение ADB, перечисление targets, определение emulator/physical, получение версии Android и основных параметров устройства.

## CI

CI запускается автоматически на каждый push и pull request. Ручной запуск workflow намеренно не используется.
