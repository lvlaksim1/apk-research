# Mobile Research v0.8.9

v0.8.9 исправляет три системные проблемы, обнаруженные при анализе реального Research ZIP, созданного v0.8.8.

## 1. Package metadata без 40-секундного зависания

Исправлена remote-shell quoting для session-scoped package dump. Вместо ошибочного `cmd package dump-package` используется валидный `cmd package dump <package>` с жёстко ограниченным по времени `dumpsys -t 5 package <package>` fallback.

Дополнительно сохраняется lightweight `cmd package list packages --show-versioncode`. Полный verbose dump остаётся полезным raw evidence, но его отсутствие больше не делает качественную сессию `partial`: diagnostic сохраняется, versionCode берётся из lightweight source, остальные collectors продолжают работу.

## 2. Настоящий clean launch

В режиме `clean` package больше не force-stop'ится до долгого preflight. Теперь порядок жёсткий:

`preflight → arm logcat/screen/PCAP → ACTIVE → force-stop → verify process gone → launch`

Если package не исчез после force-stop либо Android сообщает `Activity not started ... currently running`, clean launch считается нарушенным и сессия завершается с явной ошибкой.

## 3. Точная screen timing model

Raw MP4 остаётся неизменным evidence. В `screen.json` отдельно фиксируются:

- host/target границы жизни процесса `screenrecord`;
- `capture_span_seconds` — wall-clock coverage collector;
- Winscope elapsed frame timestamps;
- realtime-to-elapsed offset;
- UTC первого/последнего фактического кадра;
- presentation/frame span.

Статичный экран может не генерировать новые frames, поэтому MP4 presentation span не обязан совпадать с wall-clock временем recorder process. Semantic audit теперь проверяет оба слоя отдельно и требует, чтобы recorder process покрывал launch и STOP.

## Runtime

Windows display/input architecture не изменена:

`-qt-hide-window → Emulator gRPC → MMAP → AndroidView`

Input: persistent gRPC `streamInputEvent`.

Никакие display/input fallback-механизмы не возвращены.
