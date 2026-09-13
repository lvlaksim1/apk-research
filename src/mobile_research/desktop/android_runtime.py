from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Sequence

from mobile_research.desktop.components import (
    AVD_NAME,
    ComponentManager,
)

RuntimeProgress = Callable[
    [str, int | None, int | None],
    None,
]
_PACKAGE_BADGING_RE = re.compile(
    r"^package:\s+name='([^']+)'",
    re.MULTILINE,
)


class AndroidRuntimeError(RuntimeError):
    """Raised when the managed Android runtime cannot perform an operation."""


def parse_aapt_package_name(output: str) -> str:
    match = _PACKAGE_BADGING_RE.search(output)
    if not match:
        raise AndroidRuntimeError(
            "Не удалось определить package name из APK"
        )
    return match.group(1)


class AndroidRuntime:
    """Managed, private Android Emulator for the desktop application."""

    SERIAL = "emulator-5554"
    PORT = 5554

    def __init__(
        self,
        components: ComponentManager | None = None,
    ) -> None:
        self.components = components or ComponentManager()
        self.process: subprocess.Popen[bytes] | None = None
        self._process_lock = threading.Lock()

    @property
    def paths(self):
        return self.components.paths

    def ensure_ready(
        self,
        progress: RuntimeProgress | None = None,
    ) -> None:
        self.components.ensure_all(progress)
        self._emit(
            progress,
            "Проверка Android Emulator",
            None,
            None,
        )
        self._check_acceleration()
        if not self._device_online():
            self._start_emulator(progress)
        self._wait_for_boot(progress)
        self._ensure_root(progress)

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

    def tap(self, x: int, y: int) -> None:
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
        self._adb_shell(
            "input",
            "keyevent",
            str(keycode),
        )

    def text(self, value: str) -> None:
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
        }
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
                data["acceleration"] = {
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            except Exception as exc:
                data["acceleration"] = {
                    "error": str(exc)
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
        command = [
            str(self.paths.emulator),
            f"@{AVD_NAME}",
            "-port",
            str(self.PORT),
            "-no-window",
            "-gpu",
            "swiftshader_indirect",
            "-no-snapshot",
            "-noaudio",
            "-no-boot-anim",
        ]
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

    def _wait_for_boot(
        self,
        progress: RuntimeProgress | None,
    ) -> None:
        deadline = time.monotonic() + 240.0
        while time.monotonic() < deadline:
            self._ensure_process_alive()
            if self._device_online():
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
            remaining = max(
                0,
                int(deadline - time.monotonic()),
            )
            self._emit(
                progress,
                f"Загрузка Android… {remaining} с",
                None,
                None,
            )
            time.sleep(2.0)
        raise AndroidRuntimeError(
            "Android Emulator не загрузился за 240 секунд"
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

    def _check_acceleration(self) -> None:
        result = self._run(
            [
                str(self.paths.emulator),
                "-accel-check",
            ],
            timeout=20.0,
            check=False,
        )
        if result.returncode == 0:
            return

        if os.name == "nt":
            self._enable_windows_hypervisor_features()
            result = self._run(
                [
                    str(self.paths.emulator),
                    "-accel-check",
                ],
                timeout=20.0,
                check=False,
            )
            if result.returncode == 0:
                return

        detail = (
            result.stdout
            or result.stderr
        ).strip()
        raise AndroidRuntimeError(
            "Аппаратное ускорение Android Emulator пока "
            "недоступно. Mobile Research попыталась включить "
            "необходимые компоненты Windows. Если Windows "
            "запросила перезагрузку, перезагрузите компьютер "
            "и снова откройте программу. Если ошибка останется, "
            "проверьте аппаратную виртуализацию в BIOS/UEFI. "
            + detail
        )

    def _enable_windows_hypervisor_features(self) -> None:
        """Best-effort enablement of Windows virtualization via UAC."""

        command = (
            "$ErrorActionPreference='Stop'; "
            "$features=@('HypervisorPlatform',"
            "'VirtualMachinePlatform'); "
            "foreach($f in $features){"
            "$p=Start-Process dism.exe -Verb RunAs "
            "-Wait -PassThru -ArgumentList "
            "@('/Online','/Enable-Feature',"
            "('/FeatureName:'+$f),'/All','/NoRestart'); "
            "if($p.ExitCode -ne 0 -and "
            "$p.ExitCode -ne 3010){exit $p.ExitCode}}; "
            "exit 0"
        )
        creation_flags = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )
        try:
            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command,
                ],
                timeout=180,
                check=False,
                creationflags=creation_flags,
            )
        except (
            OSError,
            subprocess.TimeoutExpired,
        ):
            return

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
