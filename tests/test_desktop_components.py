from __future__ import annotations

from pathlib import Path

from mobile_research.desktop.android_runtime import (
    parse_aapt_package_name,
)
from mobile_research.desktop.components import (
    ComponentManager,
    select_archive_from_repository_xml,
)


def test_repository_xml_selects_windows_archive() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <sdk:sdk-repository xmlns:sdk='urn:test'>
      <remotePackage path='emulator'>
        <archives>
          <archive>
            <host-os>linux</host-os>
            <complete><size>1</size><checksum type='sha1'>aa</checksum><url>linux.zip</url></complete>
          </archive>
          <archive>
            <host-os>windows</host-os>
            <complete><size>123</size><checksum type='sha1'>bb</checksum><url>windows.zip</url></complete>
          </archive>
        </archives>
      </remotePackage>
    </sdk:sdk-repository>"""
    result = select_archive_from_repository_xml(
        xml,
        "emulator",
        base_url="https://example.invalid/repository/",
    )
    assert result.url == "https://example.invalid/repository/windows.zip"
    assert result.size == 123
    assert result.checksum == "bb"


def test_parse_aapt_package_name() -> None:
    output = (
        "package: name='com.example.research' "
        "versionCode='42' versionName='1.2'\n"
    )
    assert parse_aapt_package_name(output) == "com.example.research"


def test_avd_profile_is_private_to_mobile_research(
    tmp_path: Path,
) -> None:
    manager = ComponentManager(tmp_path)
    manager.paths.system_image.mkdir(parents=True)
    (manager.paths.system_image / "system.img").write_bytes(b"test")
    manager.create_avd_profile()

    assert manager.paths.avd_ini.is_file()
    config = (manager.paths.avd_dir / "config.ini").read_text(
        encoding="utf-8"
    )
    assert "target=android-35" in config
    assert "PlayStore.enabled=false" in config
    assert (
        "image.sysdir.1=system-images\\android-35\\default\\x86_64\\"
        in config
    )
