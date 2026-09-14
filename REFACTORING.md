# Refactoring and Architecture Log

Файл фиксирует архитектурные решения, границы и будущие крупные изменения Mobile Research. Это не журнал каждого мелкого коммита.

## Текущее состояние

**Этап:** v0.7.7 — atomic Android lifecycle + orphan recovery.  
**Stable baseline:** v0.7.7 Desktop Application.  
**Core evidence baseline:** v0.1.0 Research Session Core.  
**Реализовано:** GUI, self-contained Windows distribution, managed Android runtime/AVD, APK install, embedded Android view, Windows provisioning gate и desktop release gates.  
**Принцип:** v0.1.0 raw evidence contract не ослабляется.

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
9. **Real AVD-RESEARCH acceptance run — реализован и автоматизирован.**
10. **Semantic Research ZIP release audit — реализован.**
11. **v0.1.0 release gate — реализован.**

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


### ADR-030 — Крупные Android dumps не идут через capture_output
Полный `dumpsys package` может быть достаточно большим, чтобы текстовый ADB transport завершился нестабильно. Collector направляет stdout команды во временный файл под `/data/local/tmp/mobile-research/<session-id>/`, переносит его через `adb pull`, затем удаляет remote-файл best-effort. Это сохраняет полный raw dump и избегает зависимости от объёма stdout.


### ADR-031 — Screen timing берётся из встроенного Winscope metadata, а не из MP4 duration
Современный Android `screenrecord` пишет data-track `#VV1NSC0PET1ME2#` с elapsed frame timestamps и realtime-to-elapsed offset. Статичный экран может не генерировать новые frames, поэтому playback duration MP4 не обязан совпадать с wall-clock длительностью collector process. Mobile Research сохраняет raw MP4 без изменений и извлекает только summary первого/последнего frame UTC и frame count в `screen.json`.

### ADR-032 — Первый релиз требует semantic audit, а не только ZIP integrity
CRC/SHA-256 доказывают целостность архива, но не достаточность evidence. Release acceptance дополнительно проверяет lifecycle order, collector statuses, clock skew, временное покрытие logcat/PCAP, package launch и screen frame timing. Формально валидный, но семантически неполный Research ZIP не проходит release gate.


### ADR-033 — Release публикуется только после gates exact commit SHA
Release workflow не доверяет предыдущим успешным runs. Он ждёт завершения workflow `CI` и `AVD Research Acceptance` для собственного `GITHUB_SHA`. Только после двух `success` разрешены build/tag/GitHub Release. Это предотвращает публикацию версии, отличающейся от реально протестированного кода.

### ADR-034 — Release assets являются воспроизводимыми Python artifacts
v0.1.0 публикует wheel и sdist, собранные из release commit, плюс `SHA256SUMS.txt`. Research ZIP из acceptance остаётся краткоживущим CI evidence и не превращается в release artifact, поскольку это результат синтетического исследования, а не дистрибутив программы.

### ADR-035 — Release docs являются обязательной частью release commit
Release workflow проверяет, что `README.md`, `REFACTORING.md`, `CHANGELOG.md` и `RELEASE_NOTES.md` содержат выпускаемую версию. Публикация блокируется, если release documentation не синхронизирована с `pyproject.toml`.


### ADR-036 — Desktop GUI является основной границей продукта
Начиная с v0.2 штатный пользовательский интерфейс — `MobileResearch.exe`. CLI сохраняется только для разработки и диагностики. GUI вызывает core classes напрямую и не является текстовой оболочкой над CLI.

### ADR-037 — Пользователь не устанавливает Python
Desktop distribution собирается PyInstaller и устанавливается через Inno Setup. Python runtime и Qt входят в Mobile Research. Пользовательский компьютер не требует Python/pip/venv.

### ADR-038 — Android runtime принадлежит Mobile Research
ADB, Android Emulator, build-tools и system image не считаются внешними пользовательскими зависимостями. Mobile Research загружает официальные Google packages и хранит их в собственном каталоге `%LOCALAPPDATA%\MobileResearch\components`.

### ADR-039 — Android Studio не является зависимостью
Private AVD создаётся программой напрямую из managed system image/config. Android Studio и ручной AVD Manager пользователю не нужны.

### ADR-040 — Android отображается внутри GUI
Google Emulator запускается headless. Mobile Research получает framebuffer через ADB и передаёт input обратно через `input tap/swipe/text/keyevent`. Это отделяет UX от внешнего окна emulator и позволяет позже заменить framebuffer transport без изменения пользовательского контракта.

### ADR-041 — Stable desktop release публикует installer
Начиная с v0.2 основным release asset является `MobileResearchSetup.exe` + SHA-256. Stable publication требует exact-SHA Windows CI, real AVD acceptance и Desktop Build.


### ADR-042 — Managed Android использует только stable repository channel
Desktop provisioning выбирает Android SDK packages только из Google repository `channel-0`. Более новые beta/dev/canary revisions не имеют права автоматически попадать в пользовательский runtime. Это решение принято после того, как выбор не-stable Emulator привёл к отдельному crash на Windows.

### ADR-043 — Windows hosted CI проверяет provisioning, а не неподдерживаемый software boot
GitHub-hosted Windows runner без аппаратной виртуализации не является надёжным Android boot target. Windows gate обязан доказать download/checksum/extraction, executable versions и private AVD creation. Настоящий Android boot/root/tcpdump/Research ZIP остаётся обязательным real AVD gate на KVM. Пользовательский Windows runtime использует аппаратное ускорение/WHPX, а не `-accel off` как штатный fallback.

### ADR-044 — GUI авария не должна бросать уже собранные evidence
Если после старта research session GUI получает неожиданное исключение, controller best-effort вызывает штатный stop/export и публикует partial/failed Research ZIP. Если startup failure уже сформировал failed archive внутри orchestrator, GUI повторно его не экспортирует, а использует существующий архив.

### ADR-045 — Managed Android можно полностью восстановить без ручного удаления файлов
Настройки Mobile Research содержат repair action для удаления только managed Android SDK/Emulator/system image/AVD. Research sessions хранятся отдельно и не удаляются. Следующая подготовка заново скачивает официальные компоненты и проверяет checksums.


### ADR-046 — Windows WHPX hardware acceptance является дополнительным release evidence
GitHub-hosted Windows CI остаётся обязательным для сборки, unit/GUI smoke и чистого provisioning, но не считается доказательством пользовательского Android boot: nested virtualization на hosted runner не является гарантированным контрактом. Отдельный workflow `Windows WHPX Acceptance` на выделенном self-hosted Windows x64 runner с аппаратной виртуализацией и меткой `mobile-research-whpx` сохраняется как дополнительная hardware acceptance. Workflow скачивает `MobileResearchSetup.exe` из `Desktop Build` того же commit SHA, выполняет чистую установку, запускает acceptance через установленный frozen `MobileResearch.exe`, требует именно WHPX по `emulator -accel-check`, загружает private AVD, скачивает зафиксированный Appium ApiDemos v6.0.17 по immutable release URL и проверяет SHA-256 `90cc1041c063a7fb68889143250fefa3139ef0c81e4208f67dbaafe8f15c8be9`, затем именно установленный MobileResearch.exe определяет package через managed aapt2, устанавливает APK через managed ADB и исследует `io.appium.android.apis`. Gate также доказывает root ADB, tcpdump/raw PCAP, framebuffer, logcat, screen recording, complete Research ZIP, checksum verification и semantic audit. Stable publication не блокируется отсутствием или очередью этого self-hosted runner: обязательные exact-SHA gates — CI, Desktop Build и real AVD Research Acceptance. Если WHPX runner доступен, его результат сохраняется как дополнительное evidence и используется для диагностики Windows-specific regressions.


### ADR-047 — Package Manager dump failure degrades evidence instead of aborting capture
A full raw package-manager dump remains required for a `complete` session, but it is not allowed to prevent collection of unrelated high-value evidence. Before the dump, Mobile Research best-effort waits for Package Manager main/background handlers. The primary transport uses bounded `dumpsys -t 30 package <package>`; a bounded `cmd package dump-package` path is the fallback. If neither produces a complete dump, `device_metadata` still writes explicit diagnostic package evidence and normalized metadata, records a non-fatal degradation, and orchestration proceeds to logcat, screen recording and raw PCAP. The final session therefore becomes `partial`, preserving the evidence contract without turning a metadata timeout into a 1–2 KB failed archive.


### ADR-048 — Release acceptance и пользовательская hypervisor-совместимость разделены
WHPX остаётся предпочтительным Microsoft-backed Windows hypervisor и целевым dedicated Windows hardware acceptance. Это не означает, что пользовательский runtime должен отвергать уже установленный и usable AEHD/GVM, пока текущий Android Emulator официально поддерживает этот fallback. Если `emulator -accel-check` подтверждает WHPX или AEHD/GVM, Mobile Research продолжает работу без UAC. Автоматическая настройка Windows выполняется только при отсутствии usable hypervisor. Она включает только `HypervisorPlatform` и `hypervisorlaunchtype=Auto` через один elevated PowerShell process; `VirtualMachinePlatform` для Android Emulator не включается. Если изменение Windows требует reboot, приложение обязано сообщить об этом явно, поскольку `/NoRestart`/NoRestart semantics могут не показывать системный prompt.


### ADR-049 — Интерактивный Android использует Emulator gRPC
Штатный desktop path получает непрерывный RGB framebuffer из локального managed Emulator через gRPC и отправляет touch/key input тем же control plane. GUI хранит только последний кадр и публикует его примерно каждые 33 ms, поэтому устаревшие frames не образуют очередь. ADB screenshot/input остаётся compatibility fallback; research collectors по-прежнему независимы от GUI transport.

### ADR-050 — GPU rendering выбирает Emulator
При аппаратном CPU-ускорении managed Emulator использует GPU mode auto. Принудительный SwiftShader удалён из штатного hardware path и сохраняется только для software-only fallback.

### ADR-051 — Clean launch является отдельным research mode
Режим clean останавливает текущий экземпляр target package до preflight, затем запускает collectors и только после перехода capture в ACTIVE запускает APK. Режим continue сохраняет уже существующее состояние приложения. Выбранный режим фиксируется в session event log.


### ADR-052 — Framebuffer orientation берётся из Emulator rotation metadata
ImageFormat.rotation является частью официального Emulator gRPC protocol. Server уже поворачивает logical screenshot по coarse device orientation, но raw pixel buffer остаётся bottom-up. Для normal portrait/landscape GUI исправляет только bottom-up memory order; для reverse portrait/reverse landscape дополнительно нормализует 180° orientation и инвертирует touch coordinates в input space.

### ADR-053 — GUI не материализует несколько полных копий каждого кадра
v0.3.0 выполнял bytes → QImage.copy → mirrored image → QPixmap → scaled QPixmap на каждом кадре. v0.3.1 хранит owner объекта frame, создаёт QImage поверх его buffer без deep copy и выполняет bottom-up/reverse transform плюс scale непосредственно QPainter-ом. Live stream уменьшен до 360×640 RGBA, что соответствует фактическому размеру embedded view и снижает bandwidth/CPU.

### ADR-054 — Windows GPU host с автоматическим fallback
На hardware-accelerated Windows runtime сначала запускается Emulator с GPU host. Если Emulator не может загрузиться с host backend, runtime автоматически останавливает его и повторяет запуск с GPU auto. Software-emulation path сохраняет SwiftShader.


### ADR-055 — Emulator screenshot уже содержит logical rotation
`ImageFormat.rotation` описывает orientation результата, но Emulator API уже поворачивает screenshot согласно coarse device orientation. Для RGBA/RGB требуется только коррекция documented bottom-up layout. Дополнительная reverse-rotation трансформация v0.3.1 была ошибочной и удалена. При загрузке managed AVD пользовательская ориентация фиксируется в portrait (`wm user-rotation lock 0`) до начала интерактивной работы.

### ADR-056 — Pixel data идут через MMAP, input — через persistent stream
Основной embedded framebuffer transport — `ImageTransport.MMAP`: gRPC несёт metadata/frame notifications, а RGBA framebuffer записывается Emulator напрямую в client-owned memory-mapped file. Это устраняет protobuf allocation/copy полного кадра на каждом refresh. При невозможности MMAP выполняется автоматический fallback на `grpc-bytes`. GUI публикует latest frame с precise timer около 60 Hz. Touch/key events идут через один длительно живущий `streamInputEvent`; unary sendTouch/sendKey остаются fallback.

### ADR-057 — Windows использует Android-Studio-style hidden Qt Emulator
На аппаратно ускоренном Windows managed Emulator запускается с `-qt-hide-window`, сохраняя Qt graphics path без внешнего окна. Это соответствует embedded режиму Android Studio. Linux/KVM acceptance и software-only fallback продолжают использовать `-no-window`.


### ADR-058 — Windows interactive display использует native Emulator HWND
Требование пользовательского UX — плавность интерфейса, сопоставимая с обычным Android Emulator/телефоном. Screenshot-based paths (ADB PNG, gRPC bytes, MMAP framebuffer) сохраняют дополнительную стадию capture/mirror/presentation и не могут гарантировать тот же visual cadence, что собственное окно Emulator. На Windows Mobile Research поэтому использует настоящий Qt window Android Emulator: окно запускается скрытым через `-qt-hide-window`, после boot Mobile Research находит HWND процесса/его descendants, удаляет top-level chrome, выполняет `SetParent` в native QWidget и синхронизирует размер через Win32. Mouse/keyboard попадают непосредственно в Emulator child window. MMAP/gRPC framebuffer остаётся fallback при невозможности attach.

### ADR-059 — Research transport отделён от display transport
Переход на native HWND не меняет evidence contract. ADB, root, logcat, tcpdump, screenrecord, package metadata, Research ZIP и gRPC control остаются независимыми от способа визуального отображения Android. Native display можно отключить/потерять без остановки collectors; GUI автоматически возвращается к framebuffer fallback.


### ADR-060 — Сбой native Emulator display не блокирует Research Target
Реальный Windows-тест v0.5.0 показал, что Android Emulator/QEMU может аварийно завершиться ещё во время boot при использовании native Qt/GPU display path. Display transport не имеет права становиться single point of failure для research core. Windows managed boot поэтому использует последовательность профилей: native HWND + host GPU → headless + host GPU → headless + SwiftShader. После первой успешной загрузки выбранный профиль сохраняется на весь текущий runtime. Headless-профиль автоматически использует MMAP/gRPC/ADB framebuffer stack, а native HWND attach для него не выполняется. Все неуспешные попытки фиксируются в diagnostics вместе с GPU/display mode, duration, exit code, error и полной Emulator command line. Managed Emulator запускается с `-crash-report-mode disabled`, поскольку внутренний Google crash-report dialog не является частью пользовательского интерфейса Mobile Research; ошибка остаётся в локальной диагностике и инициирует автоматический fallback.


### ADR-061 — `-qt-hide-window` не является контрактом native HWND embedding
Реальный тест v0.5.1 показал ложный успех Win32 embedding: Mobile Research находила Qt HWND процесса Emulator, выполняла `SetParent` и считала display подключённым, но Android pixels в этом HWND не отображались. Официальный embedded режим Android Emulator использует `-qt-hide-window` совместно с control/framebuffer transport; скрытый Qt HWND не рассматривается как поддерживаемая внешняя native video surface. Поэтому stable runtime больше не активирует NativeEmulatorEmbedder и не останавливает framebuffer stream из-за существования такого HWND. На Windows основной display contract снова: `-qt-hide-window` + gRPC MMAP → gRPC bytes → ADB screenshot fallback. Win32 `SetParent` код остаётся изолированным экспериментом и не входит в stable path до появления отдельного доказательства корректной видеоотрисовки на реальном Windows hardware.


### ADR-062 — Native display использует только реальное standalone-окно Emulator
Для нативной плавности v0.6.0 запускает основной Windows profile без `-qt-hide-window` и без `-no-window`. Mobile Research ищет только видимое top-level окно Emulator сразу после создания процесса и переподчиняет именно его. Attach считается успешным только после проверки `SetParent`, фактического parent HWND, ненулевой client area и видимости. До подтверждения framebuffer stream не отключается; при ошибке native attach gRPC/MMAP продолжает работу.

### ADR-063 — Reverse framebuffer rotation снова нормализуется
Реальный тест v0.5.2 показал reverse-portrait первый кадр. Для raw bottom-up RGBA/RGB кадров rotation 2/3 снова трактуется как reverse orientation: применяется коррекция, эквивалентная bottom-up flip + 180-degree normalization, а input ratios инвертируются по обеим осям.


### ADR-064 — GitHub Release хранит дистрибутивы, Actions artifacts являются эфемерными
Постоянным хранилищем пользовательских бинарников считаются только GitHub Releases. Успешные AVD/provisioning/WHPX acceptance runs не создают диагностические Actions artifacts; их статус и стандартные Actions logs достаточны для подтверждения gate. При failure диагностические evidence artifacts сохраняются на 3 дня. Единственный успешный временный artifact — `mobile-research-windows-desktop` с проверенным installer и SHA-256 — создаётся только для release-candidate commit, имеет retention 1 день, используется Release workflow для публикации и удаляется API-вызовом сразу после успешного GitHub Release. Windows WHPX Acceptance больше не зависит от этого artifact и скачивает `MobileResearchSetup.exe` и `SHA256SUMS.txt` непосредственно из уже опубликованного exact-SHA GitHub Release; тем самым аппаратный gate проверяет тот же EXE, который получает пользователь.


### ADR-065 — DWM live composition заменяет cross-process SetParent
Реальный тест v0.6.0 доказал, что Mobile Research находит правильный standalone Qt HWND Android Emulator, но после cross-process `SetParent` GPU surface становится чёрной; при возврате окна к top-level состоянию изображение снова появляется. Поэтому `SetParent` исключён из active display path. Начиная с v0.7.0 Emulator остаётся самостоятельным top-level GPU window, а Mobile Research регистрирует его через `DwmRegisterThumbnail` в собственном top-level HWND и обновляет `DWM_THUMBNAIL_PROPERTIES.rcDestination` по геометрии AndroidView. DWM API требует top-level source и destination, что соответствует новой архитектуре. После успешной регистрации source window перемещается за пределы virtual desktop, но не скрывается/минимизируется; при shutdown оно не восстанавливается, чтобы исключить визуальную вспышку. Input остаётся через Emulator gRPC. При ошибке DWM используется существующий gRPC/MMAP → gRPC bytes → ADB fallback.


### ADR-066 — Release-candidate artifact определяется release commit contract
Попытка определять release-candidate сравнением версии с parent через `git show` оказалась ненадёжной в GitHub Actions checkout и дала false negative для v0.7.1. Поскольку проект уже имеет формальный commit-driven release contract, временный `mobile-research-windows-desktop` artifact создаётся только на push в main, если head commit message начинается с `Release Mobile Research v`. Обычные коммиты не создают installer artifacts. Release workflow по-прежнему удаляет этот однодневный artifact сразу после публикации.


### ADR-067 — DWM source window постоянно исключено из пользовательского desktop UX
Реальный тест v0.7.2 подтвердил плавность DWM live, но показал, что однократного `SetWindowPos` недостаточно: Qt/Emulator позднее меняет geometry и source window снова появляется на рабочем столе. v0.7.3 сохраняет source как visible/non-minimized top-level GPU window, но каждые 100 ms перемещает его полностью за правую границу всего Windows virtual desktop. Дополнительно source получает `WS_EX_TOOLWINDOW` и теряет `WS_EX_APPWINDOW`, поэтому не участвует в taskbar/Alt+Tab. Это не меняет parent, размер или GPU surface. При shutdown порядок строго обратный прежнему: сначала `runtime.stop()` завершает Emulator при ещё зарегистрированном DWM thumbnail, затем thumbnail удаляется. Это исключает вспышку standalone окна при закрытии Mobile Research.


### ADR-068 — DWM source остаётся на active desktop и скрывается покрывающим top-level окном
Реальный тест v0.7.3 показал, что полное перемещение standalone Emulator за пределы virtual desktop приводит к чёрному DWM thumbnail: Qt/GPU surface перестаёт нормально обновляться для DWM. Поэтому source window сохраняется visible/non-minimized на active desktop, но каждые 100 ms позиционируется полностью внутри screen rectangle Mobile Research и ставится непосредственно за его top-level HWND через `SetWindowPos(source, destination_hwnd, ...)`. При нехватке места source пропорционально уменьшается, чтобы ни одна его граница не могла выступить из-под Mobile Research. `WS_EX_TOOLWINDOW`/отсутствие `WS_EX_APPWINDOW` сохраняют отсутствие source в taskbar/Alt+Tab. При minimize covering window source временно скрывается; при restore сначала восстанавливаются geometry/z-order, затем source показывается без activation.

### ADR-069 — DWM thumbnail visibility управляется выбранной Qt-вкладкой
DWM thumbnail композитится в top-level HWND и не является дочерним Qt widget, поэтому QTabWidget не может автоматически clip/hide его. Начиная с v0.7.4 `tabs.currentChanged` явно переключает `DWM_THUMBNAIL_PROPERTIES.fVisible`: только индекс вкладки Исследование имеет visible=true. Это исключает наложение Android изображения поверх Настроек, Диагностики, Истории и Результатов.


### ADR-070 — Pointer drag передаётся как реальный touch lifecycle
Прежний AndroidView отправлял swipe только в `mouseReleaseEvent`, поэтому Android не получал движения до отпускания кнопки. Начиная с v0.7.5 mouse press немедленно создаёт gRPC touch DOWN, mouse move во время удержания генерирует последовательность MOVE с pressure=1, а release отправляет финальный MOVE и UP с pressure=0. MOVE ограничен интервалом 12 ms (~83 Hz), чтобы не создавать backlog на высокочастотной мыши. Controller и AndroidRuntime получили отдельные `touch_down/touch_move/touch_up`; EmulatorGrpcClient отправляет их в уже существующий persistent `streamInputEvent`. ADB fallback при отсутствии gRPC по-прежнему сводит жест к tap/swipe на release.

### ADR-071 — DWM source создаётся скрытым и показывается только после установки z-order
Даже 15-ms polling оставлял короткую вспышку standalone Emulator до того, как source HWND успевал оказаться за Mobile Research. В DWM-live Windows launch v0.7.5 передаёт `STARTUPINFO.dwFlags |= STARTF_USESHOWWINDOW` и `wShowWindow=SW_HIDE`. NativeEmulatorEmbedder ищет top-level source независимо от текущего visibility, устанавливает TOOLWINDOW/z-order/geometry за Mobile Research и только затем показывает source через `SW_SHOWNOACTIVATE`. Discovery polling сокращён до 5 ms для Emulator builds, которые частично игнорируют startup show state.


### ADR-072 — DWM source выбирается по identity, а не только по PID ancestry
Реальный тест v0.7.5 выявил race: STARTUPINFO/SW_HIDE скрывал главное окно Emulator, а `find_emulator_window(require_visible=False)` мог выбрать другой top-level Qt/helper HWND того же процесса/descendant process. DWM тогда композитил белую helper surface, а настоящее окно Emulator оставалось отдельно. v0.7.6 отменяет hidden process startup и снова ищет visible top-level source. Среди кандидатов приоритетный pool формируется только из окон, title которых содержит `Android Emulator` или имя managed AVD; PID ancestry используется лишь как дополнительный сигнал. После точной идентификации source мгновенно скрывается, позиционируется за Mobile Research и показывается через `SW_SHOWNOACTIVATE` до DWM registration. Это сохраняет нормальную GPU surface и одновременно сокращает видимую startup-вспышку.


### ADR-073 — Reset не удаляет userdata работающего/завершающегося AVD
Реальный тест v0.7.6 выявил race: `reset_userdata()` вызывал `stop()`, после чего `ComponentManager.reset_avd_userdata()` сразу удалял содержимое AVD. Launcher Emulator мог уже изменить состояние, но qemu child и single-instance lock ещё оставались живы. v0.7.7 отказывается от ручного удаления runtime AVD-файлов. Reset сначала полностью завершает managed AVD, затем создаёт persistent marker `reset-userdata.pending`. Следующий owned boot получает официальный параметр `-wipe-data`; marker удаляется только после успешного boot. Это сохраняет reset intent через рестарт приложения и исключает удаление файлов под живым Emulator.

### ADR-074 — Mobile Research владеет единственным экземпляром private AVD
Private AVD `mobile_research_api35` не должен переживать процесс Mobile Research. `stop()` теперь ждёт ADB offline и завершение launcher; на Windows после grace period дополнительно завершаются только `emulator.exe`/`qemu-system-*.exe`, command line которых содержит имя private AVD. При startup online `emulator-5554` без owned Popen считается orphan предыдущего crash и сначала завершается. Это предотвращает `Another emulator instance is running` без вмешательства в любые сторонние Android Emulator пользователя.

### ADR-075 — Reset инвалидирует display/controller state
DWM thumbnail, native-display flag и framebuffer state относятся к конкретному Emulator process lifetime. Reset/repair теперь сначала detach DWM, затем `suspend_display()`: native flag=false, screen worker stop, latest frame очищен. После wipe package state также сбрасывается, потому что APK физически больше не установлен. Нельзя переносить display/package state через уничтожение AVD.
