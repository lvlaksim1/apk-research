from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from mobile_research.session import SessionManager
from mobile_research.targets import AdbClient, AdbError

Clock = Callable[[], datetime]

_GETPROP_RE = re.compile(r"^\[([^\]]+)\]: \[(.*)\]$")
_VERSION_CODE_RE = re.compile(r"\bversionCode=(\d+)")
_VERSION_NAME_RE = re.compile(r"\bversionName=([^\r\n]+)")
_FIRST_INSTALL_RE = re.compile(r"^\s*firstInstallTime=(.+)$", re.MULTILINE)
_LAST_UPDATE_RE = re.compile(r"^\s*lastUpdateTime=(.+)$", re.MULTILINE)


class MetadataCollectorError(RuntimeError):
    """Raised when mandatory device metadata cannot be captured."""


@dataclass(frozen=True)
class DeviceMetadataResult:
    collector: str
    status: str
    raw_artifacts: tuple[str, ...]
    normalized_artifact: str
    host_started_utc: str
    host_finished_utc: str
    target_started_utc: str
    target_finished_utc: str

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["raw_artifacts"] = list(self.raw_artifacts)
        return result


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_getprop(text: str) -> dict[str, str]:
    properties: dict[str, str] = {}
    for line in text.splitlines():
        match = _GETPROP_RE.match(line.strip())
        if match:
            properties[match.group(1)] = match.group(2)
    return properties


def _search_group(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            if content and not content.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class DeviceMetadataCollector:
    """Capture raw Android/device/package metadata into one research session."""

    NAME = "device_metadata"
    BACKEND = "adb"

    def __init__(
        self,
        adb: AdbClient,
        session: SessionManager,
        *,
        clock: Clock = _utc_now,
    ) -> None:
        self.adb = adb
        self.session = session
        self.clock = clock

    def collect(self) -> DeviceMetadataResult:
        manifest = self.session.manifest
        serial = str(manifest.get("target", {}).get("serial") or "").strip()
        package_name = str(manifest.get("package", {}).get("name") or "").strip()

        if not serial:
            raise MetadataCollectorError("Session target serial is missing")
        if not package_name:
            raise MetadataCollectorError("Session package name is missing")

        if self.NAME in manifest.get("collectors", {}):
            raise MetadataCollectorError(
                f"Collector already registered: {self.NAME}"
            )

        self.session.register_collector(
            self.NAME,
            required=True,
            backend=self.BACKEND,
        )
        self.session.update_collector(self.NAME, "running")

        host_started = _iso_utc(self.clock())
        raw_artifacts: list[str] = []

        try:
            self.adb.ensure_ready(serial)
            if not self.adb.is_package_installed(serial, package_name):
                raise MetadataCollectorError(
                    f"Package {package_name!r} is not installed on {serial}"
                )

            target_started = self.adb.get_utc_time(serial)
            getprop = self.adb.get_all_properties(serial)
            package_dump = self._capture_package_dump(serial, package_name)
            package_paths = self.adb.get_package_paths(serial, package_name)

            system_text, optional_errors = self._capture_optional_system(serial)
            target_finished = self.adb.get_utc_time(serial)
            host_finished = _iso_utc(self.clock())

            files = {
                "01_raw/device/getprop.txt": getprop,
                "01_raw/device/package.txt": package_dump,
                "01_raw/device/package-paths.txt": package_paths,
                "01_raw/device/system.txt": system_text,
                "01_raw/device/clock.txt": (
                    f"host_started_utc={host_started}\n"
                    f"target_started_utc={target_started}\n"
                    f"target_finished_utc={target_finished}\n"
                    f"host_finished_utc={host_finished}\n"
                ),
            }

            for relative_path, content in files.items():
                absolute = self.session.paths.root / Path(relative_path)
                _write_text_atomic(absolute, content)
                self.session.register_artifact(
                    kind="device_metadata",
                    relative_path=relative_path,
                    source=self.NAME,
                    raw=True,
                )
                self.session.update_collector(
                    self.NAME,
                    "running",
                    artifact_path=relative_path,
                )
                raw_artifacts.append(relative_path)

            normalized = self._build_normalized(
                serial=serial,
                package_name=package_name,
                getprop=getprop,
                package_dump=package_dump,
                package_paths=package_paths,
                host_started=host_started,
                host_finished=host_finished,
                target_started=target_started,
                target_finished=target_finished,
                optional_errors=optional_errors,
            )
            normalized_path = "02_normalized/target.json"
            _write_text_atomic(
                self.session.paths.root / normalized_path,
                json.dumps(
                    normalized,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
            )
            self.session.register_artifact(
                kind="device_metadata_normalized",
                relative_path=normalized_path,
                source=self.NAME,
                raw=False,
            )
            self.session.update_collector(
                self.NAME,
                "completed",
                artifact_path=normalized_path,
            )

            return DeviceMetadataResult(
                collector=self.NAME,
                status="completed",
                raw_artifacts=tuple(raw_artifacts),
                normalized_artifact=normalized_path,
                host_started_utc=host_started,
                host_finished_utc=host_finished,
                target_started_utc=target_started,
                target_finished_utc=target_finished,
            )
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            try:
                self.session.update_collector(
                    self.NAME,
                    "failed",
                    error=message,
                )
            except Exception:
                pass

            if isinstance(exc, MetadataCollectorError):
                raise
            if isinstance(exc, AdbError):
                raise MetadataCollectorError(message) from exc
            raise MetadataCollectorError(
                f"Device metadata capture failed: {message}"
            ) from exc

    def _capture_package_dump(
        self,
        serial: str,
        package_name: str,
    ) -> str:
        remote_dir = (
            f"/data/local/tmp/mobile-research/{self.session.session_id}"
        )
        remote_path = f"{remote_dir}/package-dump.txt"
        temporary = (
            self.session.paths.raw_device / "package.remote.tmp"
        )

        try:
            self.adb.make_remote_directory(
                serial,
                remote_dir,
            )
            try:
                self.adb.remove_remote_file(
                    serial,
                    remote_path,
                )
            except AdbError:
                pass

            self.adb.capture_shell_output_to_file(
                serial,
                remote_path,
                "dumpsys",
                "package",
                package_name,
                timeout=60.0,
            )
            self.adb.pull_file(
                serial,
                remote_path,
                temporary,
                timeout=120.0,
            )

            if not temporary.is_file():
                raise MetadataCollectorError(
                    "Package dump was not pulled from Android"
                )
            if temporary.stat().st_size == 0:
                raise MetadataCollectorError(
                    "Package dump captured on Android is empty"
                )

            return temporary.read_text(
                encoding="utf-8",
                errors="replace",
            )
        finally:
            temporary.unlink(missing_ok=True)
            try:
                self.adb.remove_remote_file(
                    serial,
                    remote_path,
                )
            except AdbError:
                pass

    def _capture_optional_system(
        self,
        serial: str,
    ) -> tuple[str, list[dict[str, str]]]:
        commands = (
            ("id", ("id",)),
            ("uname", ("uname", "-a")),
            ("selinux", ("getenforce",)),
            ("wm-size", ("wm", "size")),
            ("wm-density", ("wm", "density")),
        )

        sections: list[str] = []
        errors: list[dict[str, str]] = []

        for label, arguments in commands:
            sections.append(f"===== {label} =====")
            try:
                output = self.adb.shell_output(serial, *arguments)
                sections.append(output.rstrip())
            except AdbError as exc:
                message = str(exc)
                sections.append(f"ERROR: {message}")
                errors.append({"command": label, "error": message})
            sections.append("")

        return "\n".join(sections), errors

    def _build_normalized(
        self,
        *,
        serial: str,
        package_name: str,
        getprop: str,
        package_dump: str,
        package_paths: str,
        host_started: str,
        host_finished: str,
        target_started: str,
        target_finished: str,
        optional_errors: list[dict[str, str]],
    ) -> dict[str, object]:
        properties = _parse_getprop(getprop)
        version_code = _search_group(_VERSION_CODE_RE, package_dump)
        version_name = _search_group(_VERSION_NAME_RE, package_dump)

        return {
            "schema_version": "0.1",
            "collector": self.NAME,
            "backend": self.BACKEND,
            "target": {
                "serial": serial,
                "android_release": properties.get("ro.build.version.release"),
                "sdk_level": properties.get("ro.build.version.sdk"),
                "manufacturer": properties.get("ro.product.manufacturer"),
                "model": properties.get("ro.product.model"),
                "abi": properties.get("ro.product.cpu.abi"),
                "build_fingerprint": properties.get("ro.build.fingerprint"),
            },
            "package": {
                "name": package_name,
                "version_name": version_name,
                "version_code": version_code,
                "first_install_time": _search_group(
                    _FIRST_INSTALL_RE,
                    package_dump,
                ),
                "last_update_time": _search_group(
                    _LAST_UPDATE_RE,
                    package_dump,
                ),
                "paths": [
                    line.removeprefix("package:").strip()
                    for line in package_paths.splitlines()
                    if line.strip().startswith("package:")
                ],
            },
            "clock": {
                "scope": "device_metadata_capture",
                "host_started_utc": host_started,
                "target_started_utc": target_started,
                "target_finished_utc": target_finished,
                "host_finished_utc": host_finished,
            },
            "optional_command_errors": optional_errors,
        }
