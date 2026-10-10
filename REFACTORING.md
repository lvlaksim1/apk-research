# Refactoring and Architecture Log

## v0.32.0 — Сетевой маршрут выбранного Android-приложения

Ранее HTTPS-анализатор получал только данные приложений, учитывающих системный прокси. Добавлен независимый путь для прямых IPv4 TCP/443-соединений выбранного приложения: Android UID считывается из менеджера пакетов; таблица `nat` направляет только трафик этого UID и порта на локальный служебный модуль в эмуляторе. Модуль считывает исходный IP и порт через `SO_ORIGINAL_DST`, устанавливает HTTP CONNECT к прежнему HTTPS-анализатору через `adb reverse` и прозрачно передаёт сетевые данные в обе стороны. Сертификаты, существующий анализатор, окно HTTP/HTTPS и форматы записей запросов/ответов не меняются.

Сетевое правило применяется перед штатным запуском исследуемого приложения и снимается до остановки анализатора; обработка прерванного запуска также удаляет созданные правила. Служебный модуль компилируется из исходного кода официальным Android NDK во время Linux и Windows сборок и включается в исполняемый файл. В RAW-раздел Research ZIP добавлен собственный журнал соединений, в метаданные — использованный маршрут и UID. Источником самостоятельных сетевых пакетов остаётся RAW PCAP, а факт анализа HTTPS фиксируется отдельно.

Реальное AVD-испытание проверяет обычный HTTPS-запрос и HTTPS-запрос с явным `Proxy.NO_PROXY`. Проверяется наличие обеих транзакций, непустых ответов и записи о прямом соединении в диагностическом журнале.

Ограничения: IPv4 TCP/443; не заявляется чтение QUIC/UDP, обход собственных решений доверия сертификатам или универсальная работа с любым сторонним приложением. Прежний Android 15 Default/Google APIs AVD, gRPC/MMAP, RAW PCAP, XAPK/OBB и обновление из GitHub сохраняются.


## v0.31.0 — Отдельный Android 15 Google APIs для ARM64

Текущий Default/x86_64 AVD сохраняется без изменения данных. Новый Google APIs/x86_64 AVD хранится под собственным именем и в отдельном каталоге, используя общие инструменты SDK. Для ARM-only APK/XAPK предзагрузочный анализ `aapt2` выбирает совместимый профиль до старта трансляции изображения gRPC/MMAP. Профиль записывается долговременно только после успешной загрузки Android и проверки наличия `arm64-v8a` в `ro.product.cpu.abilist`.

Исключены слепое отключение проверки ABI и принудительная замена нативных библиотек. Проверка должна доказать успешную загрузку ARM64 JNI-кода внутри реального Android 15. RAW PCAP, Research ZIP, виртуальный экран и сетевой анализ не меняются.


## v0.30.0 — Managed HTTPS traffic inspection

### Active-interception boundary

HTTPS visibility is implemented as a separate active collector rather than by pretending encrypted PCAP payload is plaintext. apk-research launches an isolated bundled mitmproxy worker, exposes it only through host loopback, connects the managed AVD with `adb reverse`, and applies an explicit Android proxy setting for the session.

### Android 15 trust boundary

The rooted AVD temporarily receives the research CA in the system trust view used by Conscrypt. For APEX-based Conscrypt, the writable certificate view is propagated into Zygote mount namespaces so newly launched applications can inherit it. Teardown restores the previous proxy, removes the reverse mapping and removes the temporary CA view.

### Evidence boundary

Decrypted transactions and bodies are derived active-interception evidence stored separately from `01_raw/network/traffic.pcap`. The PCAP remains authoritative for traffic actually observed in the intercepted research environment. Interception provenance explicitly records that the proxy may alter protocol selection, particularly QUIC/HTTP3.

### Product boundary

The desktop exposes a dedicated HTTP/HTTPS viewer with URL/method/status, headers and request/response bodies. v0.30.0 does not silently patch certificate pinning or custom trust stores and does not claim HTTP/3 decryption.

### Release acceptance

A real Android 15 AVD test installs a launchable APK, performs a genuine HTTPS request, and requires the exported transaction to contain the exact HTTPS URL, a decrypted TLS marker, HTTP 200 and a non-empty response body. Windows packaging separately starts the HTTPS worker from the built standalone executable and requires it to create its CA and reach ready state.

## v0.29.2 — MailRu-style installer/update split

The previous single-installer design mixed first-install and update responsibilities. v0.29.2 adopts the already operating MailRu Desktop separation.

### Full installer
`packaging/full.iss` performs the first installation into the fixed per-user application directory and owns normal Start-menu/optional desktop shortcuts.

### Update installer
`packaging/update.iss` shares the same AppId and file set, refuses to start when the existing apk-research executable is absent, updates files in place, and recreates shortcuts. It never invokes the previous uninstaller.

### Application handoff
The application downloads only the dedicated Update asset, keeps SHA-256 verification, calls the Windows shell directly to launch the installer, and exits. There is no PowerShell relay, detached waiter, custom installer argument protocol or application-owned relaunch orchestration.

### Release contract
Every stable GitHub Release must contain the full installer, update installer and one SHA256SUMS file that validates both binaries.

### UI boundary
The explicit Android Home button is removed; it is not part of the supported desktop workflow.

## v0.29.1 — Reliable update process handoff

### Direct-installer invariant

The application no longer creates a detached PowerShell script/process to wait, install and restart. After release integrity verification, apk-research starts the verified Inno Setup executable directly as an independent Windows child process and then exits.

### Relaunch ownership

Inno Setup owns the successful relaunch. In update mode, a dedicated `[Run]` entry starts the installed `apk-research.exe` after files have been updated successfully. `/NORELAUNCH=1` exists only for automated acceptance where the launched GUI would interfere with verification.

### Diagnostic invariant

The updater writes a handoff record and passes a persistent `/LOG` path to Inno Setup under the user's local application-data directory. A failed update therefore leaves post-mortem evidence even after the GUI has closed.

### Parent-exit acceptance

Windows CI verifies the exact failure mode reported by the owner: previous release installed, updater launched through production Python code, initiating Python process exits, then the installed executable is polled no faster than every five seconds until the candidate version is observed or the check fails with installer/handoff logs.

### Compatibility boundary

Release discovery, SHA-256 verification, same-AppId in-place installation, APK/XAPK runtime, evidence collection and forensic semantics are unchanged.

## v0.29.0 — Corrective package/runtime UX

### ABI-selection invariant

Before an XAPK install, apk-research reads the emulator ABI list from Android properties and inspects `native-code` from every APK through `aapt2 dump badging`. APK parts whose native libraries do not intersect the emulator ABI set are excluded from the install transaction. A base APK with incompatible native code, or an XAPK whose native ABI set has no emulator match, is rejected before installation with explicit diagnostics.

### Explicit install invariant

Selecting a file does not imply installation. The desktop UI exposes installation, launch and Android-home actions separately. Research cannot start until the selected package has been successfully installed.

### Icon invariant

A single project-owned icon design (phone + Android + magnifier) is generated during Windows packaging and is used by the Qt application, PyInstaller executable, Inno Setup package and resulting shortcuts.

### In-place update invariant

The updater does not invoke the old uninstaller. It launches the verified release installer with `/UPDATE=1`. Inno Setup reuses the previous application directory/group/tasks under the same AppId. Research data and QSettings live outside the program file set and are not removed by this update path.

### Compatibility boundary

Research capture, gRPC/MMAP display/input, v0.10.5 startup sequencing, Research ZIP schemas, RAW PCAP and all evidence semantics are unchanged.

## v0.28.0 — Direct GitHub Self-Update

### Scope boundary

v0.28 changes only application maintenance outside a research session. It does not modify Android runtime, capture, APK/XAPK installation, Research ZIP generation or evidence interpretation.

### Explicit-check invariant

The application does not poll GitHub in the background. Release discovery occurs only when the user presses «Проверить обновления». The request targets the public `releases/latest` endpoint for `lvlaksim1/apk-research`.

### Release-identity invariant

An update is offered only when the returned stable tag parses as a strict three-component version and is newer than the running version. The release must contain the exact `apk-research-setup_v<version>.exe` asset and `SHA256SUMS.txt`, both hosted under the project GitHub release path.

### Integrity invariant

The installer is staged in a temporary local directory. apk-research downloads `SHA256SUMS.txt`, hashes the installer itself with SHA-256 and refuses installation if file size or digest disagrees with the published release metadata/checksum file.

### Process-handoff invariant

The running executable never attempts to overwrite itself. After verification it starts a detached PowerShell handoff which waits for the current apk-research PID to exit, runs the verified Inno Setup package silently into the same installation directory, then restarts the installed executable.

### Failure boundary

Any network, release-shape, download, size, checksum or installer-launch failure leaves the current installation running/unchanged and is surfaced in Settings. An update cannot start while research or another managed operation is active.

### Compatibility boundary

v0.27 APK/XAPK intake, hidden Emulator → gRPC/MMAP → AndroidView, v0.10.5 clean-launch sequencing, dual-source screen evidence, RAW PCAP authority and all non-causality boundaries are unchanged.

## v0.27.0 — APK/XAPK Package Intake

### Scope boundary

v0.27 changes only application-package intake before a research session begins. It adds XAPK handling while preserving the verified Android runtime, collectors, Research ZIP schemas and evidence semantics.

### Package-identity invariant

XAPK is treated as an untrusted ZIP container. Package identity is not taken from vendor metadata. Every APK member is inspected with `aapt2 dump badging`; installation requires one package name, compatible versionCode values, exactly one base APK without a split name and no duplicate split names.

### Split-install invariant

A single APK keeps the established `adb install -r -t -g` path. A validated multi-APK XAPK is installed in one `adb install-multiple -r -t -g` transaction with the base APK first. apk-research never guesses a base from filenames and never mixes APK parts from different packages.

### OBB invariant

OBB data is copied only after successful APK installation to `/sdcard/Android/obb/<verified package>/`. The target directory is derived from the package identity proven by aapt2, not from an XAPK manifest or archive path.

### Container-safety invariant

Absolute paths, `..` traversal, encrypted ZIP members, damaged containers, excessive member counts and excessive extracted APK/OBB size are rejected. Temporary extraction is deleted after success or failure.

### Acceptance boundary

Unit tests cover base/split validation, mixed-package rejection, path traversal, `install-multiple`, OBB copy and single-APK regression. Real AVD acceptance builds and signs a synthetic APK, packages it into XAPK with OBB, installs it through the same `AndroidRuntime.install_package()` path, verifies package/OBB on-device, removes it, and then runs the normal Research ZIP acceptance.

### Compatibility boundary

Hidden Emulator → gRPC/MMAP → AndroidView, v0.10.5 startup/clean-launch sequencing, RAW PCAP authority, attribution/non-causality boundaries and the dual-source screen model are unchanged.

## v0.26.0 — Investigator Workspace

### Scope boundary

v0.26 is a workflow/presentation layer over the verified v0.24 Unified Session Evidence and v0.25 Transport/Protocol Analysis. It introduces no new capture path, no replacement RAW artifact and no stronger causal model.

### Stable navigation references

Each workspace row receives a deterministic `EV-...` key derived from the row's existing time/event/action/flow identity. The key is used only for navigation, bookmarks, evidence sets and reports. It does not become source evidence and does not upgrade attribution or temporal correlation.

### Analyst-state boundary

Bookmarks and named evidence sets are persisted beside the archive as `<research.zip>.investigator.json`. The immutable Research ZIP is never opened for write. Stale references are pruned against the current workspace model.

### Search/filter boundary

Global search and filters are intersections over already observed/modelled fields. A filtered-out or absent row is not evidence that an event did not occur.

### Report boundary

Markdown/JSON reports contain selected evidence references plus source navigation IDs. Report membership is explicit analyst selection. Every record retains its original relation type/strength and `causal_claim`; the report cannot strengthen the source relation.

### Compatibility boundary

RAW PCAP remains authoritative; Action ↔ Flow/Packet stays temporal-only; screen links remain time-aligned navigation; v0.25 protocol interpretation remains captured-packets-only. Hidden Emulator → gRPC/MMAP → AndroidView, v0.10.5 startup/clean-launch sequencing and the accepted Continuous Screen + high-resolution screenrecord roles are unchanged. Audio Evidence and user-facing Virtual Display remain out of scope.

## v0.25.0 — Transport and Protocol Analysis

### Evidence model

v0.25 remains a derived analysis layer over the authoritative raw PCAP. It introduces no stronger causal model and no replacement evidence artifact. The selected-flow report declares `evidence_basis=captured-packets-only` and `causal_claim=false`.

### TCP observation boundary

Sequence ranges, ACK values and advertised windows are analyzed in capture order. Repeated/overlapping sequence ranges and gaps are observations about captured sequence space only. They are deliberately not promoted into definitive packet-loss or retransmission claims because capture loss, out-of-order delivery and an already-active connection can produce similar observations. Missing SYN/FIN/RST is represented as possible missing capture start/end, never as proof of non-occurrence.

### Protocol boundary

DNS is decoded only from complete captured messages. TLS metadata is decoded only from complete records/hellos available per packet or from bounded contiguous observed TCP payload. QUIC reuses the existing authenticated Initial parser; HTTP/3 is derived only from observed ALPN. Cleartext HTTP grouping is deliberately narrow and emitted only for one unambiguous complete request/response pair in opposite directions.

### Compatibility boundary

RAW PCAP authority, Packet ↔ Action temporal-only correlation, v0.10.5 startup/clean-launch sequencing and hidden Emulator → gRPC/MMAP → AndroidView remain unchanged. Audio Evidence and user-facing Virtual Display remain out of scope.

## v0.24.0 — Unified Session Evidence

### Scope

v0.24 is a presentation/navigation layer over existing evidence. It does not replace RAW artifacts or introduce a stronger causal model. The new session graph joins target-time screen locators, archived user actions, canonical normalized flows, raw-PCAP packet locators and existing process/socket attribution.

### Screen-time invariant

Continuous Screen MediaCodec PTS remains device elapsed-time evidence. UTC navigation is derived only when an archived realtime↔elapsed transform exists in canonical `screenrecord` timing; otherwise a legacy boundary anchor is explicitly marked estimated. Screen links are `time-aligned-navigation` with `causal_claim=false`.

### Reverse attribution invariant

The new Process/Socket reverse index groups flows only by the attribution already present in `network-flows.json`; it preserves UID/PID/inode/confidence/evidence and never upgrades attribution strength.

### Dual-source screen role

Owner-side v0.23.1 idle and rollover tests proved Continuous Screen continuity, including coverage inside a canonical screenrecord rollover gap. v0.24 records it as stable continuous/timeline evidence (`experimental=false`) while retaining Android `screenrecord` as the high-resolution source. Sole-source replacement remains a future quality/revalidation decision.

### Runtime boundary

Raw PCAP remains authoritative; Action ↔ Flow stays `temporal-only`; hidden Emulator → gRPC/MMAP → AndroidView and v0.10.5 startup sequencing remain unchanged.

## v0.23.1 — Sidecar evidence isolation and idle stability

### Trigger

The first owner-side real v0.23.0 Research ZIP proved two experimental-sidecar defects:
- Sidecar control/media loopback traffic dominated normalized Network/Timeline evidence even though it was generated by apk-research itself.
- Continuous Screen ended after a static interval because the established media socket retained the generic 8-second protocol timeout while the device encoder did not support forced repeated frames.

### Infrastructure-flow invariant

The collector already archives the exact dynamic control/media host/device ports in `02_normalized/continuous-screen.json`. v0.23.1 uses only those recorded ports, and only for TCP where both endpoints are loopback, to mark `apk-research-sidecar` infrastructure packets.

Raw PCAP is not altered. Derived flow inventory skips marked infrastructure and records its packet/byte counts explicitly. Timeline action correlation also skips marked infrastructure so apk-research's own media transfer cannot become apparent target-app activity.

### Long-lived media invariant

The bounded socket timeout remains appropriate while establishing the Sidecar and validating the binary media header. Once `SidecarScreenStream` owns the established connection, the media socket is switched to blocking mode. Stream termination continues to be controlled over the separate Sidecar control channel.

A static screen is therefore a valid silent interval, not a liveness failure.

### Acceptance boundary

Unit tests cover exact archived-port classification, derived-flow exclusion with raw source accounting and inherited timeout clearing.

Real AVD acceptance now deliberately leaves the screen idle for ten seconds, exceeding the old eight-second timeout, then requires Continuous Screen to complete cleanly. It also reconstructs exact Sidecar ports from the generated archive and fails if any corresponding loopback flow appears in normalized app flows.

### Compatibility boundary

No raw evidence is deleted or rewritten. Continuous Screen remains experimental/non-canonical; canonical screenrecord remains authoritative. Emulator gRPC/MMAP display/input, v0.10.5 startup sequencing, Packet ↔ Action non-causality and v0.23 transport-session semantics are unchanged.

## v0.23.0 — Transport Session Evidence

### Scope

Stage E continues with transport-layer interpretation over the concrete packets already exposed by Raw / Packet Inspector. Capture, normalized flow identity, attribution and Android runtime behavior are unchanged.

### TCP evidence model

For each packet in a selected TCP flow, Packet Inspector derives only fields directly present in the TCP header:
- sequence number;
- acknowledgment number;
- flags;
- header length;
- receive window;
- TCP payload length.

The flow-level transport summary detects an observed three-way handshake only when SYN → SYN/ACK → ACK are all present in capture order. FIN and RST are reported only when their packets are present.

### Capture-bounded semantics

Missing lifecycle packets are represented as `partial-or-not-observed-in-capture` or `not-observed-in-capture`. apk-research does not infer that an unseen handshake or termination did not occur.

No TCP application stream reconstruction is introduced. Encrypted payload remains encrypted, and no missing packet is synthesized.

### GUI integration

Packet details/search expose transport fields and the selected flow summary presents observed handshake/termination state plus the packet IDs supporting those observations.

### Acceptance boundary

Unit tests cover TCP header parsing, complete and partial handshakes, FIN/RST and non-TCP applicability. Real AVD acceptance validates the same semantics against the generated Research ZIP.

### Compatibility boundary

Raw PCAP remains authoritative. Packet ↔ Action remains `temporal-only` with `causal_claim=false`. No Research ZIP schema, collector, hidden Emulator → gRPC/MMAP runtime, v0.10.5 startup sequencing, sidecar responsibility or canonical screenrecord behavior changes. Audio Evidence and Virtual Display remain excluded.

## v0.22.0 — Packet ↔ Action Evidence

### Scope

Stage E begins with a presentation-only cross-link between the concrete packets exposed by v0.18 and the action windows already exported by Research Timeline. Capture, attribution and runtime behavior are unchanged.

### Correlation invariant

A packet may reference an action only when:
1. the action's archived `correlation.network.flow_ids` contains the selected normalized `flow_id`; and
2. the packet target timestamp lies inside that action's archived target-time correlation window.

The inspector never creates a wider window, substitutes host time for target time, or turns temporal adjacency into a causal claim.

### GUI integration

The Packets tab adds an Action-window column, action-aware search/details and direct Packet → Timeline navigation. The selected packet retains its original raw PCAP packet index and byte offsets.

### Acceptance boundary

Unit tests cover window membership, flow mismatch and non-causality. Real AVD acceptance selects a flow with archived correlated actions when available, resolves its raw packets, requires at least one matching packet/action relation, and checks every emitted action ID against both the selected flow and archived Timeline.

### Compatibility boundary

No new Research ZIP artifact or schema. Raw PCAP remains authoritative. Hidden Emulator → gRPC/MMAP → AndroidView, v0.10.5 startup, Android sidecar, experimental continuous-screen collector and geometry-safe gRPC input remain unchanged. Audio Evidence and Virtual Display remain excluded.

## v0.21.0 — Interaction Completeness

### Scope

v0.21 completes the existing Emulator gRPC interaction layer without replacing its proven transport. The embedded Android view adds two-pointer gesture synthesis while preserving the hidden Emulator → gRPC/MMAP → AndroidView runtime and persistent `streamInputEvent`.

### Gesture model

- normal left drag remains a one-pointer touch/swipe;
- Ctrl+drag injects a symmetric two-pointer pinch/rotate gesture;
- Shift+drag injects vertical tilt;
- Ctrl+Shift+drag injects horizontal tilt;
- both active pointers are serialized in the same Emulator `TouchEvent` with stable identifiers.

### Geometry invariant

Each pointer gesture is bound to one display-geometry generation defined by framebuffer dimensions, Android input dimensions and rotation. If that geometry changes while the gesture is active, the old gesture is terminated at its last known points. Subsequent movement is not remapped onto the new geometry.

### Evidence boundary

A completed two-pointer interaction is recorded as one semantic `multi_touch` user action with mode, pointer count, start/end points, duration and geometry generation. Geometry-interrupted single-pointer input is recorded explicitly as `gesture_cancelled` with `cancel_reason=display_geometry_changed`.

These records prove what apk-research injected, not that the target application consumed the gesture or caused later network/process activity. Action ↔ Flow remains `temporal-only` with `causal_claim=false`.

### Acceptance boundary

Real AVD acceptance transmits a two-pointer event through the same persistent Emulator gRPC stream. The AVD workflow path gate now explicitly includes desktop input/runtime files so future input changes cannot bypass this acceptance.

No changes to v0.10.5 startup/clean-launch sequencing, Android sidecar responsibilities, continuous-screen A/B collection, raw PCAP semantics, Audio Evidence scope or Virtual Display scope.

## v0.20.0 — Continuous Screen Evidence

### Scope

v0.20 introduces the first collector backed by the project-owned Android sidecar, but only as a parallel experimental evidence path. Existing Android `screenrecord` remains the canonical required screen source until real owner-side archives prove that the new path has no coverage or timing regression.

### Media transport

Sidecar protocol v2 keeps the bounded text control channel and adds a separate binary media connection. The host opens a second localhost listener and installs `adb reverse` before requesting `SCREEN_START`. The agent connects back, emits a versioned stream header, then serializes every MediaCodec output record as flags + device PTS + payload length + exact payload bytes. A zero-sized terminal EOS record is part of the stream protocol and packet accounting.

### Capture provenance

The experimental collector writes:
- `01_raw/screen/continuous-screen.h264` — exact concatenation of MediaCodec payload bytes;
- `02_normalized/continuous-screen-packets.jsonl` — sequence, flags, PTS, size and raw byte offset per protocol record;
- `02_normalized/continuous-screen.json` — transport, timing model, statistics and cleanup provenance;
- `02_normalized/screen-ab-comparison.json` — diagnostic comparison against canonical screenrecord.

MediaCodec PTS are preserved in their device media clock domain; v0.20 does not pretend they are UTC. Host/target UTC boundary samples are recorded separately.

### Promotion boundary

The sidecar collector is registered `required=false`. A collector-specific failure is recorded as experimental evidence and cannot weaken a valid canonical Research Session. Release acceptance nevertheless requires the managed API 35 AVD to produce a clean experimental stream with exact host/agent accounting, nonzero presentation span, codec configuration, one terminal EOS record and complete cleanup.

`screen-ab-comparison.json` always records `promotion_decision=not-automatic`. Promotion to canonical screen evidence requires later owner-side A/B evidence.

### Runtime boundary

No change to hidden Emulator → gRPC/MMAP → AndroidView, persistent gRPC input, v0.10.5 clean-launch sequencing, PCAP capture or network evidence semantics. Audio Evidence and the user-facing Virtual Display research mode remain outside scope.

## v0.19.0 — Android Sidecar Foundation

### Scope

A bounded infrastructure layer only. v0.19 does not migrate collectors and does not alter the established Emulator display/input or clean-launch runtime.

### Agent lifecycle

The repository owns the Java source. Release builds compile it to Java 8 bytecode, convert it with Android D8 into `classes.dex`, and package that DEX as `apk-research-agent.jar`. The JAR is included in the PyInstaller distribution.

At runtime the host:
1. verifies the ADB target and pushes the JAR under the private apk-research temporary root;
2. opens a localhost listening socket first;
3. installs `adb reverse tcp:<device-port> tcp:<host-port>`;
4. starts `app_process` with the temporary JAR on `CLASSPATH`;
5. accepts the agent connection and requires exact protocol/agent version agreement;
6. uses the same socket for bounded commands;
7. sends graceful STOP, waits for process exit, removes the reverse mapping and deletes the temporary JAR.

### Protocol

Protocol v1 is intentionally minimal:
- agent banner: exact protocol and agent version;
- `HELLO → READY` handshake;
- `PING <token> → PONG <token> <monotonic-ms>`;
- `STOP → BYE`;
- bounded UTF-8 line length and restricted ping token alphabet.

### Acceptance boundary

Real AVD acceptance must prove lifecycle and cleanup, then immediately re-run the required Emulator gRPC/MMAP check. This guards against the sidecar silently becoming or disturbing the display/input path.

No evidence schema or collector contract changes in this release.

## v0.18.0 — Raw / Packet Inspector

### Scope

Post-capture/presentation-only packet drill-down. The feature resolves an existing normalized TCP/UDP flow to the concrete records in the original `01_raw/network/traffic.pcap` without changing collectors or Research ZIP schemas.

### Canonical packet resolution

The inspector reuses the same direction-independent canonical connection key as `network-flows.json`. Each matching packet receives a reproducible locator containing its global PCAP packet index, record byte offset, frame byte offset, target UTC timestamp, endpoints and captured/original lengths.

### Raw boundary

The complete packet remains authoritative only in the original PCAP. The GUI shows a bounded raw-frame hex preview and protocol metadata that can be directly supported by packet bytes. Encrypted payload is never presented as decoded application plaintext.

### GUI integration

A dedicated Packets tab is reachable from Evidence and Network. Double-clicking the raw PCAP node in Evidence resolves the selected flow directly to packets.

### Compatibility boundary

No changes to Android runtime, collectors, v0.10.5 clean-launch sequencing, gRPC/MMAP display/input, packet capture, socket attribution or Action ↔ Flow temporal-only semantics.

## v0.17.0 — Unified Evidence Explorer

### Scope

Presentation-only объединение уже существующей forensic-модели. Android runtime, clean launch, collectors, PCAP capture, socket attribution и Research ZIP schemas не изменяются.

### Evidence graph

Explorer строит два представления одной и той же evidence-модели:

- `Action → Host → Flow → Process/Socket → Raw`;
- `Host → Flow → Action / Process/Socket / Raw`.

Canonical `flow_id`, `correlated_action_ids` и owner evidence переиспользуются без изменения. Action ↔ Flow остаётся временной корреляцией, а не утверждением причинности.

### Raw provenance

Для flow формируется locator к `01_raw/network/traffic.pcap`: canonical flow id, target-time interval и bidirectional 5-tuple. Для process/socket attribution формируется locator к `01_raw/network/socket-snapshots.txt` и `02_normalized/socket-attribution.json` с PID/process/UID/inode/confidence evidence. Locator является указателем на источник и не заменяет RAW artifact.

### GUI navigation

Добавлена отдельная вкладка Evidence и двусторонние переходы Timeline ↔ Evidence ↔ Network. Поиск охватывает action, host, flow, process/PID/socket evidence, IP/port и protocol.

### Validation boundary

Dev verification: 178 tests passed; отдельный offscreen GUI construction smoke для `UnifiedEvidenceMainWindow` прошёл. Stable runtime остаётся hidden Emulator → gRPC/MMAP → AndroidView с persistent gRPC input, startup baseline остаётся v0.10.5.

## v0.16.1 — QUIC evidence hardening

### Trigger

Реальный v0.16.0 Research ZIP выявил четыре ложных QUIC flow: восемь DNS UDP/53 request/response packets случайно удовлетворяли форме long header и попадали в QUIC summary, хотя UDP/443 в сессии отсутствовал.

### Corrected evidence contract

- unknown/unsupported long-header version is not sufficient evidence of QUIC;
- supported QUIC v1/v2 context becomes confirmed only after successful Initial authentication/decryption;
- Version Negotiation and later long/short-header packets are accepted as QUIC only for an already confirmed flow;
- outbound client Initial smaller than 1200 bytes cannot establish a flow;
- real DNS prefixes from the failing archive are permanent regression fixtures.

### Boundary

Изменение только post-capture classifier. Raw PCAP, collectors, socket attribution, canonical flow identity, Timeline correlation, hidden Emulator → gRPC/MMAP runtime и v0.10.5 clean-launch sequencing не меняются.

## v0.16.0 — QUIC / HTTP/3 Network Intelligence

### Scope

Post-capture protocol intelligence only. Android runtime, clean launch, tcpdump capture, socket attribution and raw evidence collection are unchanged.

### QUIC evidence model

- QUIC is asserted only after a syntactically valid QUIC long header is recognized; UDP/443 alone is not sufficient evidence.
- QUIC v1 (`0x00000001`) and QUIC v2 (`0x6b3343cf`) Initial protection are supported.
- Initial keys are derived from the standards-defined version salt and the client's initial Destination Connection ID. This is passive analysis of public Initial protection, not MITM.
- Client Initial CRYPTO frames are reassembled and TLS ClientHello SNI/ALPN are extracted when present.
- ALPN `h3` or `h3-*` establishes HTTP/3 application-protocol evidence.
- Handshake and 1-RTT payloads remain encrypted; apk-research does not claim application-content decryption.

### Normalized evidence

`network-flows.json` schema is `0.3`. Canonical bidirectional 5-tuple `flow_id` identity and ownership attribution are unchanged. QUIC metadata is additive: application protocols, QUIC versions/types, Initial-decode state, SNI and ALPN.

### Validation boundary

The available real v0.13 Research ZIP contains UDP traffic but no UDP/443 flow, so it cannot validate a live QUIC session. Protocol correctness is covered by RFC 9001/RFC 9369 initial-key vectors and protected synthetic QUIC v1/v2 Client Initial packets. Future real archives containing QUIC will be evaluated without changing this evidence contract.

## v0.15.0 — Product identity: apk-research

### Scope

Полная миграция имени продукта. Старое имя удаляется из tracked text files и путей репозитория; canonical product identity становится `apk-research`, Python namespace — `apk_research`.

### Compatibility boundary

AppId Inno Setup сохраняется, чтобы v0.15.0 оставался обновлением существующей Windows-установки, а не независимым продуктом. Forensic/runtime architecture не меняется.

## v0.14.0 — Host Intelligence: Service vs DNS

### Scope

Релиз исправляет только presentation semantics Network Analyzer после проверки реального v0.13.0 Research ZIP. Capture/runtime и forensic schemas не меняются.

### Host role separation

Host group по-прежнему объединяет DNS evidence и service connections по имени, но теперь внутри presentation model явно разделяются роли:

- DNS resolution flow — TCP/UDP flow с DNS query и портом 53;
- service flow — остальные flows группы;
- owner/confidence host-level сводки вычисляются по service flows, если они есть;
- service remote IP/ports и resolver IP выводятся раздельно;
- если наблюдалось только DNS-разрешение, UI не выдаёт resolver endpoint за service endpoint и явно сообщает об отсутствии подтверждённого service flow для имени.

### Evidence boundary

Разделение ролей является только derived desktop presentation. network-flows.json, raw PCAP, attribution evidence и canonical flow_id остаются неизменными. DNS query не превращается в доказательство того, что последующий IP-flow принадлежит имени без собственного SNI/DNS-derived host evidence.

## v0.13.0 — Host-oriented Network Analyzer

### Scope

Этот релиз изменяет только post-capture desktop analysis. Collector lifecycle, Android Emulator gRPC/MMAP runtime, clean-launch sequencing, raw PCAP capture, socket attribution, Research ZIP structure и нормализованные forensic schemas остаются без изменения.

### Network view model

Добавлен отдельный `desktop/network_view_model.py`, который формирует presentation-only модель поверх `02_normalized/network-flows.json`:

- canonical host выбирается в порядке TLS SNI → DNS query → remote IP;
- bidirectional normalized flows группируются по host без слияния или переписывания исходных flow records;
- для host вычисляются агрегаты packets/bytes, protocols, owners, confidence counts, remote IP и correlated action IDs;
- фильтрация остаётся flow-based, а host остаётся видимым, если после фильтрации у него есть хотя бы один matching flow;
- human-readable detail renderer не заменяет исходный normalized evidence и не вводит новых forensic claims.

### Timeline integration

Network inspection теперь одновременно читает `research-timeline.json`. `correlated_action_ids` отображаются как конкретные действия с временем и типом. Пользователь может выбрать действие и перейти к нему в Timeline. Двойной клик по flow открывает первое связанное действие; переход Timeline → canonical `flow_id` остаётся симметричным.

### Regression boundaries

Нельзя возвращать flat-only Network table как единственный UX, нельзя изменять raw evidence ради удобства GUI и нельзя трактовать temporal correlation как causal attribution. Runtime baseline остаётся hidden Emulator → gRPC/MMAP → AndroidView с persistent `streamInputEvent`; startup baseline остаётся v0.10.5.

Файл фиксирует архитектурные решения, границы и будущие крупные изменения apk-research. Это не журнал каждого мелкого коммита.

## Текущее состояние

**Этап:** v0.21.0 — Interaction Completeness.
**Stable baseline:** Windows uses only hidden Emulator + top-down gRPC/MMAP display + persistent gRPC input. No alternate display/input fallback. Boot stall recovery: one `-wipe-data`; stale private-AVD cleanup remains recovery infrastructure.  
**Core evidence baseline:** v0.1.0 Research Session Core.  
**Реализовано:** GUI, self-contained Windows distribution, managed Android runtime/AVD, APK install, embedded Android view, Windows provisioning gate и desktop release gates.  
**Принцип:** v0.1.0 raw evidence contract не ослабляется.

### Активный runtime contract

- Windows: `emulator -qt-hide-window → gRPC streamScreenshot → MMAP → AndroidView`;
- input: only persistent gRPC `streamInputEvent`, pointer drag = DOWN → MOVE → UP;
- framebuffer: only `grpc-mmap`, top-down row order;
- no DWM, visible Emulator, gRPC-bytes, ADB screencap or ADB input fallback;
- no automatic graphics/display profile ladder on Windows;
- failure of required gRPC/MMAP or streamInputEvent is a product error and is surfaced explicitly;
- private-AVD stale-process/lock cleanup and one `-wipe-data` guest recovery remain allowed because they restore the same required architecture;
- Linux/KVM acceptance may use `-no-window`, but still requires the same gRPC/MMAP framebuffer/input transport;
- older display ADRs remain historical only; ADR-082 defines the active policy.


## Зафиксированные решения

### ADR-001 — Отдельный проект от Web Research
apk-research предназначен для Android-приложений. Web Research остаётся отдельным инструментом для browser/web-исследований.

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

### ADR-013 — Необязательные metadata-команды не рушат snapshot (superseded in package-dump scope by ADR-086)
Обязательные metadata-source должны быть получены полностью. Начиная с v0.8.9 полный verbose Package Manager dump классифицирован ADR-086 как дополнительное raw evidence; lightweight package identity/version evidence остаётся обязательным. Сбой дополнительной команды (`uname`, SELinux, display metadata и т. п.) фиксируется в raw/normalized данных, но сам collector остаётся успешным.

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
Полный `dumpsys package` может быть достаточно большим, чтобы текстовый ADB transport завершился нестабильно. Collector направляет stdout команды во временный файл под `/data/local/tmp/apk-research/<session-id>/`, переносит его через `adb pull`, затем удаляет remote-файл best-effort. Это сохраняет полный raw dump и избегает зависимости от объёма stdout.


### ADR-031 — Screen timing берётся из встроенного Winscope metadata, а не из MP4 duration
Современный Android `screenrecord` пишет data-track `#VV1NSC0PET1ME2#` с elapsed frame timestamps и realtime-to-elapsed offset. Статичный экран может не генерировать новые frames, поэтому playback duration MP4 не обязан совпадать с wall-clock длительностью collector process. apk-research сохраняет raw MP4 без изменений и извлекает только summary первого/последнего frame UTC и frame count в `screen.json`.

### ADR-032 — Первый релиз требует semantic audit, а не только ZIP integrity
CRC/SHA-256 доказывают целостность архива, но не достаточность evidence. Release acceptance дополнительно проверяет lifecycle order, collector statuses, clock skew, временное покрытие logcat/PCAP, package launch и screen frame timing. Формально валидный, но семантически неполный Research ZIP не проходит release gate.


### ADR-033 — Release публикуется только после gates exact commit SHA
Release workflow не доверяет предыдущим успешным runs. Он ждёт завершения workflow `CI` и `AVD Research Acceptance` для собственного `GITHUB_SHA`. Только после двух `success` разрешены build/tag/GitHub Release. Это предотвращает публикацию версии, отличающейся от реально протестированного кода.

### ADR-034 — Release assets являются воспроизводимыми Python artifacts
v0.1.0 публикует wheel и sdist, собранные из release commit, плюс `SHA256SUMS.txt`. Research ZIP из acceptance остаётся краткоживущим CI evidence и не превращается в release artifact, поскольку это результат синтетического исследования, а не дистрибутив программы.

### ADR-035 — Release docs являются обязательной частью release commit
Release workflow проверяет, что `README.md`, `REFACTORING.md`, `CHANGELOG.md` и `RELEASE_NOTES.md` содержат выпускаемую версию. Публикация блокируется, если release documentation не синхронизирована с `pyproject.toml`.


### ADR-036 — Desktop GUI является основной границей продукта
Начиная с v0.2 штатный пользовательский интерфейс — `apk-research.exe`. CLI сохраняется только для разработки и диагностики. GUI вызывает core classes напрямую и не является текстовой оболочкой над CLI.

### ADR-037 — Пользователь не устанавливает Python
Desktop distribution собирается PyInstaller и устанавливается через Inno Setup. Python runtime и Qt входят в apk-research. Пользовательский компьютер не требует Python/pip/venv.

### ADR-038 — Android runtime принадлежит apk-research
ADB, Android Emulator, build-tools и system image не считаются внешними пользовательскими зависимостями. apk-research загружает официальные Google packages и хранит их в собственном каталоге `%LOCALAPPDATA%\apk-research\components`.

### ADR-039 — Android Studio не является зависимостью
Private AVD создаётся программой напрямую из managed system image/config. Android Studio и ручной AVD Manager пользователю не нужны.

### ADR-040 — Android отображается внутри GUI
Google Emulator запускается headless. apk-research получает framebuffer через ADB и передаёт input обратно через `input tap/swipe/text/keyevent`. Это отделяет UX от внешнего окна emulator и позволяет позже заменить framebuffer transport без изменения пользовательского контракта.

### ADR-041 — Stable desktop release публикует installer
Начиная с v0.2 основным release asset является `apk-research-setup.exe` + SHA-256. Stable publication требует exact-SHA Windows CI, real AVD acceptance и Desktop Build.


### ADR-042 — Managed Android использует только stable repository channel
Desktop provisioning выбирает Android SDK packages только из Google repository `channel-0`. Более новые beta/dev/canary revisions не имеют права автоматически попадать в пользовательский runtime. Это решение принято после того, как выбор не-stable Emulator привёл к отдельному crash на Windows.

### ADR-043 — Windows hosted CI проверяет provisioning, а не неподдерживаемый software boot
GitHub-hosted Windows runner без аппаратной виртуализации не является надёжным Android boot target. Windows gate обязан доказать download/checksum/extraction, executable versions и private AVD creation. Настоящий Android boot/root/tcpdump/Research ZIP остаётся обязательным real AVD gate на KVM. Пользовательский Windows runtime использует аппаратное ускорение/WHPX, а не `-accel off` как штатный fallback.

### ADR-044 — GUI авария не должна бросать уже собранные evidence
Если после старта research session GUI получает неожиданное исключение, controller best-effort вызывает штатный stop/export и публикует partial/failed Research ZIP. Если startup failure уже сформировал failed archive внутри orchestrator, GUI повторно его не экспортирует, а использует существующий архив.

### ADR-045 — Managed Android можно полностью восстановить без ручного удаления файлов
Настройки apk-research содержат repair action для удаления только managed Android SDK/Emulator/system image/AVD. Research sessions хранятся отдельно и не удаляются. Следующая подготовка заново скачивает официальные компоненты и проверяет checksums.


### ADR-046 — Windows WHPX hardware acceptance является дополнительным release evidence
GitHub-hosted Windows CI остаётся обязательным для сборки, unit/GUI smoke и чистого provisioning, но не считается доказательством пользовательского Android boot: nested virtualization на hosted runner не является гарантированным контрактом. Отдельный workflow `Windows WHPX Acceptance` на выделенном self-hosted Windows x64 runner с аппаратной виртуализацией и меткой `apk-research-whpx` сохраняется как дополнительная hardware acceptance. Workflow скачивает `apk-research-setup.exe` из `Desktop Build` того же commit SHA, выполняет чистую установку, запускает acceptance через установленный frozen `apk-research.exe`, требует именно WHPX по `emulator -accel-check`, загружает private AVD, скачивает зафиксированный Appium ApiDemos v6.0.17 по immutable release URL и проверяет SHA-256 `90cc1041c063a7fb68889143250fefa3139ef0c81e4208f67dbaafe8f15c8be9`, затем именно установленный apk-research.exe определяет package через managed aapt2, устанавливает APK через managed ADB и исследует `io.appium.android.apis`. Gate также доказывает root ADB, tcpdump/raw PCAP, framebuffer, logcat, screen recording, complete Research ZIP, checksum verification и semantic audit. Stable publication не блокируется отсутствием или очередью этого self-hosted runner: обязательные exact-SHA gates — CI, Desktop Build и real AVD Research Acceptance. Если WHPX runner доступен, его результат сохраняется как дополнительное evidence и используется для диагностики Windows-specific regressions.


### ADR-047 — Package Manager dump failure degrades evidence instead of aborting capture (superseded by ADR-086)
Историческое решение v0.2.1 оставляло полный package dump обязательным для `complete` и переводило его отказ в `partial`. Реальный v0.8.8 Research ZIP показал, что это ошибочно смешивает полноту диагностического metadata dump с полнотой основного research evidence. Актуальный contract определён ADR-086.


### ADR-048 — Release acceptance и пользовательская hypervisor-совместимость разделены
WHPX остаётся предпочтительным Microsoft-backed Windows hypervisor и целевым dedicated Windows hardware acceptance. Это не означает, что пользовательский runtime должен отвергать уже установленный и usable AEHD/GVM, пока текущий Android Emulator официально поддерживает этот fallback. Если `emulator -accel-check` подтверждает WHPX или AEHD/GVM, apk-research продолжает работу без UAC. Автоматическая настройка Windows выполняется только при отсутствии usable hypervisor. Она включает только `HypervisorPlatform` и `hypervisorlaunchtype=Auto` через один elevated PowerShell process; `VirtualMachinePlatform` для Android Emulator не включается. Если изменение Windows требует reboot, приложение обязано сообщить об этом явно, поскольку `/NoRestart`/NoRestart semantics могут не показывать системный prompt.


### ADR-049 — Интерактивный Android использует Emulator gRPC
Штатный desktop path получает непрерывный RGB framebuffer из локального managed Emulator через gRPC и отправляет touch/key input тем же control plane. GUI хранит только последний кадр и публикует его примерно каждые 33 ms, поэтому устаревшие frames не образуют очередь. ADB screenshot/input остаётся compatibility fallback; research collectors по-прежнему независимы от GUI transport.

### ADR-050 — GPU rendering выбирает Emulator
При аппаратном CPU-ускорении managed Emulator использует GPU mode auto. Принудительный SwiftShader удалён из штатного hardware path и сохраняется только для software-only fallback.

### ADR-051 — Clean launch является отдельным research mode (sequencing superseded by ADR-087)
Режим clean и continue остаются отдельными пользовательскими режимами, но первоначальная последовательность force-stop-before-preflight больше не является активным contract. Актуальная граница clean launch зафиксирована ADR-087.


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
Требование пользовательского UX — плавность интерфейса, сопоставимая с обычным Android Emulator/телефоном. Screenshot-based paths (ADB PNG, gRPC bytes, MMAP framebuffer) сохраняют дополнительную стадию capture/mirror/presentation и не могут гарантировать тот же visual cadence, что собственное окно Emulator. На Windows apk-research поэтому использует настоящий Qt window Android Emulator: окно запускается скрытым через `-qt-hide-window`, после boot apk-research находит HWND процесса/его descendants, удаляет top-level chrome, выполняет `SetParent` в native QWidget и синхронизирует размер через Win32. Mouse/keyboard попадают непосредственно в Emulator child window. MMAP/gRPC framebuffer остаётся fallback при невозможности attach.

### ADR-059 — Research transport отделён от display transport
Переход на native HWND не меняет evidence contract. ADB, root, logcat, tcpdump, screenrecord, package metadata, Research ZIP и gRPC control остаются независимыми от способа визуального отображения Android. Native display можно отключить/потерять без остановки collectors; GUI автоматически возвращается к framebuffer fallback.


### ADR-060 — Сбой native Emulator display не блокирует Research Target
Реальный Windows-тест v0.5.0 показал, что Android Emulator/QEMU может аварийно завершиться ещё во время boot при использовании native Qt/GPU display path. Display transport не имеет права становиться single point of failure для research core. Windows managed boot поэтому использует последовательность профилей: native HWND + host GPU → headless + host GPU → headless + SwiftShader. После первой успешной загрузки выбранный профиль сохраняется на весь текущий runtime. Headless-профиль автоматически использует MMAP/gRPC/ADB framebuffer stack, а native HWND attach для него не выполняется. Все неуспешные попытки фиксируются в diagnostics вместе с GPU/display mode, duration, exit code, error и полной Emulator command line. Managed Emulator запускается с `-crash-report-mode disabled`, поскольку внутренний Google crash-report dialog не является частью пользовательского интерфейса apk-research; ошибка остаётся в локальной диагностике и инициирует автоматический fallback.


### ADR-061 — `-qt-hide-window` не является контрактом native HWND embedding
Реальный тест v0.5.1 показал ложный успех Win32 embedding: apk-research находила Qt HWND процесса Emulator, выполняла `SetParent` и считала display подключённым, но Android pixels в этом HWND не отображались. Официальный embedded режим Android Emulator использует `-qt-hide-window` совместно с control/framebuffer transport; скрытый Qt HWND не рассматривается как поддерживаемая внешняя native video surface. Поэтому stable runtime больше не активирует NativeEmulatorEmbedder и не останавливает framebuffer stream из-за существования такого HWND. На Windows основной display contract снова: `-qt-hide-window` + gRPC MMAP → gRPC bytes → ADB screenshot fallback. Win32 `SetParent` код остаётся изолированным экспериментом и не входит в stable path до появления отдельного доказательства корректной видеоотрисовки на реальном Windows hardware.


### ADR-062 — Native display использует только реальное standalone-окно Emulator
Для нативной плавности v0.6.0 запускает основной Windows profile без `-qt-hide-window` и без `-no-window`. apk-research ищет только видимое top-level окно Emulator сразу после создания процесса и переподчиняет именно его. Attach считается успешным только после проверки `SetParent`, фактического parent HWND, ненулевой client area и видимости. До подтверждения framebuffer stream не отключается; при ошибке native attach gRPC/MMAP продолжает работу.

### ADR-063 — Reverse framebuffer rotation снова нормализуется
Реальный тест v0.5.2 показал reverse-portrait первый кадр. Для raw bottom-up RGBA/RGB кадров rotation 2/3 снова трактуется как reverse orientation: применяется коррекция, эквивалентная bottom-up flip + 180-degree normalization, а input ratios инвертируются по обеим осям.


### ADR-064 — GitHub Release хранит дистрибутивы, Actions artifacts являются эфемерными
Постоянным хранилищем пользовательских бинарников считаются только GitHub Releases. Успешные AVD/provisioning/WHPX acceptance runs не создают диагностические Actions artifacts; их статус и стандартные Actions logs достаточны для подтверждения gate. При failure диагностические evidence artifacts сохраняются на 3 дня. Единственный успешный временный artifact — `apk-research-windows-desktop` с проверенным installer и SHA-256 — создаётся только для release-candidate commit, имеет retention 1 день, используется Release workflow для публикации и удаляется API-вызовом сразу после успешного GitHub Release. Windows WHPX Acceptance больше не зависит от этого artifact и скачивает `apk-research-setup.exe` и `SHA256SUMS.txt` непосредственно из уже опубликованного exact-SHA GitHub Release; тем самым аппаратный gate проверяет тот же EXE, который получает пользователь.


### ADR-065 — DWM live composition заменяет cross-process SetParent
Реальный тест v0.6.0 доказал, что apk-research находит правильный standalone Qt HWND Android Emulator, но после cross-process `SetParent` GPU surface становится чёрной; при возврате окна к top-level состоянию изображение снова появляется. Поэтому `SetParent` исключён из active display path. Начиная с v0.7.0 Emulator остаётся самостоятельным top-level GPU window, а apk-research регистрирует его через `DwmRegisterThumbnail` в собственном top-level HWND и обновляет `DWM_THUMBNAIL_PROPERTIES.rcDestination` по геометрии AndroidView. DWM API требует top-level source и destination, что соответствует новой архитектуре. После успешной регистрации source window перемещается за пределы virtual desktop, но не скрывается/минимизируется; при shutdown оно не восстанавливается, чтобы исключить визуальную вспышку. Input остаётся через Emulator gRPC. При ошибке DWM используется существующий gRPC/MMAP → gRPC bytes → ADB fallback.


### ADR-066 — Release-candidate artifact определяется release commit contract
Попытка определять release-candidate сравнением версии с parent через `git show` оказалась ненадёжной в GitHub Actions checkout и дала false negative для v0.7.1. Поскольку проект уже имеет формальный commit-driven release contract, временный `apk-research-windows-desktop` artifact создаётся только на push в main, если head commit message начинается с `Release apk-research v`. Обычные коммиты не создают installer artifacts. Release workflow по-прежнему удаляет этот однодневный artifact сразу после публикации.


### ADR-067 — DWM source window постоянно исключено из пользовательского desktop UX
Реальный тест v0.7.2 подтвердил плавность DWM live, но показал, что однократного `SetWindowPos` недостаточно: Qt/Emulator позднее меняет geometry и source window снова появляется на рабочем столе. v0.7.3 сохраняет source как visible/non-minimized top-level GPU window, но каждые 100 ms перемещает его полностью за правую границу всего Windows virtual desktop. Дополнительно source получает `WS_EX_TOOLWINDOW` и теряет `WS_EX_APPWINDOW`, поэтому не участвует в taskbar/Alt+Tab. Это не меняет parent, размер или GPU surface. При shutdown порядок строго обратный прежнему: сначала `runtime.stop()` завершает Emulator при ещё зарегистрированном DWM thumbnail, затем thumbnail удаляется. Это исключает вспышку standalone окна при закрытии apk-research.


### ADR-068 — DWM source остаётся на active desktop и скрывается покрывающим top-level окном
Реальный тест v0.7.3 показал, что полное перемещение standalone Emulator за пределы virtual desktop приводит к чёрному DWM thumbnail: Qt/GPU surface перестаёт нормально обновляться для DWM. Поэтому source window сохраняется visible/non-minimized на active desktop, но каждые 100 ms позиционируется полностью внутри screen rectangle apk-research и ставится непосредственно за его top-level HWND через `SetWindowPos(source, destination_hwnd, ...)`. При нехватке места source пропорционально уменьшается, чтобы ни одна его граница не могла выступить из-под apk-research. `WS_EX_TOOLWINDOW`/отсутствие `WS_EX_APPWINDOW` сохраняют отсутствие source в taskbar/Alt+Tab. При minimize covering window source временно скрывается; при restore сначала восстанавливаются geometry/z-order, затем source показывается без activation.

### ADR-069 — DWM thumbnail visibility управляется выбранной Qt-вкладкой
DWM thumbnail композитится в top-level HWND и не является дочерним Qt widget, поэтому QTabWidget не может автоматически clip/hide его. Начиная с v0.7.4 `tabs.currentChanged` явно переключает `DWM_THUMBNAIL_PROPERTIES.fVisible`: только индекс вкладки Исследование имеет visible=true. Это исключает наложение Android изображения поверх Настроек, Диагностики, Истории и Результатов.


### ADR-070 — v0.7.8 намеренно ограничен одним изменением относительно v0.7.4
После реальных тестов v0.7.5–v0.7.7 принято решение вернуть весь functional tree к v0.7.4. В v0.7.8 не переносятся изменения startup/DWM/reset/orphan/AVD lifecycle из последующих версий. Единственный retained delta — pointer drag как touch lifecycle: press → DOWN, move → streamed MOVE, release → UP. `AndroidView`, `DesktopController`, `AndroidRuntime` и `EmulatorGrpcClient` получают только необходимые touch methods; native display и Emulator startup code остаются байт-в-байт на baseline v0.7.4, кроме файлов, где touch integration требует изменений.


### ADR-071 — Startup cleanup ограничен только private AVD
После сбоя пользователь не должен перезагружать Windows ради освобождения AVD. v0.7.9 до создания GUI сканирует Windows процессы, но считает кандидатом только `emulator.exe`/`qemu-system-*.exe`, одновременно содержащий `apk_research_api35` в command line и относящийся к managed Emulator directory apk-research. Сначала выполняется graceful `adb -s emulator-5554 emu kill`, затем surviving matching PID завершается `taskkill /T /F`. Общий adb server и сторонние AVD не затрагиваются. `*.lock` удаляются только если matching processes больше нет; userdata/config/system image не изменяются. При наличии второго живого процесса apk-research очистка пропускается, чтобы не уничтожить активный runtime другого окна. Этот механизм не меняет DWM, boot profiles, reset или input path v0.7.8.


### ADR-072 — Зависшая загрузка AVD восстанавливается ограниченной двухступенчатой схемой (superseded by ADR-077)
Процесс Emulator и DWM surface могут быть живы, когда guest Android не достигает `sys.boot_completed=1`. Это отличается от stale process/lock и не лечится startup cleanup. v0.7.10 классифицирует hardware boot как stalled после 150 s total или 75 s continuous ADB-online без boot_completed. На первый stall выполняется soft restart того же AVD без изменения userdata. Только если повторный boot тоже stalled, один следующий launch получает официальный `-wipe-data`; флаг существует только в памяти до построения этой команды. Clean recovery имеет extended 240 s timeout. На один `ensure_ready` допускается максимум один recovery cycle, после чего сохраняется штатный graphics-profile fallback. DWM/native-window/input код не изменяется.


### ADR-073 — Нормальный startup не создаёт видимое окно Emulator
Причина startup flash находилась в самой DWM-модели: standalone Emulator сначала создавал и показывал Qt top-level window, а apk-research могла найти HWND и зарегистрировать DWM thumbnail только после этого. Между созданием source window и attach существовал race. Начиная с v0.8.0 primary Windows profiles используют `-qt-hide-window`. Изображение не извлекается из HWND: Emulator gRPC `streamScreenshot` → MMAP → AndroidView. В successful primary path отдельного source window нет.

### ADR-074 — DWM понижен до compatibility fallback
DWM код не удалён. Порядок Windows profiles: grpc-embedded host → grpc-embedded auto → headless SwiftShader → DWM host → DWM auto. DWM и возможное standalone window появляются только после отказа всех безоконных embedded/headless вариантов.

### ADR-075 — Framebuffer запускается до Android boot_completed
Display lifecycle отделён от guest boot lifecycle. После process spawn apk-research пытается поднять gRPC до 20 s и сообщает controller о display mode независимо от DWM. Controller немедленно запускает frame worker; Android boot framebuffer может отображаться внутри приложения до `sys.boot_completed=1`. Если gRPC появляется позже, `screen_frames` повторно проверяет client и автоматически переключается с временного ADB fallback на MMAP.

### ADR-076 — Ориентация framebuffer является свойством транспорта, а не предположением UI
Реальный тест v0.8.1 подтвердил, что Emulator `streamScreenshot` через gRPC/MMAP уже отдаёт логически ориентированный top-down raw frame. Старый `AndroidView` безусловно помечал любой RGBA/RGB raw frame как bottom-up и выполнял дополнительный vertical flip, из-за чего изображение оказывалось перевёрнуто относительно корректной Android input geometry. Начиная с v0.8.2 `LiveFrame` несёт явный `row_order`. gRPC/MMAP и gRPC bytes выставляют `top-down`; UI выполняет flip только при явном `bottom-up`. Input mapping, DOWN/MOVE/UP stream и rotation metadata этим изменением не модифицируются.

### ADR-077 — Guest boot stall не является graphics failure
Реальные тесты v0.7.x показали, что soft restart не восстанавливает affected AVD и только увеличивает время ожидания. Технический cleanup v0.8.3 окончательно закрепляет более строгую классификацию: если Emulator process уже жив, но Android не достигает `sys.boot_completed=1`, это guest/AVD state failure, а не повод перебирать display/GPU profiles. apk-research останавливает private AVD, очищает только принадлежащие ему stale processes/locks и выполняет ровно один официальный launch того же выбранного profile с `-wipe-data`. Для clean boot действует extended timeout. Если clean AVD также stalls, ошибка выходит наружу и startup завершается. Soft restart удалён. Host/auto/headless/DWM fallback сохраняется только для настоящих process/graphics startup failures до классификации guest boot stall.

### ADR-078 — v0.8.2 display/input является замороженным baseline
Реальный пользовательский тест v0.8.2 подтвердил одновременно четыре свойства: отдельное окно Emulator не вспыхивает, framebuffer ориентирован правильно, touch geometry совпадает с изображением, потоковый swipe плавный и отзывчивый. Поэтому technical cleanup v0.8.3 не меняет `AndroidView`, gRPC/MMAP row-order contract, input mapping или DOWN/MOVE/UP cadence. Дальнейшие изменения этого слоя допускаются только для конкретной воспроизводимой регрессии.

### ADR-079 — DWM fallback отделён от отвергнутого native HWND embedding
Аудит active runtime после v0.8.3 показал, что `native_emulator.py` уже фактически не содержал `SetParent`: файл обслуживал только DWM thumbnail compatibility path, но исторические имена `NativeEmulatorEmbedder`, `nativeDisplayAvailable`, `native_active` и связанные методы создавали ложное впечатление, что native HWND embedding всё ещё является частью архитектуры. v0.8.4 переименовывает модуль в `dwm_emulator.py`, класс в `DwmEmulatorPresenter`, а GUI/controller signals и state — в DWM-specific names. Исторические ADR v0.5-v0.6 остаются только журналом экспериментов; в active runtime нет SetParent path.

### ADR-080 — AndroidView не требует собственного HWND для DWM
`WA_NativeWindow` был нужен экспериментальной cross-process HWND embedding архитектуре. Текущий DWM presenter регистрирует thumbnail в top-level HWND apk-research и вычисляет destination rectangle через Qt mapping, поэтому отдельный native HWND у `AndroidView` не нужен. v0.8.4 удаляет этот флаг. Также удалены неиспользуемые virtual-screen constants, no-op `focus_embedded`, unused `restore` parameter и dead `tapRequested → controller.tap` chain. Runtime `AndroidRuntime.tap()` сохранён, поскольку он остаётся ADB fallback внутри touch lifecycle.

### ADR-081 — GUI smoke является обязательным gate для display-refactor
Release-candidate v0.8.4 прошёл unit tests и AVD acceptance, но Desktop Build остановился на standalone GUI smoke: после переименования `detach_native()` → `detach_dwm()` одна stale-ссылка осталась в `MainWindow.closeEvent`. Это не затрагивало normal runtime до закрытия окна, поэтому обычные unit tests её не обнаружили. v0.8.5 исправляет shutdown call и фиксирует правило: любое переименование display lifecycle считается завершённым только после standalone GUI open/close smoke-test собранного EXE. Непрошедший v0.8.4 не публикуется и не считается release baseline.

### ADR-082 — Единственный пользовательский runtime является fail-fast
После реального подтверждения v0.8.2 пользователь не планирует работать в degraded/compatibility display mode. Начиная с v0.8.6 Windows runtime имеет только одну поддерживаемую интерактивную архитектуру: hidden `-qt-hide-window` Emulator, gRPC `streamScreenshot` с MMAP и `AndroidView`; ввод идёт только через persistent `streamInputEvent`. DWM presenter, visible standalone Emulator, gRPC-bytes framebuffer, ADB screencap и ADB input fallbacks удалены. Если обязательный transport не запускается или прекращает работу, apk-research сообщает ошибку вместо незаметного переключения режима. Это делает дефекты primary path воспроизводимыми и не позволяет fallback-коду маскировать регрессии.

### ADR-083 — Recovery не является fallback
Startup cleanup строго private AVD, удаление stale locks после завершения принадлежащих apk-research процессов и один официальный `-wipe-data` при guest boot stall сохраняются. Они не меняют display/input architecture и поэтому считаются восстановлением штатного runtime. Повторный stall после clean boot или отказ обязательного gRPC/MMAP завершают startup с ошибкой.

### ADR-084 — Early framebuffer start and readiness gate are separate lifecycle stages
Real-PC v0.8.6 testing showed that Emulator gRPC readiness precedes guaranteed production of the first Android framebuffer frame. Starting the framebuffer worker early is useful because it allows boot frames to appear as soon as available, but it must not impose a short blocking deadline before Android boot completes. From v0.8.7 the display callback only starts the gRPC/MMAP worker non-blockingly. The mandatory first-frame gate is evaluated after `AndroidRuntime.ensure_ready()` completes boot, root enablement, orientation normalization and final transport verification. This preserves fail-fast semantics without misclassifying normal Android startup latency as a transport failure.

### ADR-085 — После v0.8.8 runtime cleanup считается завершённым
Реальный Windows-тест v0.8.7 подтвердил полную готовность среды: embedded Android загрузился, обязательный gRPC/MMAP framebuffer работал, Root/PCAP/APK readiness завершились успешно. Финальный cleanup v0.8.8 не меняет эту цепочку. Удалены только доказанно мёртвые поля/helpers и исторический package-level monkeypatch repository policy. Добавлен source-level regression contract, который запрещает возврат DWM/native display, ADB screencap/input fallback, graphics profile ladder и manual workflow triggers. Дальнейшие изменения runtime допустимы только для конкретной воспроизводимой проблемы; следующий продуктовый этап — User Actions + Research Timeline.

### ADR-086 — Full Package Manager dump является дополнительным evidence
Реальный v0.8.8 архив показал две проблемы старого contract: remote `sh -c` redirection была передана через ADB как раздельные host argv, из-за чего Android мог фактически выполнить bare `dumpsys`/bare `cmd`; кроме того, недоступность огромного verbose dump необоснованно переводила полностью пригодные logcat/screen/PCAP evidence в `partial`. Начиная с v0.8.9 remote command передаётся как единый quoted `sh -c '<command > session-file>'`. Primary full dump — bounded `cmd package dump <package>`, fallback — короткий `dumpsys -t 5 package <package>`. Lightweight `cmd package list packages --show-versioncode` сохраняется отдельно. Full dump остаётся raw evidence, но `required_for_complete_session=false`; его отсутствие сохраняется явно и не деградирует session само по себе.

### ADR-087 — Clean launch boundary находится после arm collectors
Clean launch должен быть доказуемым состоянием в момент старта исследования, а не состоянием десятки секунд до него. Поэтому v0.8.9 сначала завершает preflight, запускает logcat/screen/PCAP и переводит session в ACTIVE, затем выполняет `am force-stop <package>`, подтверждает исчезновение package process, фиксирует event и только после этого выполняет launch. Если process не исчез либо `am start -W` сообщает reuse уже работающего activity instance, clean-launch invariant считается нарушенным и ошибка выходит наружу.

### ADR-088 — Recorder coverage и frame presentation timeline различаются
Android `screenrecord` может оставаться активным, когда display не генерирует новые кадры; поэтому MP4/Winscope frame span может быть короче wall-clock времени collector process без потери самого capture. Raw MP4 никогда не дополняется синтетическими кадрами. `screen.json` хранит два независимых слоя: (1) host/target start/finish recorder process и `capture_span_seconds`, описывающие coverage; (2) Winscope v2 elapsed frame timestamps + realtime offset, описывающие фактически представленные кадры. Semantic audit требует process coverage через package launch и STOP и отдельно проверяет frame timeline.

### ADR-089 — User Action является semantic evidence, а не копией transport MOVE
gRPC input transport продолжает передавать DOWN → MOVE → UP в реальном времени, но normalized research evidence не должен содержать десятки MOVE events на один жест. DesktopController фиксирует начало pointer gesture и при release классифицирует его как `tap` либо `swipe`, сохраняя start/end coordinates, duration и distance. Wheel swipe, key и text input фиксируются отдельными semantic actions. Это не меняет input transport и не добавляет задержку в Android interaction path.

### ADR-090 — User Actions сохраняются в host clock и переводятся в target clock при анализе
GUI action timestamp возникает на Windows и не должен получать target time через синхронный ADB-вызов на каждом клике: такой вызов добавил бы latency в input path. Поэтому `user-actions.jsonl` хранит high-resolution host UTC. Timeline builder использует уже сохранённые metadata clock markers, вычисляет robust median `target_minus_host_seconds` и получает target-time estimate для корреляции с PCAP/logcat. Если calibration отсутствует, fallback явно помечается как identity/no-clock-samples.

### ADR-091 — Research Timeline является производным индексом, RAW остаётся источником истины
`research-timeline.json` не заменяет `traffic.pcap`, `logcat.txt`, screen MP4 или lifecycle JSONL. Timeline — воспроизводимый derived index: lifecycle + user actions + first-observed network markers, а у каждого action есть bounded correlation summary. PCAP parser извлекает flow tuples, DNS и best-effort TLS SNI только когда эти данные реально присутствуют в raw packet. Неуспешный protocol decode не изменяет raw evidence и не интерпретируется как отсутствие трафика.

### ADR-092 — Текстовый ввод является локальным research evidence
Для воспроизводимости user-action sequence текст, отправленный через встроенный Android keyboard path, сохраняется в `user-actions.jsonl`; adjacent characters могут группироваться в derived timeline. Это означает, что Research ZIP потенциально содержит чувствительный пользовательский ввод. Данные остаются локальными и рассматриваются как evidence наравне с logcat/screen/PCAP; документация обязана явно предупреждать об этом.

### ADR-093 — Exported Research ZIP contains the canonical refined Timeline
v0.9.1 introduced a refined Timeline engine with high-resolution Windows/Android calibration, exclusive non-overlapping post-action windows and explicit `temporal-only` attribution. A real v0.9.1 archive exposed that `ResearchOrchestrator.stop_and_export()` still called the legacy builder, while the GUI rebuilt the refined Timeline only when the archive was opened. Starting with v0.9.2 the orchestrator itself calls `timeline_engine.build_research_timeline` before export, so `02_normalized/research-timeline.json` inside the forensic ZIP is the canonical schema 0.2 representation. Acceptance must inspect the already-created ZIP and require schema 0.2, `adb-ntp-midpoint`, no causal claim, `temporal-only` attribution and exclusive correlation windows.

### ADR-094 — Windows release installer filename always contains the product version
Starting with v0.9.2 the public installer asset is named `apk-research-setup_v<version>.exe`. Inno Setup, Desktop Build, checksum generation, GitHub Release publication and WHPX acceptance all resolve the same versioned filename. `SHA256SUMS.txt` hashes that exact filename. This rule is part of the release contract for all subsequent apk-research releases.

### ADR-095 — Package network ownership derives from Android socket evidence
v0.10.0 adds a dedicated `socket_attribution` evidence layer on rooted AVD-RESEARCH. The collector resolves the target package UID, samples `/proc/net/tcp`, `tcp6`, `udp`, `udp6`, enumerates processes carrying that UID, and resolves `/proc/<pid>/fd` socket symlinks to inode numbers. The resulting temporal socket observations are joined to raw PCAP 5-tuples. This does not replace `traffic.pcap`; it adds ownership evidence to it.

### ADR-096 — Attribution confidence is evidence-graded and must not overclaim
`EXACT` requires a socket inode, exact bidirectional 5-tuple, a packet timestamp inside the directly observed socket lifetime, and unambiguous package ownership. Ownership is unambiguous either when the UID belongs only to the target package or, for a shared Android UID, when the target package process/PID is directly linked through its FD table to that socket inode. Shared UID without that target-process socket link is `UNKNOWN`, not inferred from UID alone. An exact tuple matched only inside the sampler margin is `HIGH`, not `EXACT`. Wildcard/local-endpoint evidence is weaker and is reported as `HIGH` or `MEDIUM`; an unmatched packet remains `UNKNOWN`. Every downgrade carries explicit ambiguity tags.

### ADR-097 — Socket attribution is additive evidence; capture truth remains RAW-first
The attribution collector is registered as non-core derived evidence so a future attribution-specific failure cannot erase otherwise valid raw PCAP/logcat/screen evidence. The supported rooted AVD-RESEARCH release gate nevertheless requires the standard collector to produce non-empty socket snapshots. Sampling can miss very short-lived sockets; such absence must remain `UNKNOWN`, never be converted into proof that the target package did not create the traffic.

### ADR-098 — Whole-session flow inventory preserves background package traffic
Action windows are not sufficient for network research because an app can communicate without a contemporaneous tap/swipe. v0.10.0 therefore persists `02_normalized/network-flows.json`, a whole-session inventory built from PCAP plus package attribution. It records first/last target time, packet/byte totals, DNS/TLS markers and the best ownership evidence for every observed flow.

### ADR-099 — Network ownership and user-action causality are separate claims
Socket attribution may prove that a flow belongs to the target package, but it does not by itself prove that a particular user action caused that flow. Research Timeline keeps `causal_claim=false` and `attribution=temporal-only` for action correlation even when the enclosed network flow has `owner.confidence=EXACT`. This separation is mandatory forensic semantics.

### ADR-100 — Real release acceptance must prove target process attribution
A real Windows v0.10.0 Research ZIP showed valid target-UID socket observations but zero `process_observations` and zero `pid_socket_links`. The cause was shell tokenization, not Android permissions: procfs emits `Uid:` values separated by actual TAB characters, while `IFS=" \\t"` supplies literal backslash/`t` characters rather than a TAB. v0.10.1 returns the sampler to the shell default whitespace IFS. Real AVD acceptance must now prove that normalized socket snapshots contain the launched target package process, so a release cannot pass with a silently broken PID/process layer. Unique-UID socket evidence remains valid independently, but shared-UID `EXACT` attribution requires the restored direct process → FD → inode link.

### ADR-101 — Clean restart is one Android-side stop/start transaction
A real v0.10.1 Windows archive showed that clean mode was forensically correct but visually noisy: after collectors were armed, separate host commands `am force-stop`, repeated `pidof` verification and a later `am start -W` let Launcher become a visible intermediate task and Android played close/open transitions. v0.10.2 keeps the ADR-087 boundary after collectors, but collapses stop and start into one Android shell transaction with no host polling gap and applies `FLAG_ACTIVITY_NO_ANIMATION` to the new Activity. The clean invariant is verified from the launch result itself: `LaunchState: COLD` is mandatory and existing-instance reuse is forbidden. Real AVD acceptance prewarms the package before the research session and requires the exported launch evidence to prove COLD start.

### ADR-102 — Operator preview may hold a frame; forensic screen evidence may not
A real Windows v0.10.2 Research ZIP proved both facts at once: the launch was a valid `COLD` start, and Android still rendered the outgoing task transition produced by destroying the old package window. Those requirements cannot both be removed inside Android: a force-stopped process has no live surface to keep displaying. v0.10.3 therefore separates presentation from evidence. The canonical raw `screenrecord` collector remains continuous and records the actual stop/splash/cold-start sequence. Only the desktop gRPC/MMAP operator preview holds its last already-published frame from `package_clean_restart_requested` until `package_launched`, while the underlying framebuffer stream continues collecting fresh frames. No Android animation scale, task policy or application setting is changed. Presentation callbacks are best-effort observers and are forbidden from affecting orchestrator/evidence lifecycle.

### ADR-103 — Slow metadata enrichment must not delay the clean-start boundary
A real v0.10.3 Windows archive measured about 7.15 seconds from `session_created` to `package_clean_restart_requested`; about 5.26 seconds were spent in the full Device/Package Metadata snapshot before collectors were armed. The clean restart itself is semantically required, but delaying it makes the application appear to reload unexpectedly several seconds after the user presses Start. v0.10.4 keeps the forensic invariant that logcat/screen/PCAP/socket attribution are armed before the cold start, but moves the expensive metadata snapshot and clock calibration after `package_launched`. Metadata remains required and is still captured in the same session. Real AVD release acceptance enforces a maximum 4-second session-created → clean-restart-requested latency so this UX regression cannot silently return.

### ADR-104 — v0.10.4 startup reordering is rejected; optimize only the optional dump
Real Windows testing of v0.10.4 on `com.evrasia` produced `Clean launch invariant failed: LaunchState=None`. The release changed too much of the already validated startup sequence in order to remove a UX delay. v0.10.5 therefore restores the v0.10.3 clean-launch ordering and strict COLD-start contract. Measurement of the successful v0.10.3 archive showed that Device Metadata consumed about 5.25 seconds before preflight completed, with the full Package Manager dump being optional evidence under ADR-086. The narrow fix is to defer only that full dump until session stop. Lightweight metadata remains pre-launch; continuous collectors and clean restart follow the same path as v0.10.3. The deferred dump is written before ZIP export, so evidence is preserved without placing the expensive operation on the launch critical path.

### ADR-105 — A normalized network flow is a bidirectional 5-tuple, not an attribution state
The v0.10.x inventory used different keys for attributed and unattributed packets and also included packet direction in the raw key. Real Research ZIPs therefore split one TCP connection into multiple records: early UNKNOWN outbound/inbound fragments and a later package-owned flow. v0.11.0 defines the normalized identity as a direction-independent `protocol + endpoint A + endpoint B` 5-tuple. Attribution is mutable evidence attached to that identity, not part of the identity itself. The strongest observed owner is retained and per-packet confidence counts preserve how the conclusion evolved. This keeps raw PCAP immutable while producing a stable connection-level model for analysis.

### ADR-106 — Network Analyzer reads normalized evidence, never live-mutates capture
The desktop Network Analyzer is a post-capture reader of `02_normalized/network-flows.json` inside a Research ZIP. It does not alter collectors, PCAP, attribution, Timeline or the Android runtime. The GUI is therefore downstream of evidence production and can evolve independently without risking capture regressions. The first version intentionally exposes filters/search and complete flow JSON before adding higher-level protocol decoding or causal navigation.

### ADR-107 — Timeline must reference normalized flow IDs instead of reconstructing packet flows
v0.11.0 introduced a canonical bidirectional 5-tuple inventory, but Research Timeline still rebuilt its own directional packet-flow identity. Real evidence therefore contained one connection in Network Analyzer and multiple network markers in Timeline. v0.12.0 removes that second identity system. Timeline packet windows resolve packets through the same canonical 5-tuple key into the already-built normalized inventory and persist `flow_id` references. Network events are generated one-per-normalized-flow. This establishes one connection identity across PCAP-derived normalization, Timeline and Network Analyzer.

### ADR-108 — Action/flow links are bidirectional temporal references, not causality
For each action correlation window, v0.12.0 records the normalized flows that carried packets during that window. The flow inventory receives the reverse `correlated_action_ids` list. These links are navigation/evidence references only: `causal_claim=false` and `attribution=temporal-only` remain mandatory. UI navigation may move between Timeline and Network Analyzer using these IDs, but it must not upgrade temporal proximity into causal attribution.

### ADR-109 — Packets outside TCP/UDP flow normalization remain explicit evidence
Normalized flow inventory intentionally models TCP/UDP 5-tuples only. ICMP, ARP and other packets remain exclusively in raw PCAP/Timeline packet evidence. v0.12.0 makes this boundary explicit with source, flow, non-TCP/UDP and unresolved transport counters so users can distinguish “not normalized as a flow” from “not captured”.

