from __future__ import annotations

from pathlib import Path

from mobile_research.desktop.android_runtime import (
    parse_aapt_package_name,
)
from mobile_research.desktop.components import (
    ComponentManager,
    repository_base_url,
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
        host_os="windows",
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


def test_software_emulator_command_uses_unaccelerated_mode(
    tmp_path: Path,
) -> None:
    from mobile_research.desktop.android_runtime import AndroidRuntime

    manager = ComponentManager(tmp_path)
    runtime = AndroidRuntime(manager)
    runtime._software_acceleration = True
    command = runtime._emulator_command()

    assert "-accel" in command
    assert command[command.index("-accel") + 1] == "off"
    assert "-gpu" in command
    assert command[command.index("-gpu") + 1] == "swiftshader"


def test_repository_base_url_follows_metadata_directory() -> None:
    assert repository_base_url(
        "https://dl.google.com/android/repository/sys-img/android/sys-img2-3.xml"
    ) == (
        "https://dl.google.com/android/repository/"
        "sys-img/android/"
    )


def test_repository_policy_prefers_latest_stable_over_canary() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <sdk:sdk-repository xmlns:sdk='urn:test'>
      <remotePackage path='emulator'>
        <revision><major>37</major><minor>1</minor><micro>10</micro></revision>
        <channelRef ref='channel-0'/>
        <archives><archive><host-os>windows</host-os><complete>
          <size>100</size><checksum type='sha1'>aa</checksum>
          <url>stable-old.zip</url>
        </complete></archive></archives>
      </remotePackage>
      <remotePackage path='emulator'>
        <revision><major>38</major><minor>0</minor><micro>0</micro></revision>
        <channelRef ref='channel-3'/>
        <archives><archive><host-os>windows</host-os><complete>
          <size>300</size><checksum type='sha1'>cc</checksum>
          <url>canary.zip</url>
        </complete></archive></archives>
      </remotePackage>
      <remotePackage path='emulator'>
        <revision><major>37</major><minor>1</minor><micro>11</micro></revision>
        <channelRef ref='channel-0'/>
        <archives><archive><host-os>windows</host-os><complete>
          <size>200</size><checksum type='sha1'>bb</checksum>
          <url>stable-new.zip</url>
        </complete></archive></archives>
      </remotePackage>
    </sdk:sdk-repository>"""

    result = select_archive_from_repository_xml(
        xml,
        "emulator",
        host_os="windows",
        base_url="https://example.invalid/repository/",
    )

    assert result.url.endswith("stable-new.zip")
    assert result.size == 200
    assert result.checksum == "bb"


def test_repository_policy_treats_missing_channel_as_stable() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <sdk:sdk-repository xmlns:sdk='urn:test'>
      <remotePackage path='platform-tools'>
        <revision><major>37</major><minor>0</minor><micro>1</micro></revision>
        <archives><archive><host-os>windows</host-os><complete>
          <size>123</size><checksum type='sha1'>aa</checksum>
          <url>platform-tools.zip</url>
        </complete></archive></archives>
      </remotePackage>
    </sdk:sdk-repository>"""

    result = select_archive_from_repository_xml(
        xml,
        "platform-tools",
        host_os="windows",
        base_url="https://example.invalid/repository/",
    )

    assert result.url.endswith("platform-tools.zip")


def test_remove_all_deletes_only_managed_component_tree(
    tmp_path: Path,
) -> None:
    manager = ComponentManager(tmp_path / "components")
    manager.paths.root.mkdir(parents=True)
    (manager.paths.root / "marker.txt").write_text(
        "managed",
        encoding="utf-8",
    )

    research_marker = tmp_path / "research.txt"
    research_marker.write_text(
        "keep",
        encoding="utf-8",
    )

    manager.remove_all()

    assert not manager.paths.root.exists()
    assert research_marker.read_text(encoding="utf-8") == "keep"
