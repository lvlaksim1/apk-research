from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

REPOSITORY = "lvlaksim1/apk-research"
LATEST_RELEASE_URL = (
    f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
)
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_SHA256_RE = re.compile(r"^([0-9a-fA-F]{64})\s+[* ]?(.+?)\s*$")


class UpdateError(RuntimeError):
    """Raised when update discovery/download/application cannot continue."""


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag: str
    installer_name: str
    installer_url: str
    installer_size: int
    checksums_url: str
    release_url: str


@dataclass(frozen=True)
class DownloadedUpdate:
    release: ReleaseInfo
    installer_path: Path
    sha256: str


def parse_release_version(value: str) -> tuple[int, int, int]:
    match = _VERSION_RE.fullmatch(str(value).strip())
    if not match:
        raise UpdateError(
            f"Неподдерживаемый номер версии: {value!r}"
        )
    return tuple(int(part) for part in match.groups())


def is_newer_version(latest: str, current: str) -> bool:
    return parse_release_version(latest) > parse_release_version(current)


def _request(
    url: str,
    *,
    current_version: str,
) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"apk-research/{current_version}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )


def _open(
    opener: Callable,
    request: urllib.request.Request,
    timeout: float,
):
    try:
        return opener(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise UpdateError(
            f"GitHub вернул HTTP {exc.code}"
        ) from exc
    except urllib.error.URLError as exc:
        raise UpdateError(
            "Не удалось подключиться к GitHub: "
            + str(exc.reason)
        ) from exc
    except OSError as exc:
        raise UpdateError(
            "Не удалось подключиться к GitHub: "
            + str(exc)
        ) from exc


def check_latest_release(
    current_version: str,
    *,
    opener: Callable = urllib.request.urlopen,
    timeout: float = 15.0,
) -> ReleaseInfo:
    request = _request(
        LATEST_RELEASE_URL,
        current_version=current_version,
    )
    with _open(opener, request, timeout) as response:
        try:
            payload = json.loads(
                response.read().decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpdateError(
                "GitHub вернул некорректное описание релиза"
            ) from exc

    if not isinstance(payload, dict):
        raise UpdateError(
            "GitHub вернул некорректное описание релиза"
        )
    if payload.get("draft") is True or payload.get("prerelease") is True:
        raise UpdateError(
            "Последний релиз GitHub не является стабильным"
        )

    tag = str(payload.get("tag_name") or "").strip()
    latest_tuple = parse_release_version(tag)
    version = ".".join(str(part) for part in latest_tuple)

    assets = payload.get("assets") or []
    if not isinstance(assets, list):
        raise UpdateError("У релиза GitHub нет списка файлов")

    installer_name = f"apk-research-setup_v{version}.exe"
    installer = next(
        (
            item
            for item in assets
            if isinstance(item, dict)
            and item.get("name") == installer_name
        ),
        None,
    )
    checksums = next(
        (
            item
            for item in assets
            if isinstance(item, dict)
            and item.get("name") == "SHA256SUMS.txt"
        ),
        None,
    )
    if installer is None or checksums is None:
        raise UpdateError(
            "В последнем релизе отсутствует установщик "
            "или SHA256SUMS.txt"
        )

    installer_url = str(
        installer.get("browser_download_url") or ""
    )
    checksums_url = str(
        checksums.get("browser_download_url") or ""
    )
    if not installer_url.startswith(
        "https://github.com/lvlaksim1/apk-research/"
    ):
        raise UpdateError(
            "GitHub вернул неожиданный адрес установщика"
        )
    if not checksums_url.startswith(
        "https://github.com/lvlaksim1/apk-research/"
    ):
        raise UpdateError(
            "GitHub вернул неожиданный адрес контрольной суммы"
        )

    return ReleaseInfo(
        version=version,
        tag=tag,
        installer_name=installer_name,
        installer_url=installer_url,
        installer_size=int(installer.get("size") or 0),
        checksums_url=checksums_url,
        release_url=str(payload.get("html_url") or ""),
    )


def _expected_checksum(
    text: str,
    installer_name: str,
) -> str:
    for raw_line in text.splitlines():
        match = _SHA256_RE.match(raw_line)
        if not match:
            continue
        digest, filename = match.groups()
        if filename.strip() == installer_name:
            return digest.lower()
    raise UpdateError(
        "SHA256SUMS.txt не содержит контрольную сумму установщика"
    )


def download_release(
    release: ReleaseInfo,
    *,
    current_version: str,
    opener: Callable = urllib.request.urlopen,
    timeout: float = 60.0,
    progress: Callable[[int, int], None] | None = None,
) -> DownloadedUpdate:
    checksum_request = _request(
        release.checksums_url,
        current_version=current_version,
    )
    with _open(opener, checksum_request, timeout) as response:
        try:
            checksum_text = response.read().decode("ascii")
        except UnicodeDecodeError as exc:
            raise UpdateError(
                "SHA256SUMS.txt имеет некорректную кодировку"
            ) from exc

    expected = _expected_checksum(
        checksum_text,
        release.installer_name,
    )

    root = Path(
        tempfile.mkdtemp(prefix="apk-research-update-")
    )
    root.mkdir(parents=True, exist_ok=True)
    partial = root / (release.installer_name + ".part")
    final = root / release.installer_name
    hasher = hashlib.sha256()
    downloaded = 0
    total = max(0, int(release.installer_size))

    installer_request = _request(
        release.installer_url,
        current_version=current_version,
    )
    try:
        with _open(
            opener,
            installer_request,
            timeout,
        ) as response, partial.open("wb") as handle:
            header_length = response.headers.get(
                "Content-Length"
            )
            if header_length:
                try:
                    total = max(total, int(header_length))
                except ValueError:
                    pass

            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                hasher.update(chunk)
                downloaded += len(chunk)
                if progress is not None:
                    progress(downloaded, total)
    except Exception:
        partial.unlink(missing_ok=True)
        raise

    if release.installer_size > 0 and downloaded != release.installer_size:
        partial.unlink(missing_ok=True)
        raise UpdateError(
            "Размер скачанного установщика не совпадает "
            "с опубликованным релизом"
        )

    actual = hasher.hexdigest().lower()
    if actual != expected:
        partial.unlink(missing_ok=True)
        raise UpdateError(
            "SHA-256 скачанного установщика не совпадает "
            "с SHA256SUMS.txt"
        )

    partial.replace(final)
    return DownloadedUpdate(
        release=release,
        installer_path=final,
        sha256=actual,
    )


def update_log_path() -> Path:
    root = Path(
        os.environ.get(
            "LOCALAPPDATA",
            tempfile.gettempdir(),
        )
    ) / "apk-research" / "updates"
    root.mkdir(parents=True, exist_ok=True)
    return root / "installer.log"


def build_installer_arguments(
    *,
    install_dir: Path,
    log_path: Path,
    relaunch: bool = True,
) -> list[str]:
    arguments = [
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CLOSEAPPLICATIONS",
        "/SP-",
        "/UPDATE=1",
        f"/DIR={install_dir}",
        f"/LOG={log_path}",
    ]
    if not relaunch:
        arguments.append("/NORELAUNCH=1")
    return arguments


def launch_update_after_exit(
    downloaded: DownloadedUpdate,
    *,
    current_pid: int,
    install_dir: Path,
    restart_exe: Path,
    relaunch: bool = True,
) -> None:
    del current_pid
    del restart_exe

    if os.name != "nt":
        raise UpdateError(
            "Автоматическая установка обновления "
            "поддерживается только в Windows"
        )
    if not downloaded.installer_path.is_file():
        raise UpdateError(
            "Скачанный установщик обновления не найден"
        )

    target_dir = Path(install_dir).resolve()
    log_path = update_log_path()
    arguments = build_installer_arguments(
        install_dir=target_dir,
        log_path=log_path,
        relaunch=relaunch,
    )

    handoff_log = log_path.with_name(
        "handoff.log"
    )
    try:
        handoff_log.write_text(
            "\n".join(
                [
                    "apk-research updater handoff",
                    f"installer={downloaded.installer_path}",
                    f"target={target_dir}",
                    f"release={downloaded.release.version}",
                    "mode=direct-inno",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass

    creation_flags = getattr(
        subprocess,
        "CREATE_NEW_PROCESS_GROUP",
        0,
    )
    try:
        subprocess.Popen(
            [
                str(downloaded.installer_path),
                *arguments,
            ],
            cwd=str(downloaded.installer_path.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            close_fds=True,
        )
    except OSError as exc:
        raise UpdateError(
            "Не удалось запустить установщик обновления: "
            + str(exc)
        ) from exc

) -> None:
    if os.name != "nt":
        raise UpdateError(
            "Автоматическая установка обновления "
            "поддерживается только в Windows"
        )
    if not downloaded.installer_path.is_file():
        raise UpdateError(
            "Скачанный установщик обновления не найден"
        )

    script = build_windows_update_script(
        current_pid=current_pid,
        installer_path=downloaded.installer_path,
        install_dir=install_dir,
        restart_exe=restart_exe,
    )
    encoded = base64.b64encode(
        script.encode("utf-16-le")
    ).decode("ascii")
    creation_flags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(
            subprocess,
            "DETACHED_PROCESS",
            0,
        )
    )
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            close_fds=True,
        )
    except OSError as exc:
        raise UpdateError(
            "Не удалось запустить установщик обновления: "
            + str(exc)
        ) from exc
