from __future__ import annotations

import contextlib
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterator

_PACKAGE_LINE_RE = re.compile(r"^package:\s+(.*)$", re.MULTILINE)
_ATTRIBUTE_RE = re.compile(r"([A-Za-z0-9_]+)='([^']*)'")
_NATIVE_CODE_LINE_RE = re.compile(
    r"^native-code:\s+(.*)$",
    re.MULTILINE,
)
_QUOTED_VALUE_RE = re.compile(r"'([^']+)'")

MAX_XAPK_APKS = 64
MAX_XAPK_OBBS = 64
MAX_XAPK_EXTRACTED_BYTES = 8 * 1024 * 1024 * 1024


class PackageInputError(ValueError):
    """Raised when an APK/XAPK input cannot be accepted safely."""


@dataclass(frozen=True)
class ApkBadging:
    path: Path
    package_name: str
    version_code: str
    split_name: str | None
    native_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaterializedPackage:
    source: Path
    source_format: str
    apk_files: tuple[Path, ...]
    obb_files: tuple[Path, ...]


def parse_apk_badging(output: str, path: Path) -> ApkBadging:
    match = _PACKAGE_LINE_RE.search(output)
    if not match:
        raise PackageInputError(
            f"Не удалось определить сведения APK: {path.name}"
        )
    attributes = dict(_ATTRIBUTE_RE.findall(match.group(1)))
    package_name = attributes.get("name", "").strip()
    if not package_name:
        raise PackageInputError(
            f"Не удалось определить package name: {path.name}"
        )
    version_code = attributes.get("versionCode", "").strip()
    split_name = attributes.get("split", "").strip() or None

    native_codes: list[str] = []
    native_match = _NATIVE_CODE_LINE_RE.search(output)
    if native_match:
        for value in _QUOTED_VALUE_RE.findall(
            native_match.group(1)
        ):
            normalized = value.strip()
            if normalized and normalized not in native_codes:
                native_codes.append(normalized)

    return ApkBadging(
        path=path,
        package_name=package_name,
        version_code=version_code,
        split_name=split_name,
        native_codes=tuple(native_codes),
    )


def _format_abis(values: tuple[str, ...] | list[str] | set[str]) -> str:
    normalized = [
        str(value).strip()
        for value in values
        if str(value).strip()
    ]
    return ", ".join(normalized) if normalized else "не указаны"


def validate_apk_set(
    badgings: list[ApkBadging],
    *,
    device_abis: tuple[str, ...] | list[str] | None = None,
) -> tuple[str, tuple[ApkBadging, ...]]:
    if not badgings:
        raise PackageInputError("В пакете не найдено ни одного APK")

    packages = {item.package_name for item in badgings}
    if len(packages) != 1:
        raise PackageInputError(
            "XAPK содержит APK из разных package name: "
            + ", ".join(sorted(packages))
        )

    versions = {
        item.version_code
        for item in badgings
        if item.version_code
    }
    if len(versions) > 1:
        raise PackageInputError(
            "XAPK содержит APK с разными versionCode"
        )

    bases = [item for item in badgings if item.split_name is None]
    if len(bases) != 1:
        raise PackageInputError(
            "XAPK должен содержать ровно один базовый APK; "
            f"найдено: {len(bases)}"
        )

    split_names = [
        item.split_name
        for item in badgings
        if item.split_name is not None
    ]
    if len(split_names) != len(set(split_names)):
        raise PackageInputError(
            "XAPK содержит повторяющиеся split APK"
        )

    base = bases[0]
    splits = sorted(
        (item for item in badgings if item is not base),
        key=lambda item: (
            item.split_name or "",
            item.path.name.lower(),
        ),
    )

    normalized_device_abis = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in (device_abis or ())
            if str(value).strip()
        )
    )
    if not normalized_device_abis:
        return base.package_name, (base, *splits)

    device_set = set(normalized_device_abis)
    package_native_abis = {
        abi
        for item in badgings
        for abi in item.native_codes
        if abi
    }

    if base.native_codes and not (
        device_set & set(base.native_codes)
    ):
        raise PackageInputError(
            "Базовый APK содержит нативные библиотеки только для "
            f"{_format_abis(base.native_codes)}, а текущий эмулятор "
            f"поддерживает {_format_abis(normalized_device_abis)}. "
            "Установка невозможна."
        )

    if package_native_abis and not (
        device_set & package_native_abis
    ):
        raise PackageInputError(
            "XAPK содержит нативные библиотеки только для "
            f"{_format_abis(sorted(package_native_abis))}, а текущий "
            f"эмулятор поддерживает {_format_abis(normalized_device_abis)}. "
            "Установка невозможна."
        )

    selected_splits: list[ApkBadging] = []
    for split in splits:
        if not split.native_codes:
            selected_splits.append(split)
            continue
        if device_set & set(split.native_codes):
            selected_splits.append(split)

    return base.package_name, (
        base,
        *selected_splits,
    )


def _safe_member_path(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise PackageInputError(
            f"Небезопасный путь внутри XAPK: {name}"
        )
    if not path.parts:
        raise PackageInputError("Пустой путь внутри XAPK")
    return path


def _extract_selected_members(
    archive: zipfile.ZipFile,
    destination: Path,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    apk_files: list[Path] = []
    obb_files: list[Path] = []
    total_bytes = 0

    for info in archive.infolist():
        if info.is_dir():
            continue
        if info.flag_bits & 0x1:
            raise PackageInputError(
                "Зашифрованные файлы внутри XAPK не поддерживаются"
            )

        member = _safe_member_path(info.filename)
        suffix = member.suffix.lower()
        if suffix not in {".apk", ".obb"}:
            continue

        total_bytes += int(info.file_size)
        if total_bytes > MAX_XAPK_EXTRACTED_BYTES:
            raise PackageInputError(
                "XAPK слишком велик для безопасной распаковки"
            )

        target = destination.joinpath(*member.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with archive.open(info, "r") as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink, length=1024 * 1024)
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            raise PackageInputError(
                f"Не удалось извлечь {info.filename} из XAPK: {exc}"
            ) from exc

        if suffix == ".apk":
            apk_files.append(target)
            if len(apk_files) > MAX_XAPK_APKS:
                raise PackageInputError(
                    "XAPK содержит слишком много APK-частей"
                )
        else:
            obb_files.append(target)
            if len(obb_files) > MAX_XAPK_OBBS:
                raise PackageInputError(
                    "XAPK содержит слишком много OBB-файлов"
                )

    if not apk_files:
        raise PackageInputError(
            "В XAPK не найдено ни одного APK"
        )
    return (
        tuple(sorted(apk_files, key=lambda path: str(path).lower())),
        tuple(sorted(obb_files, key=lambda path: str(path).lower())),
    )


@contextlib.contextmanager
def materialize_android_package(
    source_path: str | Path,
) -> Iterator[MaterializedPackage]:
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise PackageInputError(
            f"Файл приложения не найден: {source}"
        )

    suffix = source.suffix.lower()
    if suffix == ".apk":
        yield MaterializedPackage(
            source=source,
            source_format="apk",
            apk_files=(source,),
            obb_files=(),
        )
        return

    if suffix != ".xapk":
        raise PackageInputError(
            "Поддерживаются только APK и XAPK"
        )

    with tempfile.TemporaryDirectory(
        prefix="apk-research-xapk-"
    ) as temporary:
        destination = Path(temporary)
        try:
            with zipfile.ZipFile(source, "r") as archive:
                apk_files, obb_files = _extract_selected_members(
                    archive,
                    destination,
                )
        except zipfile.BadZipFile as exc:
            raise PackageInputError(
                "XAPK повреждён или не является ZIP-контейнером"
            ) from exc

        yield MaterializedPackage(
            source=source,
            source_format="xapk",
            apk_files=apk_files,
            obb_files=obb_files,
        )
