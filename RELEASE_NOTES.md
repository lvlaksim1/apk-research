# Mobile Research v0.8.8

v0.8.8 завершает technical cleanup runtime-слоя после успешного реального теста v0.8.7.

## Что подтверждено реальным тестом

- Android Emulator загружается внутри Mobile Research;
- отдельное окно Emulator не используется;
- gRPC/MMAP framebuffer работает штатно;
- Root, PCAP и APK readiness завершаются успешно;
- текущая display/input architecture не требует compatibility fallback.

## Cleanup

- удалено неиспользуемое pointer-state поле из `AndroidView`;
- удалены мёртвые `DesktopController.session_root` и `_thread_quiet`;
- удалены неиспользуемые `AndroidRuntime.emulator_pid` и GUI `_last_gpu_mode`;
- убран package-level monkeypatch Android repository selector;
- `components.py` теперь напрямую делегирует выбор архива единой stable repository policy;
- удалён дублирующий старый XML parser;
- добавлен regression contract, запрещающий возврат DWM/native/ADB-display fallback и `workflow_dispatch`.

## Runtime contract не изменён

Windows: `-qt-hide-window → Emulator gRPC → MMAP → AndroidView`.

Input: `AndroidView → persistent gRPC streamInputEvent → Android`.

Private-AVD stale-process cleanup и один `-wipe-data` при guest boot stall остаются recovery того же runtime, а не альтернативными режимами.

После этого релиза runtime technical cleanup считается завершённым. Следующий этап разработки — User Actions + Research Timeline.
