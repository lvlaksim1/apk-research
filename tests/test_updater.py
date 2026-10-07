from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from apk_research.desktop.updater import (
    DownloadedUpdate,
    ReleaseInfo,
    UpdateError,
    build_windows_update_script,
    check_latest_release,
    download_release,
    is_newer_version,
    parse_release_version,
)


class FakeResponse:
    def __init__(
        self,
        data: bytes,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._data = data
        self._offset = 0
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            data = self._data[self._offset :]
            self._offset = len(self._data)
            return data
        data = self._data[
            self._offset : self._offset + size
        ]
        self._offset += len(data)
        return data


def test_semantic_release_version_comparison() -> None:
    assert parse_release_version("v0.28.0") == (0, 28, 0)
    assert is_newer_version("0.28.0", "0.27.0") is True
    assert is_newer_version("0.27.0", "0.27.0") is False
    assert is_newer_version("0.26.9", "0.27.0") is False

    with pytest.raises(UpdateError):
        parse_release_version("0.28")


def test_check_latest_release_resolves_exact_assets() -> None:
    payload = {
        "tag_name": "v0.28.0",
        "draft": False,
        "prerelease": False,
        "html_url": (
            "https://github.com/lvlaksim1/"
            "apk-research/releases/tag/v0.28.0"
        ),
        "assets": [
            {
                "name": "apk-research-setup_v0.28.0.exe",
                "size": 12345,
                "browser_download_url": (
                    "https://github.com/lvlaksim1/apk-research/"
                    "releases/download/v0.28.0/"
                    "apk-research-setup_v0.28.0.exe"
                ),
            },
            {
                "name": "SHA256SUMS.txt",
                "size": 98,
                "browser_download_url": (
                    "https://github.com/lvlaksim1/apk-research/"
                    "releases/download/v0.28.0/SHA256SUMS.txt"
                ),
            },
        ],
    }

    def opener(request, timeout):
        assert timeout == 15.0
        assert request.full_url.endswith("/releases/latest")
        return FakeResponse(
            json.dumps(payload).encode("utf-8")
        )

    release = check_latest_release(
        "0.27.0",
        opener=opener,
    )

    assert release.version == "0.28.0"
    assert (
        release.installer_name
        == "apk-research-setup_v0.28.0.exe"
    )
    assert release.installer_size == 12345


def test_download_release_verifies_published_sha256(
    tmp_path: Path,
    monkeypatch,
) -> None:
    installer = b"verified installer bytes"
    digest = hashlib.sha256(installer).hexdigest()
    release = ReleaseInfo(
        version="0.28.0",
        tag="v0.28.0",
        installer_name="apk-research-setup_v0.28.0.exe",
        installer_url=(
            "https://github.com/lvlaksim1/apk-research/"
            "releases/download/v0.28.0/"
            "apk-research-setup_v0.28.0.exe"
        ),
        installer_size=len(installer),
        checksums_url=(
            "https://github.com/lvlaksim1/apk-research/"
            "releases/download/v0.28.0/SHA256SUMS.txt"
        ),
        release_url="",
    )
    monkeypatch.setattr(
        "apk_research.desktop.updater.tempfile.mkdtemp",
        lambda prefix: str(tmp_path / "update"),
    )

    def opener(request, timeout):
        if request.full_url.endswith("SHA256SUMS.txt"):
            return FakeResponse(
                (
                    f"{digest}  {release.installer_name}\n"
                ).encode("ascii")
            )
        return FakeResponse(
            installer,
            headers={
                "Content-Length": str(len(installer))
            },
        )

    progress: list[tuple[int, int]] = []
    downloaded = download_release(
        release,
        current_version="0.27.0",
        opener=opener,
        progress=lambda current, total: progress.append(
            (current, total)
        ),
    )

    assert downloaded.sha256 == digest
    assert downloaded.installer_path.read_bytes() == installer
    assert progress[-1] == (
        len(installer),
        len(installer),
    )


def test_download_release_rejects_bad_checksum(
    tmp_path: Path,
    monkeypatch,
) -> None:
    installer = b"tampered installer"
    release = ReleaseInfo(
        version="0.28.0",
        tag="v0.28.0",
        installer_name="apk-research-setup_v0.28.0.exe",
        installer_url=(
            "https://github.com/lvlaksim1/apk-research/"
            "releases/download/v0.28.0/"
            "apk-research-setup_v0.28.0.exe"
        ),
        installer_size=len(installer),
        checksums_url=(
            "https://github.com/lvlaksim1/apk-research/"
            "releases/download/v0.28.0/SHA256SUMS.txt"
        ),
        release_url="",
    )
    monkeypatch.setattr(
        "apk_research.desktop.updater.tempfile.mkdtemp",
        lambda prefix: str(tmp_path / "update"),
    )

    def opener(request, timeout):
        if request.full_url.endswith("SHA256SUMS.txt"):
            return FakeResponse(
                (
                    "0" * 64
                    + f"  {release.installer_name}\n"
                ).encode("ascii")
            )
        return FakeResponse(installer)

    with pytest.raises(UpdateError, match="SHA-256"):
        download_release(
            release,
            current_version="0.27.0",
            opener=opener,
        )


def test_windows_update_script_waits_installs_and_restarts(
    tmp_path: Path,
) -> None:
    installer = tmp_path / "apk-research-setup_v0.28.0.exe"
    install_dir = tmp_path / "Program Files" / "apk-research"
    restart = install_dir / "apk-research.exe"

    script = build_windows_update_script(
        current_pid=4321,
        installer_path=installer,
        install_dir=install_dir,
        restart_exe=restart,
    )

    assert "Wait-Process -Id 4321" in script
    assert "/VERYSILENT" in script
    assert "/SUPPRESSMSGBOXES" in script
    assert f"/DIR={install_dir}" in script
    assert "Start-Process -FilePath $restart" in script
