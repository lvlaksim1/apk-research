# Project Rules

- Canonical product name is `apk-research`.
- Normal user workflow is GUI-first and standalone; no external Python installation is required.
- Android Emulator/runtime is managed by the application.
- v0.10.5 clean-launch/startup ordering is the proven baseline.
- Avoid fallback chains that mask a broken primary runtime path; repair the primary path systematically.
- Raw PCAP is source of truth for network evidence.
- Package/socket attribution strength and temporal action correlation must remain explicitly separated.
- Action ↔ Flow correlation is `temporal-only`; no causal claim without stronger evidence.
- QUIC/HTTP3 classification must be evidence-driven and regression-protected.
- Final installer filenames contain the version.
- Stable releases are commit-triggered; do not manually bypass release gates.
- Remove temporary verification workflows/artifacts from final product state.
- Prefer public repositories where practical and keep repository state free of unnecessary artifacts.
- Use real Research ZIP evidence to validate user-visible forensic behavior when available.
- Manager state is authoritative only on `context`; `main` is product authority plus discovery bootstrap.
- Never persist credentials, tokens, cookies, private keys or hidden reasoning in Context Capsule.

## Основная рабочая среда (OWNER-LOCAL-FIRST-2026-10-30)

Основная разработка и хранение капсулы выполняются на DOMKAT, в каталоге D:\Dev. GitHub используется для истории версий, синхронизации и резервного восстановления, но прямая разработка в GitHub допускается как исключение. Сохранять полномочия веток продукта и менеджера, проверять целостность капсулы, расхождения Git и неопубликованные локальные изменения. Подробности в файле .context/rules/local-first-workspace.md.

## Стандарт пакетной разработки (OWNER-BATCH-EXECUTION-2026-10-30)

Выполнять разработку по правилу Владельца 30.10.2026: одна стадия планирования моделью, один исполняемый пакет операций на DOMKAT, один содержательный итоговый отчёт. GUI-операции примерно через одну секунду; PowerShell/CMD/Git/файлы без искусственных пауз. Неожиданная ошибка возвращается модели для оценки; остановка всей работы или обращение к Владельцу производится только по обоснованной необходимости. Подробный норматив: .context/rules/batch-development-standard.md. Правило не изменяет полномочия менеджера и существующие ограничения.


## Принцип приоритета возможностей (OWNER-POSSIBILITY-FIRST-2026-10-30)

Сначала исследовать способы достижения цели Владельца, включая комбинации механизмов, протоколов, API и локальных инструментов; незнание способа, отсутствие готовой функции или чужой неподтверждённый отрицательный опыт не являются доказательствами невозможности. Приоритет имеют спецификации, исходники и собственные воспроизводимые эксперименты. Не объявлять задачу невозможной до предметного анализа применимых вариантов и проверок. Чётко отличать гипотезу от подтверждённой реализации. Соблюдать безопасность, полномочия и целостность данных. Полный стандарт: .context/rules/possibility-first-research.md.
