from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from apk_research.desktop.package_input import (
    ApkBadging,
    PackageInputError,
    materialize_android_package,
    parse_apk_badging,
    validate_apk_set,
)


def test_parse_apk_badging_reads_base_and_split(tmp_path: Path) -> None:
    base = parse_apk_badging(
        "package: name='com.example.app' versionCode='42' versionName='1.0'\n",
        tmp_path / "base.apk",
    )
    split = parse_apk_badging(
        "package: name='com.example.app' versionCode='42' "
        "versionName='1.0' split='config.arm64_v8a'\n",
        tmp_path / "config.apk",
    )

    assert base.package_name == "com.example.app"
    assert base.version_code == "42"
    assert base.split_name is None
    assert split.split_name == "config.arm64_v8a"


def test_validate_apk_set_orders_base_first(tmp_path: Path) -> None:
    package, ordered = validate_apk_set(
        [
            ApkBadging(
                tmp_path / "z.apk",
                "com.example.app",
                "42",
                "config.xxhdpi",
            ),
            ApkBadging(
                tmp_path / "base.apk",
                "com.example.app",
                "42",
                None,
            ),
            ApkBadging(
                tmp_path / "a.apk",
                "com.example.app",
                "42",
                "config.arm64_v8a",
            ),
        ]
    )

    assert package == "com.example.app"
    assert [item.split_name for item in ordered] == [
        None,
        "config.arm64_v8a",
        "config.xxhdpi",
    ]


def test_validate_apk_set_rejects_mixed_packages(tmp_path: Path) -> None:
    with pytest.raises(PackageInputError, match="разных package name"):
        validate_apk_set(
            [
                ApkBadging(
                    tmp_path / "base.apk",
                    "com.example.one",
                    "1",
                    None,
                ),
                ApkBadging(
                    tmp_path / "split.apk",
                    "com.example.two",
                    "1",
                    "config.arm64_v8a",
                ),
            ]
        )


def test_validate_apk_set_requires_one_base(tmp_path: Path) -> None:
    with pytest.raises(PackageInputError, match="ровно один базовый APK"):
        validate_apk_set(
            [
                ApkBadging(
                    tmp_path / "one.apk",
                    "com.example.app",
                    "1",
                    "config.arm64_v8a",
                ),
                ApkBadging(
                    tmp_path / "two.apk",
                    "com.example.app",
                    "1",
                    "config.xxhdpi",
                ),
            ]
        )


def test_materialize_xapk_extracts_only_apk_and_obb(tmp_path: Path) -> None:
    archive_path = tmp_path / "sample.xapk"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("base.apk", b"base")
        archive.writestr("splits/config.arm64_v8a.apk", b"split")
        archive.writestr(
            "Android/obb/com.example.app/main.42.com.example.app.obb",
            b"obb",
        )
        archive.writestr("manifest.json", b"{}")
        archive.writestr("icon.png", b"ignored")

    with materialize_android_package(archive_path) as bundle:
        assert bundle.source_format == "xapk"
        assert [path.name for path in bundle.apk_files] == [
            "base.apk",
            "config.arm64_v8a.apk",
        ]
        assert [path.suffix for path in bundle.obb_files] == [".obb"]
        extracted_root = bundle.apk_files[0].parent
        assert bundle.apk_files[0].read_bytes() == b"base"
        assert bundle.obb_files[0].read_bytes() == b"obb"

    assert not extracted_root.exists()


def test_materialize_xapk_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "bad.xapk"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../base.apk", b"base")

    with pytest.raises(PackageInputError, match="Небезопасный путь"):
        with materialize_android_package(archive_path):
            pass


def test_materialize_rejects_unknown_extension(tmp_path: Path) -> None:
    path = tmp_path / "sample.apks"
    path.write_bytes(b"not used")

    with pytest.raises(PackageInputError, match="только APK и XAPK"):
        with materialize_android_package(path):
            pass
