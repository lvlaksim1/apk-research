from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

CommandRunner = Callable[[Sequence[str], float], subprocess.CompletedProcess[str]]

_PACKAGE_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$"
)


class AdbError(RuntimeError):
    """Base exception for ADB target operations."""


class AdbNotFoundError(AdbError):
    """Raised when an ADB executable cannot be located."""


class AdbCommandError(AdbError):
    """Raised when an ADB command fails."""

    def __init__(
        self,
        command: Sequence[str],
        returncode: int,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.command = tuple(command)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

        detail = stderr.strip() or stdout.strip() or "no diagnostic output"
        super().__init__(
            f"ADB command failed with exit code {returncode}: "
            f"{' '.join(command)}; {detail}"
        )


@dataclass(frozen=True)
class AdbTarget:
    serial: str
    state: str
    kind: str
    product: str | None = None
    model: str | None = None
    device: str | None = None
    transport_id: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(frozen=True)
class AdbTargetDetails:
    serial: str
    state: str
    kind: str
    android_release: str
    sdk_level: int | None
    manufacturer: str
    model: str
    abi: str
    build_fingerprint: str
    is_root: bool

    def to_dict(self) -> dict[str, str | int | bool | None]:
        return asdict(self)


def resolve_adb(explicit_path: str | os.PathLike[str] | None = None) -> Path:
    """Locate adb.exe/adb without invoking a shell."""

    if explicit_path:
        candidate = Path(explicit_path).expanduser()
        if candidate.is_file():
            return candidate.resolve()

        found = shutil.which(str(explicit_path))
        if found:
            return Path(found).resolve()

        raise AdbNotFoundError(f"ADB not found at configured path: {explicit_path}")

    found = shutil.which("adb")
    if found:
        return Path(found).resolve()

    sdk_roots: list[Path] = []
    for variable in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        value = os.environ.get(variable)
        if value:
            sdk_roots.append(Path(value).expanduser())

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        sdk_roots.append(Path(local_app_data) / "Android" / "Sdk")

    executable_names = ("adb.exe", "adb")
    for root in sdk_roots:
        for executable_name in executable_names:
            candidate = root / "platform-tools" / executable_name
            if candidate.is_file():
                return candidate.resolve()

    raise AdbNotFoundError(
        "ADB was not found. Configure --adb, add platform-tools to PATH, "
        "or configure ANDROID_SDK_ROOT/ANDROID_HOME."
    )


def parse_adb_devices(output: str) -> list[AdbTarget]:
    """Parse output from `adb devices -l` without querying targets."""

    targets: list[AdbTarget] = []

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("*"):
            continue
        if line.lower().startswith("list of devices attached"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        serial = parts[0]
        state = parts[1]
        properties: dict[str, str] = {}

        for token in parts[2:]:
            key, separator, value = token.partition(":")
            if separator:
                properties[key] = value

        initial_kind = "emulator" if serial.startswith("emulator-") else "unknown"

        targets.append(
            AdbTarget(
                serial=serial,
                state=state,
                kind=initial_kind,
                product=properties.get("product"),
                model=properties.get("model"),
                device=properties.get("device"),
                transport_id=properties.get("transport_id"),
            )
        )

    return targets


def validate_package_name(package_name: str) -> str:
    package_name = package_name.strip()
    if not _PACKAGE_RE.fullmatch(package_name):
        raise ValueError(f"Invalid Android package name: {package_name!r}")
    return package_name



_REMOTE_RESEARCH_ROOT = "/data/local/tmp/mobile-research"
_PROCESS_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def validate_remote_research_path(path: str) -> str:
    normalized = path.replace("\\", "/").rstrip("/")
    if (
        not normalized.startswith(_REMOTE_RESEARCH_ROOT)
        or normalized == _REMOTE_RESEARCH_ROOT
        or "/../" in f"{normalized}/"
        or "/./" in f"{normalized}/"
    ):
        raise ValueError(
            "Remote research path must remain under "
            f"{_REMOTE_RESEARCH_ROOT}/: {path!r}"
        )
    return normalized


def validate_process_name(process_name: str) -> str:
    process_name = process_name.strip()
    if not _PROCESS_NAME_RE.fullmatch(process_name):
        raise ValueError(f"Invalid Android process name: {process_name!r}")
    return process_name

class AdbClient:
    """Small ADB client used by the Target Manager.

    The client never uses a local shell. A custom runner can be injected for tests.
    """

    def __init__(
        self,
        adb_path: str | os.PathLike[str],
        runner: CommandRunner | None = None,
    ) -> None:
        self.adb_path = Path(adb_path)
        self._runner = runner or self._default_runner

    @classmethod
    def from_environment(
        cls,
        explicit_path: str | os.PathLike[str] | None = None,
    ) -> "AdbClient":
        return cls(resolve_adb(explicit_path))

    def _default_runner(
        self,
        arguments: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        command = [str(self.adb_path), *arguments]
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                creationflags=creation_flags,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdbError(
                f"ADB command timed out after {timeout:g}s: {' '.join(command)}"
            ) from exc
        except OSError as exc:
            raise AdbError(f"Unable to execute ADB: {self.adb_path}") from exc

    def _run_checked(
        self,
        arguments: Sequence[str],
        timeout: float = 10.0,
    ) -> subprocess.CompletedProcess[str]:
        result = self._runner(arguments, timeout)
        if result.returncode != 0:
            raise AdbCommandError(
                [str(self.adb_path), *arguments],
                result.returncode,
                result.stdout or "",
                result.stderr or "",
            )
        return result

    def shell_output(
        self,
        serial: str,
        *arguments: str,
        timeout: float = 10.0,
    ) -> str:
        """Run a fixed Android shell command and return stdout as text."""

        result = self._run_checked(
            ["-s", serial, "shell", *arguments],
            timeout=timeout,
        )
        return result.stdout or ""

    def _shell_value(
        self,
        serial: str,
        *arguments: str,
        timeout: float = 10.0,
    ) -> str:
        return self.shell_output(
            serial,
            *arguments,
            timeout=timeout,
        ).strip()

    def list_targets(self) -> list[AdbTarget]:
        result = self._run_checked(["devices", "-l"])
        parsed = parse_adb_devices(result.stdout or "")

        enriched: list[AdbTarget] = []
        for target in parsed:
            kind = target.kind
            if target.state == "device" and kind == "unknown":
                try:
                    qemu = self._shell_value(
                        target.serial,
                        "getprop",
                        "ro.kernel.qemu",
                    )
                    kind = "emulator" if qemu == "1" else "physical"
                except AdbError:
                    kind = "unknown"

            enriched.append(
                AdbTarget(
                    serial=target.serial,
                    state=target.state,
                    kind=kind,
                    product=target.product,
                    model=target.model,
                    device=target.device,
                    transport_id=target.transport_id,
                )
            )

        return enriched

    def get_target(self, serial: str) -> AdbTarget:
        for target in self.list_targets():
            if target.serial == serial:
                return target
        raise AdbError(f"ADB target not found: {serial}")

    def ensure_ready(self, serial: str) -> AdbTarget:
        target = self.get_target(serial)
        if target.state != "device":
            raise AdbError(
                f"ADB target {serial} is not ready; current state: {target.state}"
            )
        return target

    def get_target_details(self, serial: str) -> AdbTargetDetails:
        target = self.ensure_ready(serial)

        qemu = self._shell_value(serial, "getprop", "ro.kernel.qemu")
        precise_kind = "emulator" if qemu == "1" else "physical"

        sdk_text = self._shell_value(serial, "getprop", "ro.build.version.sdk")
        try:
            sdk_level = int(sdk_text)
        except ValueError:
            sdk_level = None

        uid_text = self._shell_value(serial, "id", "-u")
        is_root = uid_text == "0"

        return AdbTargetDetails(
            serial=serial,
            state=target.state,
            kind=precise_kind,
            android_release=self._shell_value(
                serial,
                "getprop",
                "ro.build.version.release",
            ),
            sdk_level=sdk_level,
            manufacturer=self._shell_value(
                serial,
                "getprop",
                "ro.product.manufacturer",
            ),
            model=self._shell_value(
                serial,
                "getprop",
                "ro.product.model",
            ),
            abi=self._shell_value(
                serial,
                "getprop",
                "ro.product.cpu.abi",
            ),
            build_fingerprint=self._shell_value(
                serial,
                "getprop",
                "ro.build.fingerprint",
            ),
            is_root=is_root,
        )

    def is_package_installed(self, serial: str, package_name: str) -> bool:
        self.ensure_ready(serial)
        package_name = validate_package_name(package_name)

        arguments = [
            "-s",
            serial,
            "shell",
            "pm",
            "path",
            package_name,
        ]
        result = self._runner(arguments, 10.0)

        if result.returncode == 1:
            return False
        if result.returncode != 0:
            raise AdbCommandError(
                [str(self.adb_path), *arguments],
                result.returncode,
                result.stdout or "",
                result.stderr or "",
            )

        return any(
            line.strip().startswith("package:")
            for line in (result.stdout or "").splitlines()
        )

    def get_all_properties(self, serial: str) -> str:
        self.ensure_ready(serial)
        return self.shell_output(serial, "getprop")

    def get_package_dump(self, serial: str, package_name: str) -> str:
        self.ensure_ready(serial)
        package_name = validate_package_name(package_name)
        return self.shell_output(serial, "dumpsys", "package", package_name)

    def get_package_paths(self, serial: str, package_name: str) -> str:
        self.ensure_ready(serial)
        package_name = validate_package_name(package_name)
        return self.shell_output(serial, "pm", "path", package_name)

    def resolve_launch_activity(
        self,
        serial: str,
        package_name: str,
    ) -> str:
        self.ensure_ready(serial)
        package_name = validate_package_name(package_name)

        output = self.shell_output(
            serial,
            "cmd",
            "package",
            "resolve-activity",
            "--brief",
            "-a",
            "android.intent.action.MAIN",
            "-c",
            "android.intent.category.LAUNCHER",
            package_name,
        )

        candidates = [
            line.strip()
            for line in output.splitlines()
            if "/" in line and " " not in line.strip()
        ]
        if not candidates:
            raise AdbError(
                f"No launcher activity resolved for package {package_name}"
            )

        component = candidates[-1]
        if not component.startswith(package_name + "/"):
            raise AdbError(
                "Resolved launcher component does not belong to package "
                f"{package_name}: {component}"
            )
        return component

    def force_stop_package(
        self,
        serial: str,
        package_name: str,
    ) -> None:
        self.ensure_ready(serial)
        package_name = validate_package_name(
            package_name
        )
        self._run_checked(
            [
                "-s",
                serial,
                "shell",
                "am",
                "force-stop",
                package_name,
            ],
            timeout=15.0,
        )

    def launch_package(
        self,
        serial: str,
        package_name: str,
    ) -> str:
        component = self.resolve_launch_activity(
            serial,
            package_name,
        )
        result = self._run_checked(
            [
                "-s",
                serial,
                "shell",
                "am",
                "start",
                "-W",
                "-n",
                component,
            ],
            timeout=30.0,
        )
        output = (result.stdout or "") + (result.stderr or "")
        if "Error:" in output:
            raise AdbError(
                f"Unable to launch package {package_name}: "
                f"{output.strip()}"
            )
        return output

    def get_utc_time(self, serial: str) -> str:
        self.ensure_ready(serial)
        return self._shell_value(
            serial,
            "date",
            "-u",
            "+%Y-%m-%dT%H:%M:%SZ",
        )

    def get_uid(self, serial: str) -> int:
        self.ensure_ready(serial)
        value = self._shell_value(serial, "id", "-u")
        try:
            return int(value)
        except ValueError as exc:
            raise AdbError(
                f"Unable to parse Android uid for {serial}: {value!r}"
            ) from exc

    def probe_executable(
        self,
        serial: str,
        candidates: Sequence[str],
        *,
        version_arguments: Sequence[str] = ("--version",),
    ) -> tuple[str, str]:
        self.ensure_ready(serial)

        diagnostics: list[str] = []
        for candidate in candidates:
            try:
                result = self._run_checked(
                    [
                        "-s",
                        serial,
                        "shell",
                        candidate,
                        *version_arguments,
                    ]
                )
            except AdbCommandError as exc:
                diagnostics.append(
                    f"{candidate}: exit {exc.returncode}"
                )
                continue

            version_text = (
                (result.stdout or "").strip()
                or (result.stderr or "").strip()
            )
            return candidate, version_text

        raise AdbError(
            "No usable executable found. Tried: "
            + ", ".join(candidates)
            + (
                "; diagnostics: " + "; ".join(diagnostics)
                if diagnostics
                else ""
            )
        )

    def make_remote_directory(self, serial: str, remote_path: str) -> None:
        remote_path = validate_remote_research_path(remote_path)
        self.ensure_ready(serial)
        self._run_checked(
            ["-s", serial, "shell", "mkdir", "-p", remote_path]
        )

    def capture_shell_output_to_file(
        self,
        serial: str,
        remote_path: str,
        *arguments: str,
        timeout: float = 60.0,
    ) -> None:
        remote_path = validate_remote_research_path(remote_path)
        if not arguments:
            raise ValueError("At least one remote command argument is required")
        self.ensure_ready(serial)

        shell_command = (
            shlex.join(arguments)
            + " >"
            + shlex.quote(remote_path)
        )
        self._run_checked(
            [
                "-s",
                serial,
                "shell",
                "sh",
                "-c",
                shell_command,
            ],
            timeout=timeout,
        )

    def pull_file(
        self,
        serial: str,
        remote_path: str,
        local_path: str | os.PathLike[str],
        *,
        timeout: float = 120.0,
    ) -> None:
        remote_path = validate_remote_research_path(remote_path)
        self.ensure_ready(serial)
        local = Path(local_path)
        local.parent.mkdir(parents=True, exist_ok=True)
        self._run_checked(
            ["-s", serial, "pull", remote_path, str(local)],
            timeout=timeout,
        )

    def remove_remote_file(self, serial: str, remote_path: str) -> None:
        remote_path = validate_remote_research_path(remote_path)
        self.ensure_ready(serial)
        self._run_checked(
            ["-s", serial, "shell", "rm", "-f", remote_path]
        )

    def get_process_ids(
        self,
        serial: str,
        process_name: str,
    ) -> list[int]:
        self.ensure_ready(serial)
        process_name = validate_process_name(process_name)
        try:
            result = self._run_checked(
                ["-s", serial, "shell", "pidof", process_name]
            )
        except AdbCommandError as exc:
            if exc.returncode == 1:
                return []
            raise

        process_ids: list[int] = []
        for token in (result.stdout or "").split():
            try:
                value = int(token)
            except ValueError:
                continue
            if value > 0:
                process_ids.append(value)
        return process_ids

    def send_signal(
        self,
        serial: str,
        process_id: int,
        signal_number: int,
    ) -> None:
        self.ensure_ready(serial)
        if process_id <= 0:
            raise ValueError("process_id must be positive")
        if not 1 <= signal_number <= 64:
            raise ValueError("signal_number must be between 1 and 64")
        self._run_checked(
            [
                "-s",
                serial,
                "shell",
                "kill",
                f"-{signal_number}",
                str(process_id),
            ]
        )
