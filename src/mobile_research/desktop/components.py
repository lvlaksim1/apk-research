from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

ProgressCallback = Callable[[str, int | None, int | None], None]

ANDROID_REPOSITORY_BASE = "https://dl.google.com/android/repository/"
ANDROID_REPOSITORY_XML = urllib.parse.urljoin(
    ANDROID_REPOSITORY_BASE,
    "repository2-3.xml",
)
ANDROID_SYSTEM_IMAGE_XML = urllib.parse.urljoin(
    ANDROID_REPOSITORY_BASE,
    "sys-img/android/sys-img2-3.xml",
)

AVD_NAME = "mobile_research_api35"
SYSTEM_IMAGE_PACKAGE = "system-images;android-35;default;x86_64"
BUILD_TOOLS_PACKAGE = "build-tools;35.0.0"


class ComponentInstallError(RuntimeError):
    """Raised when a managed Android component cannot be provisioned."""


@dataclass(frozen=True)
class ArchiveInfo:
    package_path: str
    url: str
    size: int | None
    checksum: str | None
    checksum_type: str | None


@dataclass(frozen=True)
class AndroidPaths:
    root: Path
    sdk_root: Path
    avd_home: Path
    cache: Path
    adb: Path
    emulator: Path
    aapt2: Path
    system_image: Path
    avd_ini: Path
    avd_dir: Path

    def to_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


@dataclass(frozen=True)
class ComponentState:
    platform_tools: bool
    emulator: bool
    build_tools: bool
    system_image: bool
    avd_profile: bool

    @property
    def ready(self) -> bool:
        return all(
            (
                self.platform_tools,
                self.emulator,
                self.build_tools,
                self.system_image,
                self.avd_profile,
            )
        )

    def to_dict(self) -> dict[str, bool]:
        value = asdict(self)
        value["ready"] = self.ready
        return value


def default_component_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "MobileResearch" / "components"
    return Path.home() / ".mobile-research" / "components"


def repository_base_url(repository_url: str) -> str:
    """Return the directory used to resolve relative SDK archive URLs."""

    return urllib.parse.urljoin(
        repository_url,
        "./",
    )


def select_archive_from_repository_xml(
    xml_bytes: bytes,
    package_path: str,
    *,
    host_os: str = "windows",
    base_url: str = ANDROID_REPOSITORY_BASE,
) -> ArchiveInfo:
    """Select the newest stable archive for the requested host."""

    from mobile_research.desktop.repository_policy import (
        select_stable_archive,
    )

    return select_stable_archive(
        xml_bytes,
        package_path,
        host_os=host_os,
        base_url=base_url,
    )


class ComponentManager:
    """Owns all Android runtime components used by the desktop application."""

    def __init__(self, root: str | os.PathLike[str] | None = None) -> None:
        component_root = (
            Path(root).expanduser().resolve()
            if root is not None
            else default_component_root().resolve()
        )
        sdk_root = component_root / "android-sdk"
        avd_home = component_root / "avd"
        self.paths = AndroidPaths(
            root=component_root,
            sdk_root=sdk_root,
            avd_home=avd_home,
            cache=component_root / "cache",
            adb=sdk_root / "platform-tools" / "adb.exe",
            emulator=sdk_root / "emulator" / "emulator.exe",
            aapt2=sdk_root / "build-tools" / "35.0.0" / "aapt2.exe",
            system_image=(
                sdk_root
                / "system-images"
                / "android-35"
                / "default"
                / "x86_64"
            ),
            avd_ini=avd_home / f"{AVD_NAME}.ini",
            avd_dir=avd_home / f"{AVD_NAME}.avd",
        )
        self._metadata_path = component_root / "components.json"

    def state(self) -> ComponentState:
        return ComponentState(
            platform_tools=self.paths.adb.is_file(),
            emulator=self.paths.emulator.is_file(),
            build_tools=self.paths.aapt2.is_file(),
            system_image=(self.paths.system_image / "system.img").is_file(),
            avd_profile=(
                self.paths.avd_ini.is_file()
                and (self.paths.avd_dir / "config.ini").is_file()
            ),
        )

    def environment(self) -> dict[str, str]:
        env = dict(os.environ)
        env["ANDROID_HOME"] = str(self.paths.sdk_root)
        env["ANDROID_SDK_ROOT"] = str(self.paths.sdk_root)
        env["ANDROID_AVD_HOME"] = str(self.paths.avd_home)
        return env

    def resolve_required_archives(self) -> list[ArchiveInfo]:
        """Resolve current official Google archives required by v0.2."""

        repository_xml = self._download_bytes(
            ANDROID_REPOSITORY_XML
        )
        system_image_xml = self._download_bytes(
            ANDROID_SYSTEM_IMAGE_XML
        )
        return [
            select_archive_from_repository_xml(
                repository_xml,
                "platform-tools",
                host_os="windows",
                base_url=repository_base_url(
                    ANDROID_REPOSITORY_XML
                ),
            ),
            select_archive_from_repository_xml(
                repository_xml,
                "emulator",
                host_os="windows",
                base_url=repository_base_url(
                    ANDROID_REPOSITORY_XML
                ),
            ),
            select_archive_from_repository_xml(
                repository_xml,
                BUILD_TOOLS_PACKAGE,
                host_os="windows",
                base_url=repository_base_url(
                    ANDROID_REPOSITORY_XML
                ),
            ),
            select_archive_from_repository_xml(
                system_image_xml,
                SYSTEM_IMAGE_PACKAGE,
                host_os="windows",
                base_url=repository_base_url(
                    ANDROID_SYSTEM_IMAGE_XML
                ),
            ),
        ]

    def ensure_all(
        self,
        progress: ProgressCallback | None = None,
    ) -> ComponentState:
        self.paths.root.mkdir(parents=True, exist_ok=True)
        self.paths.sdk_root.mkdir(parents=True, exist_ok=True)
        self.paths.cache.mkdir(parents=True, exist_ok=True)
        self.paths.avd_home.mkdir(parents=True, exist_ok=True)

        if not self.state().platform_tools:
            self._install_repository_package(
                "platform-tools",
                self.paths.sdk_root / "platform-tools",
                mode="named-directory",
                progress=progress,
            )
        if not self.state().emulator:
            self._install_repository_package(
                "emulator",
                self.paths.sdk_root / "emulator",
                mode="named-directory",
                progress=progress,
            )
        if not self.state().build_tools:
            self._install_repository_package(
                BUILD_TOOLS_PACKAGE,
                self.paths.sdk_root / "build-tools" / "35.0.0",
                mode="find-aapt2",
                progress=progress,
            )
        if not self.state().system_image:
            self._install_repository_package(
                SYSTEM_IMAGE_PACKAGE,
                self.paths.system_image,
                mode="find-system-img",
                repository_url=ANDROID_SYSTEM_IMAGE_XML,
                progress=progress,
            )

        if not self.state().avd_profile:
            self.create_avd_profile()

        final_state = self.state()
        if not final_state.ready:
            raise ComponentInstallError(
                "Android environment provisioning finished incompletely"
            )
        return final_state

    def reset_avd_userdata(self) -> None:
        if not self.paths.avd_dir.exists():
            self.create_avd_profile()
            return
        for child in self.paths.avd_dir.iterdir():
            if child.name == "config.ini":
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

    def remove_all(self) -> None:
        """Remove every Mobile Research managed Android component.

        Research sessions are stored outside this tree, so repairing the
        Android runtime never deletes captured research data.
        """

        if self.paths.root.exists():
            shutil.rmtree(
                self.paths.root,
                ignore_errors=False,
            )

    def create_avd_profile(self) -> None:
        image = self.paths.system_image
        if not (image / "system.img").is_file():
            raise ComponentInstallError(
                "Cannot create AVD profile before the API 35 system image exists"
            )

        self.paths.avd_home.mkdir(parents=True, exist_ok=True)
        self.paths.avd_dir.mkdir(parents=True, exist_ok=True)

        relative_image = "system-images\\android-35\\default\\x86_64\\"
        config = "\n".join(
            [
                "AvdId=" + AVD_NAME,
                "PlayStore.enabled=false",
                "abi.type=x86_64",
                "avd.ini.displayname=Mobile Research Android 15",
                "avd.ini.encoding=UTF-8",
                "disk.dataPartition.size=6G",
                "fastboot.forceChosenSnapshotBoot=no",
                "fastboot.forceColdBoot=yes",
                "fastboot.forceFastBoot=no",
                "hw.accelerometer=yes",
                "hw.audioInput=no",
                "hw.battery=yes",
                "hw.camera.back=none",
                "hw.camera.front=none",
                "hw.cpu.arch=x86_64",
                "hw.cpu.ncore=4",
                "hw.dPad=no",
                "hw.device.manufacturer=Google",
                "hw.device.name=pixel_5",
                "hw.gps=yes",
                "hw.gpu.enabled=yes",
                "hw.gpu.mode=auto",
                "hw.initialOrientation=Portrait",
                "hw.keyboard=yes",
                "hw.lcd.density=420",
                "hw.lcd.height=1920",
                "hw.lcd.width=1080",
                "hw.mainKeys=no",
                "hw.ramSize=4096",
                "hw.sdCard=no",
                f"image.sysdir.1={relative_image}",
                "runtime.network.latency=none",
                "runtime.network.speed=full",
                "showDeviceFrame=no",
                "skin.dynamic=yes",
                "skin.name=1080x1920",
                "tag.display=Default",
                "tag.id=default",
                "target=android-35",
                "vm.heapSize=256",
            ]
        ) + "\n"
        (self.paths.avd_dir / "config.ini").write_text(
            config,
            encoding="utf-8",
            newline="\n",
        )

        ini = "\n".join(
            [
                "avd.ini.encoding=UTF-8",
                f"path={self.paths.avd_dir}",
                f"path.rel=avd\\{AVD_NAME}.avd",
                "target=android-35",
            ]
        ) + "\n"
        self.paths.avd_ini.write_text(
            ini,
            encoding="utf-8",
            newline="\n",
        )

    def _install_repository_package(
        self,
        package_path: str,
        destination: Path,
        *,
        mode: str,
        repository_url: str = ANDROID_REPOSITORY_XML,
        progress: ProgressCallback | None = None,
    ) -> None:
        self._emit(
            progress,
            f"Получение метаданных: {package_path}",
            None,
            None,
        )
        xml = self._download_bytes(repository_url)
        archive = select_archive_from_repository_xml(
            xml,
            package_path,
            host_os="windows",
            base_url=repository_base_url(
                repository_url
            ),
        )
        cache_name = Path(
            urllib.parse.urlparse(archive.url).path
        ).name
        cache_path = self.paths.cache / cache_name
        self._download_archive(archive, cache_path, progress)

        self._emit(progress, f"Распаковка: {package_path}", None, None)
        with tempfile.TemporaryDirectory(
            prefix="mobile-research-",
            dir=self.paths.root,
        ) as temporary:
            temp_root = Path(temporary)
            self._extract_zip_safe(cache_path, temp_root)
            source = self._locate_payload(
                temp_root,
                mode,
                destination.name,
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                shutil.rmtree(destination, ignore_errors=True)
            shutil.copytree(source, destination)

        self._record_component(package_path, archive)

    def _locate_payload(
        self,
        extracted_root: Path,
        mode: str,
        destination_name: str,
    ) -> Path:
        if mode == "named-directory":
            direct = extracted_root / destination_name
            if direct.is_dir():
                return direct
            matches = [
                path
                for path in extracted_root.rglob(destination_name)
                if path.is_dir()
            ]
            if matches:
                return matches[0]

        if mode == "find-aapt2":
            matches = list(extracted_root.rglob("aapt2.exe"))
            if matches:
                return matches[0].parent

        if mode == "find-system-img":
            matches = list(extracted_root.rglob("system.img"))
            if matches:
                return matches[0].parent

        raise ComponentInstallError(
            f"Downloaded Android archive has unexpected layout ({mode})"
        )

    def _download_archive(
        self,
        archive: ArchiveInfo,
        destination: Path,
        progress: ProgressCallback | None,
    ) -> None:
        if (
            destination.is_file()
            and self._checksum_matches(destination, archive)
        ):
            self._emit(
                progress,
                f"Кэш: {archive.package_path}",
                archive.size,
                archive.size,
            )
            return

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(
            destination.suffix + ".tmp"
        )
        temporary.unlink(missing_ok=True)

        request = urllib.request.Request(
            archive.url,
            headers={"User-Agent": "MobileResearch/0.2"},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=60,
            ) as response:
                total_header = response.headers.get("Content-Length")
                total = archive.size
                if total is None and total_header:
                    try:
                        total = int(total_header)
                    except ValueError:
                        total = None
                downloaded = 0
                with temporary.open("wb") as handle:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        handle.write(block)
                        downloaded += len(block)
                        self._emit(
                            progress,
                            f"Загрузка: {archive.package_path}",
                            downloaded,
                            total,
                        )
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            raise ComponentInstallError(
                f"Unable to download {archive.package_path}: {exc}"
            ) from exc

        if not self._checksum_matches(temporary, archive):
            temporary.unlink(missing_ok=True)
            raise ComponentInstallError(
                "Checksum mismatch for Android component: "
                f"{archive.package_path}"
            )
        os.replace(temporary, destination)

    def _checksum_matches(
        self,
        path: Path,
        archive: ArchiveInfo,
    ) -> bool:
        if not path.is_file():
            return False
        if not archive.checksum:
            return True
        algorithm = (
            (archive.checksum_type or "sha1")
            .lower()
            .replace("-", "")
        )
        if algorithm not in hashlib.algorithms_available:
            raise ComponentInstallError(
                f"Unsupported repository checksum algorithm: {algorithm}"
            )
        digest = hashlib.new(algorithm)
        with path.open("rb") as handle:
            for block in iter(
                lambda: handle.read(1024 * 1024),
                b"",
            ):
                digest.update(block)
        return (
            digest.hexdigest().lower()
            == archive.checksum.lower()
        )

    def _download_bytes(self, url: str) -> bytes:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "MobileResearch/0.2"},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=30,
            ) as response:
                return response.read()
        except Exception as exc:
            raise ComponentInstallError(
                "Unable to download Android repository metadata: "
                f"{exc}"
            ) from exc

    def _extract_zip_safe(
        self,
        archive: Path,
        destination: Path,
    ) -> None:
        try:
            with zipfile.ZipFile(archive) as handle:
                root = destination.resolve()
                for member in handle.infolist():
                    target = (
                        destination / member.filename
                    ).resolve()
                    try:
                        target.relative_to(root)
                    except ValueError as exc:
                        raise ComponentInstallError(
                            "Unsafe path in Android archive: "
                            f"{member.filename}"
                        ) from exc
                handle.extractall(destination)
        except zipfile.BadZipFile as exc:
            raise ComponentInstallError(
                "Downloaded Android component is not a valid ZIP: "
                f"{archive.name}"
            ) from exc

    def _record_component(
        self,
        package_path: str,
        archive: ArchiveInfo,
    ) -> None:
        value: dict[str, object] = {}
        if self._metadata_path.is_file():
            try:
                value = json.loads(
                    self._metadata_path.read_text(
                        encoding="utf-8"
                    )
                )
            except (json.JSONDecodeError, OSError):
                value = {}
        components = value.setdefault("components", {})
        assert isinstance(components, dict)
        components[package_path] = asdict(archive)
        temporary = self._metadata_path.with_suffix(
            ".json.tmp"
        )
        temporary.write_text(
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self._metadata_path)

    @staticmethod
    def _emit(
        callback: ProgressCallback | None,
        message: str,
        current: int | None,
        total: int | None,
    ) -> None:
        if callback is not None:
            callback(message, current, total)
