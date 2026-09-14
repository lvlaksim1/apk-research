from __future__ import annotations

import urllib.parse
from xml.etree import ElementTree

STABLE_CHANNEL = "channel-0"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(element: ElementTree.Element, name: str):
    for value in element:
        if _local_name(value.tag) == name:
            return value
    return None


def _text(element: ElementTree.Element, name: str) -> str | None:
    value = _child(element, name)
    if value is None:
        return None
    return (value.text or "").strip() or None


def _channel(package: ElementTree.Element) -> str:
    value = _child(package, "channelRef")
    if value is None:
        return STABLE_CHANNEL
    return value.attrib.get("ref") or STABLE_CHANNEL


def _revision(package: ElementTree.Element) -> tuple[int, int, int, int]:
    value = _child(package, "revision")
    if value is None:
        return (0, 0, 0, 0)

    numbers: list[int] = []
    for name in ("major", "minor", "micro", "preview"):
        raw = _text(value, name)
        try:
            numbers.append(int(raw) if raw else 0)
        except ValueError:
            numbers.append(0)
    return tuple(numbers)  # type: ignore[return-value]


def select_stable_archive(
    xml_bytes: bytes,
    package_path: str,
    *,
    host_os: str,
    base_url: str,
):
    from mobile_research.desktop.components import (
        ArchiveInfo,
        ComponentInstallError,
    )

    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise ComponentInstallError(
            "Android repository metadata is invalid XML"
        ) from exc

    packages = [
        element
        for element in root.iter()
        if _local_name(element.tag) == "remotePackage"
        and element.attrib.get("path") == package_path
        and _channel(element) == STABLE_CHANNEL
    ]
    if not packages:
        raise ComponentInstallError(
            "Stable Android repository package is unavailable: "
            f"{package_path}"
        )

    package = max(packages, key=_revision)

    for archive in package.iter():
        if _local_name(archive.tag) != "archive":
            continue
        archive_host = _text(archive, "host-os")
        if archive_host and archive_host.lower() != host_os.lower():
            continue

        complete = _child(archive, "complete")
        if complete is None:
            continue

        url_text = _text(complete, "url")
        if not url_text:
            continue

        size_text = _text(complete, "size")
        try:
            size = int(size_text) if size_text else None
        except ValueError:
            size = None

        checksum = None
        checksum_type = None
        for value in complete:
            if _local_name(value.tag) == "checksum":
                checksum = (value.text or "").strip() or None
                checksum_type = value.attrib.get("type") or "sha1"
                break

        return ArchiveInfo(
            package_path=package_path,
            url=urllib.parse.urljoin(base_url, url_text),
            size=size,
            checksum=checksum,
            checksum_type=checksum_type,
        )

    raise ComponentInstallError(
        f"No stable Windows archive found: {package_path}"
    )
