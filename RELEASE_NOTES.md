# Mobile Research v0.9.0

v0.9.0 начинает следующий продуктовый этап после стабилизации Research Session Core: **User Actions + unified Research Timeline**.

## User Actions

Во время ACTIVE-сессии Mobile Research теперь сохраняет `02_normalized/user-actions.jsonl`.

Фиксируются:

- click/tap;
- pointer swipe/drag как одно semantic action с start/end coordinates и duration;
- wheel swipe;
- Android navigation/key events;
- текстовый ввод.

Высокочастотные touch MOVE остаются транспортной деталью gRPC и не засоряют timeline отдельными записями.

Текст, введённый через встроенный Android, сохраняется в локальном Research ZIP. Поэтому Research ZIP следует считать потенциально чувствительным evidence.

## Unified Research Timeline

При завершении сессии создаётся `02_normalized/research-timeline.json`.

Timeline объединяет:

- lifecycle events;
- user actions;
- первые наблюдения network flows;
- DNS query markers;
- best-effort TLS ClientHello SNI.

Для каждого user action строится correlation window и сохраняются:

- packet count и captured bytes;
- наиболее активные flow tuples;
- новые flows, появившиеся рядом с действием;
- DNS queries;
- TLS SNI, если ClientHello доступен целиком в packet payload;
- релевантный logcat sample и общее число logcat entries в окне.

Raw PCAP, raw logcat и raw MP4 остаются первичными evidence и не изменяются.

## Clock alignment

User actions возникают на Windows, а PCAP/logcat timestamps принадлежат Android target. Timeline использует сохранённые host/target clock markers и вычисляет `target_minus_host_seconds`. Корреляция выполняется уже в target clock domain, а не простым сравнением несинхронизированных часов.

## GUI

На вкладке «Результаты» появилась кнопка **Research Timeline**. Она открывает timeline выбранного Research ZIP без ручной распаковки архива.

## Acceptance

Real AVD Research Acceptance теперь не только создаёт complete Research ZIP, но и записывает реальные swipe actions и требует, чтобы semantic audit подтвердил наличие user actions и объединённых timeline events.

## Runtime

Embedded Android contract не изменён:

`-qt-hide-window → Emulator gRPC → MMAP → AndroidView`

Input transport остаётся persistent gRPC `streamInputEvent`. Никакие display/input fallback-механизмы не возвращены.
