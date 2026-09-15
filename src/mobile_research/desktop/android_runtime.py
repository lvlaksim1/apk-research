from __future__ import annotations

import base64
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Sequence

from mobile_research.desktop.components import (
    AVD_NAME,
    ComponentManager,
)
from mobile_research.desktop.emulator_grpc import (
    EmulatorGrpcClient,
    LiveFrame,
)

RuntimeProgress = Callable[
    [str, int | None, int | None],
    None,
]
RuntimeDisplayReady = Callable[
    [int, str, str],
    None,
]
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
        self._fallback_touch_start: (
            tuple[int, int, float] | None
        ) = None
        self._wipe_data_next_start = False

    @property
    def paths(self):
        return self.components.paths

    @property
    def native_display_supported(self) -> bool:
        return (
            self._is_windows()
            and self._display_mode == "dwm-live"
        )

    @property
    def emulator_pid(self) -> int:
        with self._process_lock:
            process = self.process
        if (
            process is None
            or process.poll() is not None
        ):
            return 0
        return int(process.pid)

    def cleanup_stale_managed_runtime(
        self,
    ) -> dict[str, object]:
        """Clean only orphaned processes/locks of Mobile Research's private AVD.

        This deliberately does not touch generic adb.exe processes or any
        Emulator whose command line does not belong to mobile_research_api35.
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

        if self._other_mobile_research_instance_running():
            report["skipped"] = (
                "another Mobile Research instance is running"
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

    def _other_mobile_research_instance_running(
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
        if not self._device_online():
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
                    "Автоматическое восстановление…",
                    None,
                    None,
                )
                self.stop()
                self.cleanup_stale_managed_runtime()
                self._boot_managed_emulator(
                    progress,
                    display_ready,
                )
        self._ensure_root(progress)
        self._normalize_initial_orientation(progress)
        self._ensure_live_transport(progress)

    def _startup_profiles(
        self,
    ) -> list[tuple[str, str, str]]:
        """Return ordered graphics/display profiles for managed boot."""

        if self._software_acceleration:
            return [
                (
                    "swiftshader",
                    "headless",
                    "software compatibility",
                )
            ]
        if self._is_windows():
            return [
                (
                    "host",
                    "dwm-live",
                    "DWM live GPU host",
                ),
                (
                    "auto",
                    "dwm-live",
                    "DWM live GPU auto",
                ),
                (
                    "host",
                    "grpc-embedded",
                    "embedded gRPC/MMAP GPU host",
                ),
                (
                    "auto",
                    "grpc-embedded",
                    "embedded gRPC/MMAP GPU auto",
                ),
                (
                    "swiftshader",
                    "headless",
                    "headless SwiftShader compatibility",
                ),
            ]
        return [
            (
                "auto",
                "headless",
                "headless display",
            )
        ]

    def _boot_managed_emulator(
        self,
        progress: RuntimeProgress | None,
        display_ready: RuntimeDisplayReady | None = None,
    ) -> None:
        """Boot with graphics fallback and one bounded AVD self-healing cycle."""

        profiles = self._startup_profiles()
        self._startup_attempts = []
        last_error: AndroidRuntimeError | None = None
        recovery_used = False

        for index, (
            gpu_mode,
            display_mode,
            label,
        ) in enumerate(profiles):
            self._gpu_mode = gpu_mode
            self._display_mode = display_mode
            self._emit(
                progress,
                f"Запуск Android: {label}",
                None,
                None,
            )
            started = time.monotonic()
            failure: AndroidRuntimeError | None = None
            recovery_stage = ""

            try:
                self._start_emulator(progress)
                self._notify_display_ready(
                    display_ready
                )
                self._wait_for_boot(progress)
            except AndroidBootTimeout as exc:
                if not recovery_used:
                    recovery_used = True
                    try:
                        recovery_stage = (
                            self._recover_stalled_boot(
                                progress,
                                display_ready,
                            )
                        )
                    except AndroidRuntimeError as recovery_exc:
                        failure = recovery_exc
                    else:
                        failure = None
                else:
                    failure = exc
            except AndroidRuntimeError as exc:
                failure = exc

            if failure is not None:
                process = self.process
                exit_code = (
                    process.returncode
                    if process is not None
                    else None
                )
                self._startup_attempts.append(
                    {
                        "label": label,
                        "gpu_mode": gpu_mode,
                        "display_mode": display_mode,
                        "status": "failed",
                        "duration_seconds": round(
                            time.monotonic() - started,
                            3,
                        ),
                        "exit_code": exit_code,
                        "error": str(failure),
                        "command": list(
                            self._last_emulator_command
                        ),
                    }
                )
                last_error = failure
                self.stop()
                if index + 1 < len(profiles):
                    self._emit(
                        progress,
                        "Android Emulator завершился. "
                        "Автоматический переход к "
                        "совместимому режиму…",
                        None,
                        None,
                    )
                continue

            self._startup_attempts.append(
                {
                    "label": label,
                    "gpu_mode": gpu_mode,
                    "display_mode": display_mode,
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
            if self._is_windows():
                if display_mode == "dwm-live":
                    message = (
                        "Android запущен: DWM live "
                        f"(GPU {gpu_mode})"
                    )
                else:
                    message = (
                        "Android запущен: framebuffer "
                        f"({display_mode}, GPU {gpu_mode})"
                    )
                if recovery_stage == "wipe-data":
                    message += " • AVD восстановлен"
                elif recovery_stage == "soft-restart":
                    message += " • после автоперезапуска"
                self._emit(
                    progress,
                    message,
                    None,
                    None,
                )
            return

        detail = (
            str(last_error)
            if last_error is not None
            else "неизвестная ошибка запуска"
        )
        raise AndroidRuntimeError(
            "Android Emulator не удалось запустить "
            "ни в одном совместимом режиме. "
            "Последняя ошибка: "
            + detail
        )

    def _notify_display_ready(
        self,
        display_ready: RuntimeDisplayReady | None,
    ) -> None:
        if (
            display_ready is not None
            and self.native_display_supported
        ):
            display_ready(
                self.emulator_pid,
                AVD_NAME,
                self._display_mode,
            )

    def _recover_stalled_boot(
        self,
        progress: RuntimeProgress | None,
        display_ready: RuntimeDisplayReady | None,
    ) -> str:
        """Try one same-data restart, then one official -wipe-data recovery."""

        self._emit(
            progress,
            "Android не завершил загрузку. "
            "Мягкий перезапуск Emulator…",
            None,
            None,
        )
        self.stop()
        self.cleanup_stale_managed_runtime()

        self._start_emulator(progress)
        self._notify_display_ready(
            display_ready
        )
        try:
            self._wait_for_boot(
                progress,
                boot_timeout=120.0,
                online_stall_timeout=60.0,
            )
            return "soft-restart"
        except AndroidBootTimeout:
            self._emit(
                progress,
                "Повторная загрузка зависла. "
                "Восстановление чистого AVD через wipe-data…",
                None,
                None,
            )
            self.stop()
            self.cleanup_stale_managed_runtime()

        self._wipe_data_next_start = True
        try:
            self._start_emulator(progress)
        finally:
            # -wipe-data is a one-launch recovery flag, never a persistent mode.
            self._wipe_data_next_start = False

        self._notify_display_ready(
            display_ready
        )
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

    def package_name_from_apk(
        self,
        apk_path: str | os.PathLike[str],
    ) -> str:
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
        return parse_aapt_package_name(result.stdout)

    def install_apk(
        self,
        apk_path: str | os.PathLike[str],
        progress: RuntimeProgress | None = None,
    ) -> str:
        apk = Path(apk_path).expanduser().resolve()
        package = self.package_name_from_apk(apk)
        self._emit(
            progress,
            f"Установка {apk.name}",
            None,
            None,
        )
        result = self._run(
            [
                str(self.paths.adb),
                "-s",
                self.SERIAL,
                "install",
                "-r",
                "-t",
                "-g",
                str(apk),
            ],
            timeout=180.0,
        )
        combined = (
            result.stdout + "\n" + result.stderr
        ).lower()
        if "success" not in combined:
            raise AndroidRuntimeError(
                "Android не подтвердил установку APK: "
                f"{result.stdout.strip()} "
                f"{result.stderr.strip()}"
            )
        self._emit(
            progress,
            f"APK установлен: {package}",
            None,
            None,
        )
        return package

    def screenshot_png(self) -> bytes:
        if not self.paths.adb.is_file():
            return b""
        creation_flags = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )
        try:
            result = subprocess.run(
                [
                    str(self.paths.adb),
                    "-s",
                    self.SERIAL,
                    "exec-out",
                    "screencap",
                    "-p",
                ],
                capture_output=True,
                timeout=5,
                check=False,
                creationflags=creation_flags,
            )
        except (
            OSError,
            subprocess.TimeoutExpired,
        ):
            return b""
        return (
            result.stdout
            if result.returncode == 0
            else b""
        )

    def screen_frames(
        self,
        stop_event: threading.Event,
        *,
        width: int = 405,
        height: int = 720,
    ):
        client = self._get_grpc_client()
        if client is not None:
            try:
                for frame in client.stream_frames(
                    width=width,
                    height=height,
                ):
                    if stop_event.is_set():
                        return
                    yield frame
                return
            except Exception:
                self._drop_grpc_client()

        while not stop_event.is_set():
            png = self.screenshot_png()
            if png:
                yield LiveFrame(
                    encoding="png",
                    data=png,
                    width=0,
                    height=0,
                    input_width=0,
                    input_height=0,
                    transport="adb-screencap",
                )
            stop_event.wait(0.12)

    def touch_down(self, x: int, y: int) -> None:
        self._fallback_touch_start = (
            int(x),
            int(y),
            time.perf_counter(),
        )
        client = self._get_grpc_client()
        if client is not None:
            try:
                client.touch_down(x, y)
                return
            except Exception:
                self._grpc_input_failures += 1

    def touch_move(self, x: int, y: int) -> None:
        client = self._get_grpc_client()
        if client is not None:
            try:
                client.touch_move(x, y)
                return
            except Exception:
                self._grpc_input_failures += 1

    def touch_up(self, x: int, y: int) -> None:
        start = self._fallback_touch_start
        self._fallback_touch_start = None
        client = self._get_grpc_client()
        if client is not None:
            try:
                client.touch_up(x, y)
                return
            except Exception:
                self._grpc_input_failures += 1
        if start is None:
            self.tap(x, y)
            return
        x1, y1, started = start
        duration_ms = max(
            1,
            int(
                (time.perf_counter() - started)
                * 1000
            ),
        )
        dx = abs(int(x) - x1)
        dy = abs(int(y) - y1)
        if dx < 12 and dy < 12:
            self.tap(x, y)
            return
        self._adb_shell(
            "input",
            "swipe",
            str(max(0, x1)),
            str(max(0, y1)),
            str(max(0, x)),
            str(max(0, y)),
            str(duration_ms),
        )

    def tap(self, x: int, y: int) -> None:
        client = self._get_grpc_client()
        if client is not None:
            try:
                client.tap(x, y)
                return
            except Exception:
                self._grpc_input_failures += 1
        self._adb_shell(
            "input",
            "tap",
            str(max(0, x)),
            str(max(0, y)),
        )

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 250,
    ) -> None:
        client = self._get_grpc_client()
        if client is not None:
            try:
                client.swipe(
                    x1,
                    y1,
                    x2,
                    y2,
                    duration_ms,
                )
                return
            except Exception:
                self._grpc_input_failures += 1
        self._adb_shell(
            "input",
            "swipe",
            str(max(0, x1)),
            str(max(0, y1)),
            str(max(0, x2)),
            str(max(0, y2)),
            str(max(1, duration_ms)),
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
        client = self._get_grpc_client()
        key = key_map.get(int(keycode))
        if client is not None and key:
            try:
                client.send_key(key)
                return
            except Exception:
                self._grpc_input_failures += 1
        self._adb_shell(
            "input",
            "keyevent",
            str(keycode),
        )

    def text(self, value: str) -> None:
        client = self._get_grpc_client()
        if client is not None:
            try:
                client.send_text(value)
                return
            except Exception:
                self._grpc_input_failures += 1
        escaped = (
            value.replace("%", "%25")
            .replace(" ", "%s")
        )
        self._adb_shell(
            "input",
            "text",
            escaped,
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
                    else "adb-screencap"
                ),
                "grpc_port": self._grpc_port,
                "gpu_mode": self._gpu_mode,
                "display_mode": self._display_mode,
                "input_rpc_failures": self._grpc_input_failures,
                "frame_transport_error": (
                    self._get_grpc_client().frame_transport_error
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
            "native_display": {
                "supported": self.native_display_supported,
                "process_id": self.emulator_pid,
                "avd_name": AVD_NAME,
                "preferred": (
                    "dwm-live"
                    if self.native_display_supported
                    else "framebuffer"
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
            if self._display_mode == "dwm-live":
                pass
            elif self._display_mode == "grpc-embedded":
                command.append("-qt-hide-window")
            else:
                command.append("-no-window")
                self._display_mode = "headless"
        else:
            command.append("-no-window")
            self._display_mode = "headless"

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
                "MOBILE_RESEARCH_SOFTWARE_EMULATOR"
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
                        "(совместимый fallback)",
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
                    "После перезагрузки снова откройте Mobile Research. "
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
    ) -> None:
        if self._grpc_port is None:
            self._emit(
                progress,
                "Интерактивный экран: ADB fallback",
                None,
                None,
            )
            return
        client: EmulatorGrpcClient | None = None
        try:
            client = EmulatorGrpcClient(self._grpc_port)
            client.wait_ready(timeout=8.0)
        except Exception:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            self._emit(
                progress,
                "Интерактивный экран: ADB fallback",
                None,
                None,
            )
            return

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
            "Интерактивный экран: Emulator gRPC",
            None,
            None,
        )

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
