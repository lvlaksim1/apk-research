from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Sequence

from apk_research.desktop.components import (
    AVD_NAME,
    ComponentManager,
)
from apk_research.desktop.emulator_grpc import (
    EmulatorGrpcClient,
)
from apk_research.desktop.home_shortcut import (
    ensure_shortcut_in_database,
    has_package_shortcut,
    launcher_database_from_listing,
    parse_launcher_favorites,
)
from apk_research.desktop.package_input import (
    ApkBadging,
    PackageInputError,
    materialize_android_package,
    parse_apk_badging,
    validate_apk_set,
)

RuntimeProgress = Callable[
    [str, int | None, int | None],
    None,
]
RuntimeDisplayReady = Callable[[], None]
_PACKAGE_BADGING_RE = re.compile(
    r"^package:\s+name='([^']+)'",
    re.MULTILINE,
)


class AndroidRuntimeError(RuntimeError):
    """Raised when the managed Android runtime cannot perform an operation."""


class AndroidBootTimeout(AndroidRuntimeError):
    """Raised when the Emulator process lives but Android never completes boot."""


def parse_aapt_package_name(output: str) -> str:
    match = _PACKAGE_BADGING_RE.search(output)
    if not match:
        raise AndroidRuntimeError(
            "Не удалось определить package name из APK"
        )
    return match.group(1)


def acceleration_provider(detail: str) -> str:
    """Normalize Android Emulator -accel-check output."""

    normalized = detail.upper()
    if "WHPX" in normalized:
        return "whpx"
    if "AEHD" in normalized or "GVM" in normalized:
        return "aehd"
    if "KVM" in normalized:
        return "kvm"
    if "HYPERVISOR.FRAMEWORK" in normalized:
        return "hypervisor-framework"
    return "unknown"


class AndroidRuntime:
    """Managed, private Android Emulator for the desktop application."""

    SERIAL = "emulator-5554"
    PORT = 5554
    SUPPORTED_WINDOWS_HYPERVISORS = {"whpx", "aehd"}

    def __init__(
        self,
        components: ComponentManager | None = None,
    ) -> None:
        self.components = components or ComponentManager()
        self.process: subprocess.Popen[bytes] | None = None
        self._process_lock = threading.Lock()
        self._grpc_lock = threading.Lock()
        self._grpc_client: EmulatorGrpcClient | None = None
        self._grpc_port: int | None = None
        self._grpc_input_failures = 0
        self._software_acceleration = False
        self._gpu_mode = "auto"
        self._display_mode = "headless"
        self._startup_attempts: list[dict[str, object]] = []
        self._last_emulator_command: list[str] = []
        self._wipe_data_next_start = False

    @property
    def paths(self):
        return self.components.paths

    def cleanup_stale_managed_runtime(
        self,
    ) -> dict[str, object]:
        """Clean only orphaned processes/locks of apk-research's private AVD.

        This deliberately does not touch generic adb.exe processes or any
        Emulator whose command line does not belong to apk_research_api35.
        """

        report: dict[str, object] = {
            "supported": self._is_windows(),
            "skipped": "",
            "detected_processes": [],
            "terminated_processes": [],
            "locks_removed": [],
            "remaining_processes": [],
        }
        if not self._is_windows():
            return report

        if self._other_apk_research_instance_running():
            report["skipped"] = (
                "another apk-research instance is running"
            )
            return report

        detected = self._windows_managed_avd_processes()
        report["detected_processes"] = [
            {
                "pid": item["pid"],
                "name": item["name"],
            }
            for item in detected
        ]

        if detected:
            # First ask the running managed AVD to shut down cleanly when ADB
            # still sees it. This is safe because process identity has already
            # been restricted to our private AVD.
            if self.paths.adb.is_file():
                try:
                    self._run(
                        [
                            str(self.paths.adb),
                            "-s",
                            self.SERIAL,
                            "emu",
                            "kill",
                        ],
                        timeout=5.0,
                        check=False,
                    )
                except Exception:
                    pass

            self._wait_for_managed_processes_to_exit(
                timeout=2.5
            )
            remaining = self._windows_managed_avd_processes()

            for item in remaining:
                pid = int(item["pid"])
                try:
                    result = subprocess.run(
                        [
                            "taskkill.exe",
                            "/PID",
                            str(pid),
                            "/T",
                            "/F",
                        ],
                        capture_output=True,
                        timeout=8.0,
                        check=False,
                        creationflags=getattr(
                            subprocess,
                            "CREATE_NO_WINDOW",
                            0,
                        ),
                    )
                    if result.returncode == 0:
                        cast_list = report[
                            "terminated_processes"
                        ]
                        assert isinstance(cast_list, list)
                        cast_list.append(
                            {
                                "pid": pid,
                                "name": item["name"],
                            }
                        )
                except (
                    OSError,
                    subprocess.TimeoutExpired,
                ):
                    pass

            self._wait_for_managed_processes_to_exit(
                timeout=5.0
            )

        remaining = self._windows_managed_avd_processes()
        report["remaining_processes"] = [
            {
                "pid": item["pid"],
                "name": item["name"],
            }
            for item in remaining
        ]

        # A lock is safe to remove only after no process belonging to this AVD
        # remains. We never delete userdata or configuration here.
        if not remaining:
            removed = self._remove_stale_avd_locks()
            report["locks_removed"] = [
                str(path)
                for path in removed
            ]

        return report

    def _wait_for_managed_processes_to_exit(
        self,
        *,
        timeout: float,
    ) -> None:
        deadline = time.monotonic() + max(
            0.0,
            float(timeout),
        )
        while time.monotonic() < deadline:
            if not self._windows_managed_avd_processes():
                return
            time.sleep(0.2)

    def _windows_managed_avd_processes(
        self,
    ) -> list[dict[str, object]]:
        if not self._is_windows():
            return []

        avd = AVD_NAME.replace("'", "''")
        emulator_root = str(
            self.paths.sdk_root / "emulator"
        ).replace("'", "''")
        script = (
            "[Console]::OutputEncoding="
            "[System.Text.UTF8Encoding]::new();"
            f"$avd='{avd}';"
            f"$root='{emulator_root}';"
            "$items=@(Get-CimInstance Win32_Process | "
            "Where-Object {"
            "($_.Name -ieq 'emulator.exe' -or "
            "$_.Name -like 'qemu-system-*.exe') -and "
            "$_.CommandLine -and "
            "$_.CommandLine.IndexOf($avd,"
            "[System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and "
            "(($_.ExecutablePath -and "
            "$_.ExecutablePath.StartsWith($root,"
            "[System.StringComparison]::OrdinalIgnoreCase)) -or "
            "$_.CommandLine.IndexOf($root,"
            "[System.StringComparison]::OrdinalIgnoreCase) -ge 0)"
            "} | Select-Object ProcessId,Name,CommandLine);"
            "$items | ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8.0,
                check=False,
                creationflags=getattr(
                    subprocess,
                    "CREATE_NO_WINDOW",
                    0,
                ),
            )
        except (
            OSError,
            subprocess.TimeoutExpired,
        ):
            return []
        if result.returncode != 0:
            return []
        raw = result.stdout.strip()
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            return []

        processes: list[dict[str, object]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            try:
                pid = int(item.get("ProcessId") or 0)
            except (TypeError, ValueError):
                continue
            if pid <= 0 or pid == os.getpid():
                continue
            processes.append(
                {
                    "pid": pid,
                    "name": str(item.get("Name") or ""),
                    "command_line": str(
                        item.get("CommandLine") or ""
                    ),
                }
            )
        return processes

    def _other_apk_research_instance_running(
        self,
    ) -> bool:
        if not self._is_windows():
            return False

        executable = Path(sys.executable)
        name = executable.name.lower()
        if "mobileresearch" not in name.replace(" ", ""):
            # Development/test Python processes must not be treated as other
            # application instances.
            return False

        path = str(executable.resolve()).replace("'", "''")
        current_pid = os.getpid()
        script = (
            "[Console]::OutputEncoding="
            "[System.Text.UTF8Encoding]::new();"
            f"$path='{path}';"
            f"$pid0={current_pid};"
            "$count=@(Get-CimInstance Win32_Process | "
            "Where-Object {"
            "$_.ProcessId -ne $pid0 -and "
            "$_.ExecutablePath -and "
            "$_.ExecutablePath.Equals($path,"
            "[System.StringComparison]::OrdinalIgnoreCase)"
            "}).Count;"
            "Write-Output $count"
        )
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5.0,
                check=False,
                creationflags=getattr(
                    subprocess,
                    "CREATE_NO_WINDOW",
                    0,
                ),
            )
            return (
                result.returncode == 0
                and int(result.stdout.strip() or "0") > 0
            )
        except (
            OSError,
            ValueError,
            subprocess.TimeoutExpired,
        ):
            return False

    def _remove_stale_avd_locks(
        self,
    ) -> list[Path]:
        removed: list[Path] = []
        roots = (
            self.paths.avd_home,
            self.paths.avd_dir,
        )
        for root in roots:
            if not root.is_dir():
                continue
            for path in root.glob("*.lock"):
                try:
                    if path.is_dir():
                        shutil.rmtree(
                            path,
                            ignore_errors=False,
                        )
                    else:
                        path.unlink(
                            missing_ok=True
                        )
                    removed.append(path)
                except OSError:
                    continue
        return removed

    def ensure_ready(
        self,
        progress: RuntimeProgress | None = None,
        display_ready: RuntimeDisplayReady | None = None,
    ) -> None:
        self.components.ensure_all(progress)
        self._emit(
            progress,
            "Проверка Android Emulator",
            None,
            None,
        )
        self._check_acceleration(progress)

        if (
            not self._device_online()
            or self._grpc_port is None
        ):
            if self._device_online():
                self._emit(
                    progress,
                    "Перезапуск private AVD в обязательном "
                    "gRPC/MMAP режиме…",
                    None,
                    None,
                )
                self.stop()
                self.cleanup_stale_managed_runtime()
            self._boot_managed_emulator(
                progress,
                display_ready,
            )
        else:
            try:
                self._wait_for_boot(progress)
            except AndroidBootTimeout:
                self._emit(
                    progress,
                    "Android найден, но загрузка зависла. "
                    "Восстановление чистого AVD…",
                    None,
                    None,
                )
                self._gpu_mode = self._preferred_gpu_mode()
                self._display_mode = self._required_display_mode()
                self._recover_stalled_boot(
                    progress,
                    display_ready,
                )

        self._ensure_root(progress)
        self._normalize_initial_orientation(progress)
        self._ensure_live_transport(progress)

    def _required_display_mode(self) -> str:
        if (
            self._is_windows()
            and not self._software_acceleration
        ):
            return "grpc-mmap"
        return "headless-grpc-mmap"

    def _boot_managed_emulator(
        self,
        progress: RuntimeProgress | None,
        display_ready: RuntimeDisplayReady | None = None,
    ) -> None:
        """Boot the one supported display/input architecture."""

        self._gpu_mode = self._preferred_gpu_mode()
        self._display_mode = self._required_display_mode()
        self._startup_attempts = []
        label = (
            "required gRPC/MMAP"
            f" GPU {self._gpu_mode}"
        )
        self._emit(
            progress,
            f"Запуск Android: {label}",
            None,
            None,
        )
        started = time.monotonic()
        recovery_stage = ""

        try:
            self._start_embedded_emulator(
                progress,
                display_ready,
            )
            try:
                self._wait_for_boot(progress)
            except AndroidBootTimeout:
                recovery_stage = self._recover_stalled_boot(
                    progress,
                    display_ready,
                )
        except AndroidRuntimeError as exc:
            process = self.process
            exit_code = (
                process.returncode
                if process is not None
                else None
            )
            self._startup_attempts.append(
                {
                    "label": label,
                    "gpu_mode": self._gpu_mode,
                    "display_mode": self._display_mode,
                    "status": "failed",
                    "duration_seconds": round(
                        time.monotonic() - started,
                        3,
                    ),
                    "exit_code": exit_code,
                    "error": str(exc),
                    "command": list(
                        self._last_emulator_command
                    ),
                }
            )
            self.stop()
            raise

        self._startup_attempts.append(
            {
                "label": label,
                "gpu_mode": self._gpu_mode,
                "display_mode": self._display_mode,
                "status": "completed",
                "duration_seconds": round(
                    time.monotonic() - started,
                    3,
                ),
                "exit_code": None,
                "error": "",
                "recovery": recovery_stage,
                "command": list(
                    self._last_emulator_command
                ),
            }
        )
        message = (
            "Android запущен: обязательный gRPC/MMAP "
            f"(GPU {self._gpu_mode})"
        )
        if recovery_stage == "wipe-data":
            message += " • AVD восстановлен"
        self._emit(
            progress,
            message,
            None,
            None,
        )

    def _start_embedded_emulator(
        self,
        progress: RuntimeProgress | None,
        display_ready: RuntimeDisplayReady | None,
    ) -> None:
        self._start_emulator(progress)
        self._ensure_live_transport(
            progress,
            timeout=20.0,
        )
        if display_ready is not None:
            display_ready()

    def _recover_stalled_boot(
        self,
        progress: RuntimeProgress | None,
        display_ready: RuntimeDisplayReady | None,
    ) -> str:
        """Perform exactly one official -wipe-data recovery launch."""

        self._emit(
            progress,
            "Android не завершил загрузку. "
            "Восстановление чистого AVD через wipe-data…",
            None,
            None,
        )
        self.stop()
        self.cleanup_stale_managed_runtime()

        self._gpu_mode = self._preferred_gpu_mode()
        self._display_mode = self._required_display_mode()
        self._wipe_data_next_start = True
        try:
            self._start_embedded_emulator(
                progress,
                display_ready,
            )
        finally:
            self._wipe_data_next_start = False

        try:
            self._wait_for_boot(
                progress,
                boot_timeout=240.0,
                online_stall_timeout=120.0,
            )
        except AndroidRuntimeError:
            self.stop()
            self.cleanup_stale_managed_runtime()
            raise
        return "wipe-data"

    def _apk_badging(
        self,
        apk_path: str | os.PathLike[str],
    ) -> ApkBadging:
        apk = Path(apk_path).expanduser().resolve()
        if not apk.is_file():
            raise AndroidRuntimeError(f"APK не найден: {apk}")
        if not self.paths.aapt2.is_file():
            raise AndroidRuntimeError(
                "Компонент aapt2 ещё не установлен"
            )
        result = self._run(
            [
                str(self.paths.aapt2),
                "dump",
                "badging",
                str(apk),
            ],
            timeout=30.0,
        )
        try:
            return parse_apk_badging(result.stdout, apk)
        except PackageInputError as exc:
            raise AndroidRuntimeError(str(exc)) from exc

    def package_name_from_apk(
        self,
        apk_path: str | os.PathLike[str],
    ) -> str:
        return self._apk_badging(apk_path).package_name

    def device_abis(self) -> tuple[str, ...]:
        result = self._adb_shell(
            "getprop",
            "ro.product.cpu.abilist",
            timeout=10.0,
            check=False,
        )
        values = [
            value.strip()
            for value in result.stdout.strip().split(",")
            if value.strip()
        ]
        if not values:
            fallback = self._adb_shell(
                "getprop",
                "ro.product.cpu.abi",
                timeout=10.0,
                check=False,
            ).stdout.strip()
            if fallback:
                values = [fallback]
        return tuple(dict.fromkeys(values))

    def _resolve_main_component(
        self,
        category: str,
        package_name: str | None = None,
    ) -> str:
        command = [
            "cmd",
            "package",
            "resolve-activity",
            "--brief",
            "-a",
            "android.intent.action.MAIN",
            "-c",
            category,
        ]
        if package_name:
            command.append(package_name)
        result = self._adb_shell(
            *command,
            timeout=15.0,
            check=False,
        )
        candidates = [
            line.strip()
            for line in result.stdout.splitlines()
            if "/" in line and " " not in line.strip()
        ]
        if not candidates:
            if package_name:
                raise AndroidRuntimeError(
                    "У приложения нет запускаемой Activity: "
                    f"{package_name}"
                )
            raise AndroidRuntimeError(
                "Не удалось определить системный Launcher Android"
            )
        return candidates[-1]

    def ensure_home_shortcut(
        self,
        package_name: str,
        label: str,
    ) -> str:
        component = self._resolve_main_component(
            "android.intent.category.LAUNCHER",
            package_name,
        )
        launcher_component = self._resolve_main_component(
            "android.intent.category.HOME",
        )
        launcher_package = launcher_component.split("/", 1)[0]
        if launcher_package != "com.android.launcher3":
            raise AndroidRuntimeError(
                "Автоматическое добавление ярлыка поддерживается "
                "только управляемым Launcher3; найден: "
                f"{launcher_package}"
            )

        uri = (
            "content://com.android.launcher3.settings/favorites"
        )
        query = self._adb_shell(
            "content",
            "query",
            "--uri",
            uri,
            timeout=15.0,
            check=False,
        )
        if query.returncode != 0:
            raise AndroidRuntimeError(
                "Не удалось прочитать рабочий стол Launcher3: "
                + (
                    query.stderr.strip()
                    or query.stdout.strip()
                    or "нет диагностики"
                )
            )

        favorites = parse_launcher_favorites(
            query.stdout
        )
        if has_package_shortcut(
            favorites,
            package_name,
        ):
            self._adb_shell(
                "input",
                "keyevent",
                "KEYCODE_HOME",
                timeout=10.0,
                check=False,
            )
            return "existing"

        database_dir = (
            f"/data/user/0/{launcher_package}/databases"
        )
        listing = self._adb_shell(
            "ls",
            database_dir,
            timeout=10.0,
            check=False,
        )
        database_name, columns, rows = (
            launcher_database_from_listing(
                listing.stdout
            )
        )
        remote_database = (
            f"{database_dir}/{database_name}"
        )

        self._adb_shell(
            "am",
            "start",
            "-a",
            "android.settings.SETTINGS",
            timeout=15.0,
            check=False,
        )
        self._adb_shell(
            "am",
            "force-stop",
            launcher_package,
            timeout=10.0,
            check=False,
        )

        state = "created"
        with tempfile.TemporaryDirectory(
            prefix="apk-research-launcher-"
        ) as temporary:
            local_database = (
                Path(temporary) / database_name
            )
            pulled = self._run(
                [
                    str(self.paths.adb),
                    "-s",
                    self.SERIAL,
                    "pull",
                    remote_database,
                    str(local_database),
                ],
                timeout=30.0,
                check=False,
            )
            if (
                pulled.returncode != 0
                or not local_database.is_file()
            ):
                raise AndroidRuntimeError(
                    "Не удалось получить базу рабочего стола Launcher3: "
                    + (
                        pulled.stderr.strip()
                        or pulled.stdout.strip()
                        or remote_database
                    )
                )

            try:
                state = ensure_shortcut_in_database(
                    local_database,
                    package_name=package_name,
                    label=label,
                    component=component,
                    columns=columns,
                    rows=rows,
                )
            except (OSError, ValueError) as exc:
                raise AndroidRuntimeError(
                    "Не удалось подготовить ярлык Launcher3: "
                    + str(exc)
                ) from exc

            if state == "created":
                staging = (
                    "/data/local/tmp/"
                    "apk-research-launcher.db"
                )
                pushed = self._run(
                    [
                        str(self.paths.adb),
                        "-s",
                        self.SERIAL,
                        "push",
                        str(local_database),
                        staging,
                    ],
                    timeout=30.0,
                    check=False,
                )
                if pushed.returncode != 0:
                    raise AndroidRuntimeError(
                        "Не удалось вернуть базу Launcher3 на Android: "
                        + (
                            pushed.stderr.strip()
                            or pushed.stdout.strip()
                            or "нет диагностики"
                        )
                    )

                replaced = self._adb_shell(
                    "sh",
                    "-c",
                    (
                        f"rm -f {remote_database}-wal "
                        f"{remote_database}-shm "
                        f"&& cat {staging} > {remote_database} "
                        f"&& sync && rm -f {staging}"
                    ),
                    timeout=20.0,
                    check=False,
                )
                if replaced.returncode != 0:
                    raise AndroidRuntimeError(
                        "Не удалось обновить базу рабочего стола Launcher3: "
                        + (
                            replaced.stderr.strip()
                            or replaced.stdout.strip()
                            or "нет диагностики"
                        )
                    )

        self._adb_shell(
            "input",
            "keyevent",
            "KEYCODE_HOME",
            timeout=10.0,
            check=False,
        )
        time.sleep(1.0)

        verify = self._adb_shell(
            "content",
            "query",
            "--uri",
            uri,
            timeout=15.0,
            check=False,
        )
        verified = parse_launcher_favorites(
            verify.stdout
        )
        if not has_package_shortcut(
            verified,
            package_name,
        ):
            raise AndroidRuntimeError(
                "Launcher3 не подтвердил ярлык после перезапуска "
                f"для {package_name}. Ответ: "
                + (
                    verify.stderr.strip()
                    or verify.stdout.strip()
                    or "пустой"
                )
            )
        return state

    def install_package(
        self,
        package_path: str | os.PathLike[str],
        progress: RuntimeProgress | None = None,
    ) -> str:
        source = Path(package_path).expanduser().resolve()
        try:
            context = materialize_android_package(source)
            with context as materialized:
                badgings = [
                    self._apk_badging(path)
                    for path in materialized.apk_files
                ]
                device_abis = self.device_abis()
                self._emit(
                    progress,
                    "Архитектуры эмулятора: "
                    + (
                        ", ".join(device_abis)
                        if device_abis
                        else "не определены"
                    ),
                    None,
                    None,
                )
                try:
                    package, ordered = validate_apk_set(
                        badgings,
                        device_abis=device_abis,
                    )
                except PackageInputError as exc:
                    raise AndroidRuntimeError(str(exc)) from exc

                apk_files = [
                    item.path
                    for item in ordered
                ]
                skipped = len(badgings) - len(ordered)
                self._emit(
                    progress,
                    (
                        f"Установка {source.name}"
                        if materialized.source_format == "apk"
                        else (
                            f"Установка XAPK {source.name}: "
                            f"{len(apk_files)} совместимых APK-частей"
                            + (
                                f", исключено несовместимых ABI: {skipped}"
                                if skipped
                                else ""
                            )
                        )
                    ),
                    None,
                    None,
                )

                if len(apk_files) == 1:
                    command = [
                        str(self.paths.adb),
                        "-s",
                        self.SERIAL,
                        "install",
                        "-r",
                        "-t",
                        "-g",
                        str(apk_files[0]),
                    ]
                else:
                    command = [
                        str(self.paths.adb),
                        "-s",
                        self.SERIAL,
                        "install-multiple",
                        "-r",
                        "-t",
                        "-g",
                        *[
                            str(path)
                            for path in apk_files
                        ],
                    ]

                result = self._run(
                    command,
                    timeout=300.0,
                    check=False,
                )
                combined = (
                    result.stdout + "\n" + result.stderr
                ).strip()
                lowered = combined.lower()
                if result.returncode != 0 or "success" not in lowered:
                    if "install_failed_no_matching_abis" in lowered:
                        package_abis = sorted(
                            {
                                abi
                                for item in badgings
                                for abi in item.native_codes
                                if abi
                            }
                        )
                        raise AndroidRuntimeError(
                            "Приложение нельзя установить: "
                            "Android сообщает INSTALL_FAILED_NO_MATCHING_ABIS. "
                            "Архитектуры пакета: "
                            + (
                                ", ".join(package_abis)
                                if package_abis
                                else "не удалось определить"
                            )
                            + "; архитектуры эмулятора: "
                            + (
                                ", ".join(device_abis)
                                if device_abis
                                else "не удалось определить"
                            )
                            + "."
                        )
                    raise AndroidRuntimeError(
                        "Android не подтвердил установку пакета: "
                        + (combined or "нет диагностики")
                    )

                if materialized.obb_files:
                    remote_dir = (
                        f"/sdcard/Android/obb/{package}"
                    )
                    self._emit(
                        progress,
                        (
                            "Перенос OBB: "
                            f"{len(materialized.obb_files)} файл(ов)"
                        ),
                        None,
                        None,
                    )
                    self._adb_shell(
                        "mkdir",
                        "-p",
                        remote_dir,
                        timeout=20.0,
                    )
                    for index, obb in enumerate(
                        materialized.obb_files,
                        start=1,
                    ):
                        self._emit(
                            progress,
                            f"OBB {index}/"
                            f"{len(materialized.obb_files)}: "
                            f"{obb.name}",
                            index,
                            len(materialized.obb_files),
                        )
                        self._run(
                            [
                                str(self.paths.adb),
                                "-s",
                                self.SERIAL,
                                "push",
                                str(obb),
                                f"{remote_dir}/{obb.name}",
                            ],
                            timeout=300.0,
                        )

                base_badging = ordered[0]
                shortcut_state = self.ensure_home_shortcut(
                    package,
                    base_badging.app_label or package,
                )
                self._emit(
                    progress,
                    (
                        "Ярлык на рабочем столе уже существует: "
                        if shortcut_state == "existing"
                        else "Ярлык добавлен на рабочий стол: "
                    )
                    + (base_badging.app_label or package),
                    None,
                    None,
                )

                self._emit(
                    progress,
                    f"Пакет установлен: {package}",
                    None,
                    None,
                )
                return package
        except PackageInputError as exc:
            raise AndroidRuntimeError(str(exc)) from exc

    def install_apk(
        self,
        apk_path: str | os.PathLike[str],
        progress: RuntimeProgress | None = None,
    ) -> str:
        """Backward-compatible wrapper for the unified APK/XAPK installer."""
        return self.install_package(apk_path, progress)

    def screen_frames(
        self,
        stop_event: threading.Event,
        *,
        width: int = 405,
        height: int = 720,
    ):
        client = self._require_grpc_client()
        try:
            for frame in client.stream_frames(
                width=width,
                height=height,
            ):
                if stop_event.is_set():
                    return
                if frame.transport != "grpc-mmap":
                    raise AndroidRuntimeError(
                        "Получен неподдерживаемый framebuffer "
                        f"transport: {frame.transport}"
                    )
                yield frame
        except Exception as exc:
            if stop_event.is_set():
                return
            self._drop_grpc_client()
            if isinstance(exc, AndroidRuntimeError):
                raise
            raise AndroidRuntimeError(
                "Обязательный gRPC/MMAP framebuffer "
                "stream остановлен: "
                + (str(exc) or exc.__class__.__name__)
            ) from exc

    def _run_required_input(
        self,
        method: str,
        *args,
    ) -> None:
        client = self._require_grpc_client()
        try:
            getattr(client, method)(*args)
        except Exception as exc:
            self._grpc_input_failures += 1
            raise AndroidRuntimeError(
                "Обязательный Emulator gRPC "
                "streamInputEvent недоступен: "
                + (str(exc) or exc.__class__.__name__)
            ) from exc

    def touch_down(self, x: int, y: int) -> None:
        self._run_required_input(
            "touch_down",
            x,
            y,
        )

    def touch_move(self, x: int, y: int) -> None:
        self._run_required_input(
            "touch_move",
            x,
            y,
        )

    def touch_up(self, x: int, y: int) -> None:
        self._run_required_input(
            "touch_up",
            x,
            y,
        )

    def touch_points(
        self,
        points: Sequence[
            tuple[int, int, int, int]
        ],
    ) -> None:
        self._run_required_input(
            "touch_points",
            tuple(points),
        )

    def tap(self, x: int, y: int) -> None:
        self._run_required_input(
            "tap",
            x,
            y,
        )

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 250,
    ) -> None:
        self._run_required_input(
            "swipe",
            x1,
            y1,
            x2,
            y2,
            duration_ms,
        )

    def keyevent(self, keycode: int) -> None:
        key_map = {
            3: "GoHome",
            4: "GoBack",
            19: "ArrowUp",
            20: "ArrowDown",
            21: "ArrowLeft",
            22: "ArrowRight",
            61: "Tab",
            66: "Enter",
            67: "Backspace",
        }
        key = key_map.get(int(keycode))
        if not key:
            raise AndroidRuntimeError(
                f"Неподдерживаемый Android keycode: {keycode}"
            )
        self._run_required_input(
            "send_key",
            key,
        )

    def text(self, value: str) -> None:
        self._run_required_input(
            "send_text",
            value,
        )

    def stop(self) -> None:
        self._drop_grpc_client()
        self._grpc_port = None
        if self.paths.adb.is_file():
            try:
                self._run(
                    [
                        str(self.paths.adb),
                        "-s",
                        self.SERIAL,
                        "emu",
                        "kill",
                    ],
                    timeout=10.0,
                    check=False,
                )
            except Exception:
                pass
        with self._process_lock:
            process = self.process
            self.process = None
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    def reset_userdata(self) -> None:
        self.stop()
        self.components.reset_avd_userdata()

    def diagnostics(self) -> dict[str, object]:
        state = self.components.state()
        data: dict[str, object] = {
            "components": state.to_dict(),
            "paths": self.paths.to_dict(),
            "serial": self.SERIAL,
            "device_online": self._device_online(),
            "interactive_transport": {
                "active": (
                    self._get_grpc_client().frame_transport
                    if self._get_grpc_client() is not None
                    else "unavailable"
                ),
                "required": "grpc-mmap",
                "input_required": "streamInputEvent",
                "grpc_port": self._grpc_port,
                "gpu_mode": self._gpu_mode,
                "display_mode": self._display_mode,
                "input_rpc_failures": self._grpc_input_failures,
                "frame_transport_error": (
                    self._get_grpc_client().frame_transport_error
                    if self._get_grpc_client() is not None
                    else ""
                ),
                "input_stream_error": (
                    self._get_grpc_client().input_stream_error
                    if self._get_grpc_client() is not None
                    else ""
                ),
                "startup_attempts": list(
                    self._startup_attempts
                ),
                "emulator_command": list(
                    self._last_emulator_command
                ),
            },
        }

        versions: dict[str, object] = {}
        version_commands = (
            (
                "adb",
                state.platform_tools,
                [str(self.paths.adb), "version"],
            ),
            (
                "emulator",
                state.emulator,
                [str(self.paths.emulator), "-version"],
            ),
            (
                "aapt2",
                state.build_tools,
                [str(self.paths.aapt2), "version"],
            ),
        )
        for name, available, command in version_commands:
            if not available:
                versions[name] = {
                    "available": False,
                    "version": "",
                }
                continue
            try:
                result = self._run(
                    command,
                    timeout=20.0,
                    check=False,
                )
                text = (
                    result.stdout
                    or result.stderr
                ).strip()
                versions[name] = {
                    "available": result.returncode == 0,
                    "returncode": result.returncode,
                    "version": (
                        text.splitlines()[0]
                        if text
                        else ""
                    ),
                }
            except Exception as exc:
                versions[name] = {
                    "available": False,
                    "version": "",
                    "error": str(exc),
                }
        data["versions"] = versions

        if state.emulator:
            try:
                result = self._run(
                    [
                        str(self.paths.emulator),
                        "-accel-check",
                    ],
                    timeout=20.0,
                    check=False,
                )
                detail = (
                    result.stdout
                    or result.stderr
                ).strip()
                data["acceleration"] = {
                    "available": result.returncode == 0,
                    "returncode": result.returncode,
                    "provider": acceleration_provider(detail),
                    "detail": detail,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            except Exception as exc:
                data["acceleration"] = {
                    "available": False,
                    "error": str(exc),
                }

        if data["device_online"]:
            try:
                uid = self._adb_shell(
                    "id",
                    "-u",
                    check=False,
                )
                data["root"] = (
                    uid.returncode == 0
                    and uid.stdout.strip() == "0"
                )
                tcpdump = self._adb_shell(
                    "tcpdump",
                    "--version",
                    check=False,
                )
                version_text = (
                    tcpdump.stdout
                    or tcpdump.stderr
                )
                data["tcpdump"] = {
                    "available": tcpdump.returncode == 0,
                    "version": (
                        version_text.splitlines()[0]
                        if version_text
                        else ""
                    ),
                }
            except Exception as exc:
                data["target_probe_error"] = str(exc)
        return data

    def _start_emulator(
        self,
        progress: RuntimeProgress | None,
    ) -> None:
        self._emit(
            progress,
            "Запуск встроенного Android",
            None,
            None,
        )
        log_path = self.paths.root / "emulator.log"
        log_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        log_handle = log_path.open("ab")
        self._drop_grpc_client()
        self._grpc_port = self._find_free_tcp_port()
        command = self._emulator_command()
        self._last_emulator_command = list(command)
        creation_flags = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=self.components.environment(),
                creationflags=creation_flags,
            )
        except OSError as exc:
            log_handle.close()
            raise AndroidRuntimeError(
                "Не удалось запустить Android Emulator: "
                f"{exc}"
            ) from exc
        finally:
            try:
                log_handle.close()
            except Exception:
                pass
        with self._process_lock:
            self.process = process

    def _emulator_command(self) -> list[str]:
        command = [
            str(self.paths.emulator),
            f"@{AVD_NAME}",
            "-port",
            str(self.PORT),
            "-gpu",
            (
                "swiftshader"
                if self._software_acceleration
                else self._gpu_mode
            ),
            "-grpc",
            str(self._grpc_port or self._find_free_tcp_port()),
            "-no-snapshot",
            "-noaudio",
            "-no-boot-anim",
            "-crash-report-mode",
            "disabled",
        ]
        if self._wipe_data_next_start:
            command.append("-wipe-data")

        if (
            self._is_windows()
            and not self._software_acceleration
        ):
            command.append("-qt-hide-window")
            self._display_mode = "grpc-mmap"
        else:
            command.append("-no-window")
            self._display_mode = "headless-grpc-mmap"

        if self._software_acceleration:
            command.extend(
                [
                    "-accel",
                    "off",
                    "-cores",
                    "2",
                    "-memory",
                    "2048",
                ]
            )
        return command

    def _wait_for_boot(
        self,
        progress: RuntimeProgress | None,
        *,
        boot_timeout: float | None = None,
        online_stall_timeout: float | None = None,
    ) -> None:
        if boot_timeout is None:
            boot_timeout = (
                900.0
                if self._software_acceleration
                else 150.0
            )
        if online_stall_timeout is None:
            online_stall_timeout = (
                240.0
                if self._software_acceleration
                else 75.0
            )

        started = time.monotonic()
        deadline = started + boot_timeout
        online_since: float | None = None

        while time.monotonic() < deadline:
            self._ensure_process_alive()
            now = time.monotonic()
            if self._device_online():
                if online_since is None:
                    online_since = now
                result = self._adb_shell(
                    "getprop",
                    "sys.boot_completed",
                    timeout=10.0,
                    check=False,
                )
                if (
                    result.returncode == 0
                    and result.stdout.strip() == "1"
                ):
                    self._emit(
                        progress,
                        "Android загружен",
                        None,
                        None,
                    )
                    return
                if (
                    online_since is not None
                    and now - online_since
                    >= online_stall_timeout
                ):
                    raise AndroidBootTimeout(
                        "ADB доступен, но Android не завершил "
                        "загрузку за "
                        f"{int(online_stall_timeout)} секунд"
                    )
            else:
                online_since = None

            remaining = max(
                0,
                int(deadline - now),
            )
            self._emit(
                progress,
                f"Загрузка Android… {remaining} с",
                None,
                None,
            )
            time.sleep(2.0)

        raise AndroidBootTimeout(
            "Android Emulator не завершил загрузку за "
            f"{int(boot_timeout)} секунд"
        )

    def _ensure_root(
        self,
        progress: RuntimeProgress | None,
    ) -> None:
        self._emit(
            progress,
            "Включение исследовательского root ADB",
            None,
            None,
        )
        deadline = time.monotonic() + 60.0
        last_error = ""
        while time.monotonic() < deadline:
            result = self._run(
                [
                    str(self.paths.adb),
                    "-s",
                    self.SERIAL,
                    "root",
                ],
                timeout=15.0,
                check=False,
            )
            last_error = (
                result.stdout
                + "\n"
                + result.stderr
            ).strip()
            time.sleep(1.0)
            uid = self._adb_shell(
                "id",
                "-u",
                timeout=10.0,
                check=False,
            )
            if (
                uid.returncode == 0
                and uid.stdout.strip() == "0"
            ):
                self._emit(
                    progress,
                    "Research Android готов",
                    None,
                    None,
                )
                return
            time.sleep(2.0)
        raise AndroidRuntimeError(
            "Не удалось получить root ADB для "
            "AVD-RESEARCH. "
            + last_error
        )

    def _check_acceleration(
        self,
        progress: RuntimeProgress | None = None,
    ) -> None:
        if (
            os.environ.get(
                "APK_RESEARCH_SOFTWARE_EMULATOR"
            )
            == "1"
        ):
            self._software_acceleration = True
            return

        result = self._acceleration_check()
        detail = (
            result.stdout
            or result.stderr
        ).strip()
        provider = acceleration_provider(detail)

        if result.returncode == 0:
            if not self._is_windows():
                self._software_acceleration = False
                return
            if provider in self.SUPPORTED_WINDOWS_HYPERVISORS:
                self._software_acceleration = False
                if provider == "aehd":
                    self._emit(
                        progress,
                        "Аппаратное ускорение: AEHD "
                        "(совместимый provider)",
                        None,
                        None,
                    )
                return

        if self._is_windows():
            setup_code = self._enable_windows_hypervisor_features()
            result = self._acceleration_check()
            detail = (
                result.stdout
                or result.stderr
            ).strip()
            provider = acceleration_provider(detail)

            if (
                result.returncode == 0
                and provider in self.SUPPORTED_WINDOWS_HYPERVISORS
            ):
                self._software_acceleration = False
                if provider == "aehd":
                    self._emit(
                        progress,
                        "WHPX включён; до следующей "
                        "перезагрузки используется AEHD",
                        None,
                        None,
                    )
                return

            if setup_code == 10:
                raise AndroidRuntimeError(
                    "Windows Hypervisor Platform (WHPX) включён. "
                    "Чтобы Windows загрузила системный гипервизор, "
                    "нужно перезагрузить компьютер. Windows может "
                    "не показывать отдельный запрос на перезагрузку. "
                    "После перезагрузки снова откройте apk-research. "
                    "Диагностика Android Emulator: "
                    + detail
                )

            if setup_code not in {0, None}:
                raise AndroidRuntimeError(
                    "Не удалось автоматически настроить Windows "
                    "Hypervisor Platform. Код настройки: "
                    f"{setup_code}. Проверьте, что запрос UAC был "
                    "разрешён, и повторите попытку. Диагностика: "
                    + detail
                )

        raise AndroidRuntimeError(
            "Аппаратное ускорение Android Emulator недоступно. "
            "Проверьте аппаратную виртуализацию VT-x/AMD-V "
            "в BIOS/UEFI. На Windows после первого включения "
            "WHPX может потребоваться перезагрузка. Диагностика: "
            + detail
        )

    def _acceleration_check(
        self,
    ) -> subprocess.CompletedProcess[str]:
        return self._run(
            [
                str(self.paths.emulator),
                "-accel-check",
            ],
            timeout=20.0,
            check=False,
        )

    @staticmethod
    def _is_windows() -> bool:
        return os.name == "nt"

    def _enable_windows_hypervisor_features(
        self,
    ) -> int | None:
        """Enable WHPX with a single UAC prompt.

        Exit code 10 means that Windows configuration changed and
        a reboot is required before WHPX can become active.
        """

        elevated_script = (
            "$ErrorActionPreference='Stop';"
            "$restart=$false;"
            "$feature=Get-WindowsOptionalFeature "
            "-Online -FeatureName HypervisorPlatform;"
            "$state=[string]$feature.State;"
            "if($state -eq 'EnablePending'){"
            "$restart=$true;"
            "}elseif($state -ne 'Enabled'){"
            "$r=Enable-WindowsOptionalFeature -Online "
            "-FeatureName HypervisorPlatform -All -NoRestart;"
            "$restart=$true;"
            "if($r.RestartNeeded){$restart=$true;}"
            "};"
            "$bcd=(& bcdedit.exe /enum '{current}' 2>&1 "
            "| Out-String);"
            "if($LASTEXITCODE -ne 0){exit 22};"
            "if($bcd -notmatch "
            "'hypervisorlaunchtype\\s+Auto'){"
            "& bcdedit.exe /set hypervisorlaunchtype Auto "
            "| Out-Null;"
            "if($LASTEXITCODE -ne 0){exit 23};"
            "$restart=$true;"
            "};"
            "if($restart){exit 10};"
            "exit 0"
        )
        encoded = base64.b64encode(
            elevated_script.encode("utf-16-le")
        ).decode("ascii")
        command = (
            "$ErrorActionPreference='Stop';"
            "try{"
            "$p=Start-Process powershell.exe -Verb RunAs "
            "-WindowStyle Hidden -Wait -PassThru "
            "-ArgumentList @("
            "'-NoProfile','-ExecutionPolicy','Bypass',"
            "'-EncodedCommand','"
            + encoded
            + "');"
            "exit $p.ExitCode;"
            "}catch{exit 122;}"
        )
        creation_flags = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command,
                ],
                timeout=240,
                check=False,
                creationflags=creation_flags,
            )
            return int(result.returncode)
        except (
            OSError,
            subprocess.TimeoutExpired,
        ):
            return None

    def _normalize_initial_orientation(
        self,
        progress: RuntimeProgress | None,
    ) -> None:
        self._emit(
            progress,
            "Нормализация ориентации Android",
            None,
            None,
        )
        commands = (
            (
                "wm",
                "user-rotation",
                "lock",
                "0",
            ),
            (
                "settings",
                "put",
                "system",
                "accelerometer_rotation",
                "0",
            ),
            (
                "settings",
                "put",
                "system",
                "user_rotation",
                "0",
            ),
        )
        for command in commands:
            self._adb_shell(
                *command,
                timeout=10.0,
                check=False,
            )

    def _ensure_live_transport(
        self,
        progress: RuntimeProgress | None,
        *,
        timeout: float = 8.0,
    ) -> None:
        existing = self._get_grpc_client()
        if existing is not None:
            return

        if self._grpc_port is None:
            raise AndroidRuntimeError(
                "Обязательный Emulator gRPC endpoint "
                "не был создан"
            )

        client: EmulatorGrpcClient | None = None
        try:
            client = EmulatorGrpcClient(self._grpc_port)
            client.wait_ready(
                timeout=max(0.5, float(timeout))
            )
        except Exception as exc:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            raise AndroidRuntimeError(
                "Обязательный Emulator gRPC transport "
                "недоступен: "
                + (str(exc) or exc.__class__.__name__)
            ) from exc

        with self._grpc_lock:
            previous = self._grpc_client
            self._grpc_client = client
        if previous is not None:
            try:
                previous.close()
            except Exception:
                pass
        self._emit(
            progress,
            "Интерактивный transport: обязательный "
            "Emulator gRPC/MMAP",
            None,
            None,
        )

    def _require_grpc_client(
        self,
    ) -> EmulatorGrpcClient:
        client = self._get_grpc_client()
        if client is None:
            raise AndroidRuntimeError(
                "Обязательный Emulator gRPC/MMAP "
                "transport не активен"
            )
        return client

    def _get_grpc_client(
        self,
    ) -> EmulatorGrpcClient | None:
        with self._grpc_lock:
            return self._grpc_client

    def _drop_grpc_client(self) -> None:
        with self._grpc_lock:
            client = self._grpc_client
            self._grpc_client = None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    @staticmethod
    def _find_free_tcp_port() -> int:
        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        ) as handle:
            handle.bind(("127.0.0.1", 0))
            return int(handle.getsockname()[1])

    def _preferred_gpu_mode(self) -> str:
        if self._software_acceleration:
            return "swiftshader"
        if self._is_windows():
            return "host"
        return "auto"

    def _device_online(self) -> bool:
        if not self.paths.adb.is_file():
            return False
        result = self._run(
            [
                str(self.paths.adb),
                "devices",
            ],
            timeout=10.0,
            check=False,
        )
        return any(
            line.split()[:2]
            == [self.SERIAL, "device"]
            for line in result.stdout.splitlines()
        )

    def _ensure_process_alive(self) -> None:
        with self._process_lock:
            process = self.process
        if (
            process is not None
            and process.poll() is not None
        ):
            log_path = self.paths.root / "emulator.log"
            tail = ""
            if log_path.is_file():
                try:
                    tail = log_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )[-4000:]
                except OSError:
                    pass
            raise AndroidRuntimeError(
                "Android Emulator завершился с кодом "
                f"{process.returncode}.\n{tail}"
            )

    def _adb_shell(
        self,
        *arguments: str,
        timeout: float = 15.0,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return self._run(
            [
                str(self.paths.adb),
                "-s",
                self.SERIAL,
                "shell",
                *arguments,
            ],
            timeout=timeout,
            check=check,
        )

    def _run(
        self,
        command: Sequence[str],
        *,
        timeout: float,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        creation_flags = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )
        try:
            result = subprocess.run(
                list(command),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                env=self.components.environment(),
                creationflags=creation_flags,
            )
        except subprocess.TimeoutExpired as exc:
            raise AndroidRuntimeError(
                "Команда Android превысила таймаут "
                f"{timeout:g} с"
            ) from exc
        except OSError as exc:
            raise AndroidRuntimeError(
                "Не удалось запустить Android-команду: "
                f"{exc}"
            ) from exc
        if check and result.returncode != 0:
            detail = (
                result.stderr.strip()
                or result.stdout.strip()
                or "нет диагностики"
            )
            raise AndroidRuntimeError(
                "Android-команда завершилась с кодом "
                f"{result.returncode}: {detail}"
            )
        return result

    @staticmethod
    def _emit(
        callback: RuntimeProgress | None,
        message: str,
        current: int | None,
        total: int | None,
    ) -> None:
        if callback is not None:
            callback(message, current, total)
