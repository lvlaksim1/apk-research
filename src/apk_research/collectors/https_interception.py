from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Callable, Protocol, Sequence

from cryptography import x509

from apk_research.session import SessionManager, SessionStatus
from apk_research.targets import AdbClient, AdbError

Clock = Callable[[], datetime]


class ProcessLike(Protocol):
    pid: int
    returncode: int | None

    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...


ProcessFactory = Callable[
    [Sequence[str], BinaryIO],
    ProcessLike,
]


class HttpsInterceptionCollectorError(RuntimeError):
    """Raised when managed HTTPS interception cannot be established."""


@dataclass(frozen=True)
class HttpsInterceptionPreflight:
    serial: str
    root: bool
    nsenter_available: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class HttpsInterceptionResult:
    collector: str
    status: str
    transactions_artifact: str
    metadata_artifact: str
    transaction_count: int
    started_utc: str
    stopped_utc: str
    proxy_returncode: int | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json_atomic(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                value,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _subject_hash_old(certificate_path: Path) -> str:
    data = certificate_path.read_bytes()
    try:
        certificate = x509.load_pem_x509_certificate(data)
    except ValueError:
        certificate = x509.load_der_x509_certificate(data)
    full_hash = hashlib.md5(
        certificate.subject.public_bytes(),
        usedforsecurity=False,
    ).digest()
    value = (
        full_hash[0]
        | (full_hash[1] << 8)
        | (full_hash[2] << 16)
        | (full_hash[3] << 24)
    )
    return f"{value:08x}"


def _default_process_factory(
    command: Sequence[str],
    stderr: BinaryIO,
) -> ProcessLike:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        list(command),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=stderr,
        creationflags=creation_flags,
    )


def _worker_command(arguments: list[str]) -> list[str]:
    if getattr(sys, "frozen", False):
        return [
            sys.executable,
            "--https-proxy-worker",
            *arguments,
        ]
    return [
        sys.executable,
        "-m",
        "apk_research.desktop_entry",
        "--https-proxy-worker",
        *arguments,
    ]


class HttpsInterceptionCollector:
    """Manage HTTP(S) traffic analysis in the dedicated research AVD.

    The Android system proxy and an application-scoped TCP/443 route share
    the same existing HTTPS analyzer. Passive PCAP remains independent.
    """

    NAME = "https_interception"
    BACKEND = "mitmproxy-regular-adb-reverse+app-uid-tcp443-route"
    TRANSACTIONS_ARTIFACT = "02_normalized/http-transactions.jsonl"
    BODIES_DIR = "02_normalized/http-bodies"
    METADATA_ARTIFACT = "02_normalized/http-interception.json"
    STDERR_ARTIFACT = "01_raw/network/https-proxy.stderr.txt"
    DEVICE_PROXY_PORT = 38887
    DEVICE_ROUTE_PORT = 38888
    ROUTE_CHAIN = "APKRS_HTTPS32"
    ROUTE_ROOT = "/data/local/tmp/apk-research/https-route32"
    ROUTE_LOG_ARTIFACT = "01_raw/network/https-direct-route.log"

    def __init__(
        self,
        adb: AdbClient,
        session: SessionManager,
        *,
        package_name: str,
        clock: Clock = _utc_now,
        process_factory: ProcessFactory = _default_process_factory,
    ) -> None:
        self.adb = adb
        self.session = session
        self.package_name = package_name
        self.clock = clock
        self.process_factory = process_factory

        self._preflight: HttpsInterceptionPreflight | None = None
        self._process: ProcessLike | None = None
        self._stderr: BinaryIO | None = None
        self._temp_dir: Path | None = None
        self._host_port: int | None = None
        self._serial = ""
        self._previous_proxy: str | None = None
        self._started_utc: str | None = None
        self._stopped_utc: str | None = None
        self._ca_sha256 = ""
        self._ca_subject_hash = ""
        self._finished = False
        self._proxy_configured = False
        self._reverse_configured = False
        self._ca_injected = False
        self._ca_injection_succeeded = False
        self._route_attempted = False
        self._route_active = False
        self._route_ever_active = False
        self._route_uid: int | None = None
        self._route_binary_sha256 = ""

    @property
    def running(self) -> bool:
        return (
            self._process is not None
            and not self._finished
            and self._process.poll() is None
        )

    def preflight(self) -> HttpsInterceptionPreflight:
        manifest = self.session.manifest
        target = manifest.get("target", {})
        serial = str(target.get("serial") or "").strip()
        kind = str(target.get("kind") or "").strip()
        if not serial:
            raise HttpsInterceptionCollectorError(
                "Session target serial is missing"
            )
        if kind and kind != "emulator":
            raise HttpsInterceptionCollectorError(
                "HTTPS interception currently requires the managed emulator"
            )
        self._serial = serial
        try:
            self.adb.ensure_ready(serial)
            uid = self.adb.get_uid(serial)
            apex = self._shell_script(
                "if [ -d /apex/com.android.conscrypt/cacerts ]; "
                "then echo apex; else echo legacy; fi"
            ).strip()
            nsenter_available = (
                "nsenter"
                in self._shell_script(
                    "command -v nsenter || true"
                )
            )
        except AdbError as exc:
            raise HttpsInterceptionCollectorError(str(exc)) from exc
        if uid != 0:
            raise HttpsInterceptionCollectorError(
                "HTTPS interception requires root ADB on AVD-RESEARCH"
            )
        if apex == "apex" and not nsenter_available:
            raise HttpsInterceptionCollectorError(
                "Android Conscrypt APEX is active but nsenter is unavailable"
            )
        self._preflight = HttpsInterceptionPreflight(
            serial=serial,
            root=True,
            nsenter_available=nsenter_available,
        )
        return self._preflight

    def start(self) -> None:
        if self._finished or self._process is not None:
            raise HttpsInterceptionCollectorError(
                "HTTPS interception collector was already started"
            )
        if self.session.status != SessionStatus.STARTING:
            raise HttpsInterceptionCollectorError(
                "HTTPS interception may start only while the session is starting"
            )
        if self._preflight is None:
            self.preflight()

        self.session.register_collector(
            self.NAME,
            required=True,
            backend=self.BACKEND,
        )
        for kind, relative_path, raw in (
            ("http_transactions", self.TRANSACTIONS_ARTIFACT, False),
            ("http_interception_metadata", self.METADATA_ARTIFACT, False),
            ("http_proxy_stderr", self.STDERR_ARTIFACT, True),
            ("https_route_diagnostics", self.ROUTE_LOG_ARTIFACT, True),
        ):
            self.session.register_artifact(
                kind=kind,
                relative_path=relative_path,
                source=self.NAME,
                raw=raw,
            )
            self.session.update_collector(
                self.NAME,
                "starting",
                artifact_path=relative_path,
            )

        transactions_path = (
            self.session.paths.root / self.TRANSACTIONS_ARTIFACT
        )
        bodies_dir = self.session.paths.root / self.BODIES_DIR
        stderr_path = self.session.paths.root / self.STDERR_ARTIFACT
        transactions_path.parent.mkdir(parents=True, exist_ok=True)
        bodies_dir.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        (self.session.paths.root / self.ROUTE_LOG_ARTIFACT).parent.mkdir(
            parents=True, exist_ok=True,
        )
        (self.session.paths.root / self.ROUTE_LOG_ARTIFACT).touch(exist_ok=True)
        transactions_path.touch(exist_ok=True)
        self._stderr = stderr_path.open("wb")

        self._temp_dir = Path(
            tempfile.mkdtemp(prefix="apk-research-https-")
        )
        confdir = self._temp_dir / "mitmproxy"
        ready_file = self._temp_dir / "ready.json"
        error_file = self._temp_dir / "error.txt"
        self._host_port = self._allocate_host_port()

        args = [
            "--listen-port",
            str(self._host_port),
            "--confdir",
            str(confdir),
            "--transactions",
            str(transactions_path),
            "--bodies",
            str(bodies_dir),
            "--ready-file",
            str(ready_file),
            "--error-file",
            str(error_file),
        ]
        command = _worker_command(args)
        self._started_utc = _iso_utc(self.clock())

        try:
            self._process = self.process_factory(
                command,
                self._stderr,
            )
            ca_cert = self._wait_for_proxy(
                ready_file,
                error_file,
                confdir,
            )
            self._ca_sha256 = hashlib.sha256(
                ca_cert.read_bytes()
            ).hexdigest()
            self._ca_subject_hash = _subject_hash_old(ca_cert)
            self._inject_ca(ca_cert)
            self._configure_proxy()
            self._configure_direct_route()
        except Exception as exc:
            self._cleanup_best_effort()
            message = str(exc) or exc.__class__.__name__
            self.session.update_collector(
                self.NAME,
                "failed",
                error=message,
            )
            self._write_metadata(
                "failed",
                error=message,
            )
            self._finished = True
            raise HttpsInterceptionCollectorError(message) from exc

        self.session.update_collector(
            self.NAME,
            "running",
        )
        self._write_metadata(
            "running",
            error=None,
        )

    def check_health(self) -> bool:
        if not self.running:
            if not self._finished:
                self.session.update_collector(
                    self.NAME,
                    "failed",
                    error="HTTPS proxy worker is not running",
                )
            return False
        return True

    def stop(
        self,
        grace_period: float = 3.0,
    ) -> HttpsInterceptionResult:
        if self._finished:
            raise HttpsInterceptionCollectorError(
                "HTTPS interception collector is already stopped"
            )
        if grace_period <= 0:
            raise ValueError("grace_period must be positive")

        # Remove the application-scoped Android route first, then stop its
        # host analyzer. This avoids leaving the selected app without HTTPS.
        self._stop_direct_route()
        process = self._process
        returncode: int | None = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                returncode = process.wait(timeout=grace_period)
            except subprocess.TimeoutExpired:
                process.kill()
                returncode = process.wait(timeout=2.0)
        elif process is not None:
            returncode = process.poll()

        self._cleanup_device_best_effort()
        if self._stderr is not None:
            self._stderr.close()
            self._stderr = None
        self._stopped_utc = _iso_utc(self.clock())
        self._finished = True

        count = self._transaction_count()
        status = "completed"
        self.session.update_collector(
            self.NAME,
            status,
        )
        self._write_metadata(
            status,
            error=None,
            proxy_returncode=returncode,
            transaction_count=count,
        )
        self._cleanup_temp_dir()

        return HttpsInterceptionResult(
            collector=self.NAME,
            status=status,
            transactions_artifact=self.TRANSACTIONS_ARTIFACT,
            metadata_artifact=self.METADATA_ARTIFACT,
            transaction_count=count,
            started_utc=self._started_utc or "",
            stopped_utc=self._stopped_utc,
            proxy_returncode=returncode,
        )

    def _allocate_host_port(self) -> int:
        import socket

        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        ) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _wait_for_proxy(
        self,
        ready_file: Path,
        error_file: Path,
        confdir: Path,
    ) -> Path:
        deadline = time.monotonic() + 30.0
        ca_cert = confdir / "mitmproxy-ca-cert.cer"
        while time.monotonic() < deadline:
            if error_file.is_file():
                message = error_file.read_text(
                    encoding="utf-8",
                    errors="replace",
                ).strip()
                raise HttpsInterceptionCollectorError(
                    "HTTPS proxy failed: " + message
                )
            if (
                ready_file.is_file()
                and ca_cert.is_file()
                and ca_cert.stat().st_size > 0
            ):
                return ca_cert
            if self._process is not None:
                returncode = self._process.poll()
                if returncode is not None:
                    raise HttpsInterceptionCollectorError(
                        "HTTPS proxy exited during startup with code "
                        f"{returncode}"
                    )
            time.sleep(0.1)
        raise HttpsInterceptionCollectorError(
            "HTTPS proxy did not become ready within 30 seconds"
        )

    def _inject_ca(self, ca_cert: Path) -> None:
        serial = self._serial
        remote_dir = "/data/local/tmp/apk-research/https"
        remote_cert = (
            f"{remote_dir}/{self._ca_subject_hash}.0"
        )
        self.adb.make_remote_directory(
            serial,
            remote_dir,
        )
        self.adb.push_file(
            serial,
            ca_cert,
            remote_cert,
            timeout=30.0,
        )

        script = f"""
set -eu
CERT={remote_cert}
WORK=/data/local/tmp/apk-research/https-ca
SYSTEM=/system/etc/security/cacerts
APEX=/apex/com.android.conscrypt/cacerts
rm -rf "$WORK"
mkdir -p "$WORK/original"
if [ -d "$APEX" ]; then
  cp "$APEX"/* "$WORK/original/" 2>/dev/null || true
else
  cp "$SYSTEM"/* "$WORK/original/" 2>/dev/null || true
fi
umount "$SYSTEM" 2>/dev/null || true
mount -t tmpfs tmpfs "$SYSTEM"
cp "$WORK/original/"* "$SYSTEM/" 2>/dev/null || true
cp "$CERT" "$SYSTEM/{self._ca_subject_hash}.0"
chown root:root "$SYSTEM"/*
chmod 644 "$SYSTEM"/*
chcon u:object_r:system_file:s0 "$SYSTEM"/* 2>/dev/null || true
if [ -d "$APEX" ]; then
  for Z in $(pidof zygote 2>/dev/null || true) $(pidof zygote64 2>/dev/null || true); do
    nsenter --mount=/proc/$Z/ns/mnt -- /bin/mount --bind "$SYSTEM" "$APEX"
  done
  for P in $(pidof {self.package_name} 2>/dev/null || true); do
    nsenter --mount=/proc/$P/ns/mnt -- /bin/mount --bind "$SYSTEM" "$APEX"
  done
fi
test -s "$SYSTEM/{self._ca_subject_hash}.0"
"""
        output = self._shell_script(
            script,
            timeout=30.0,
        )
        if "permission denied" in output.lower():
            raise HttpsInterceptionCollectorError(
                "Android rejected temporary CA injection: " + output.strip()
            )
        self._ca_injected = True
        self._ca_injection_succeeded = True

    def _shell_script(
        self,
        script: str,
        *,
        timeout: float = 10.0,
    ) -> str:
        remote = "sh -c " + shlex.quote(script)
        return self.adb.shell_output(
            self._serial,
            remote,
            timeout=timeout,
        )

    def _configure_proxy(self) -> None:
        serial = self._serial
        current = self.adb.shell_output(
            serial,
            "settings",
            "get",
            "global",
            "http_proxy",
        ).strip()
        self._previous_proxy = current
        self.adb.reverse_tcp(
            serial,
            device_port=self.DEVICE_PROXY_PORT,
            host_port=int(self._host_port or 0),
        )
        self._reverse_configured = True
        self.adb.shell_output(
            serial,
            "settings",
            "put",
            "global",
            "http_proxy",
            f"127.0.0.1:{self.DEVICE_PROXY_PORT}",
        )
        verified = self.adb.shell_output(
            serial,
            "settings",
            "get",
            "global",
            "http_proxy",
        ).strip()
        if verified != f"127.0.0.1:{self.DEVICE_PROXY_PORT}":
            raise HttpsInterceptionCollectorError(
                "Android proxy setting was not applied: "
                f"{verified!r}"
            )
        self._proxy_configured = True

    @staticmethod
    def _route_executable() -> Path:
        """Find the platform-specific packaged Android route executable."""
        if getattr(sys, "frozen", False):
            root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
            path = (
                root / "apk_research" / "resources"
                / "apk-research-https-route"
            )
        else:
            root = Path(__file__).resolve().parents[3]
            path = root / "build" / "android-route" / "apk-research-https-route"
        if not path.is_file() or path.stat().st_size <= 0:
            raise HttpsInterceptionCollectorError(
                "Служебный модуль направления HTTPS не найден: "
                + str(path)
            )
        return path

    def _target_uid(self) -> int:
        """Obtain the installed target's actual Android application UID."""
        # Android package manager reports the UID; never infer it from names.
        listing = self.adb.shell_output(
            self._serial, "cmd", "package", "list", "packages",
            "-U", "--user", "0", self.package_name,
            timeout=15.0,
        )
        pattern = re.compile(
            r"^package:" + re.escape(self.package_name)
            + r"\s+uid:(\d+)\s*$",
            re.MULTILINE,
        )
        match = pattern.search(listing)
        if not match:
            raise HttpsInterceptionCollectorError(
                "Android не сообщил UID выбранного приложения: "
                + self.package_name
            )
        return int(match.group(1))

    def _configure_direct_route(self) -> None:
        """Add only the selected app's IPv4 TCP/443 to the analyzer route."""
        self._route_uid = self._target_uid()
        binary = self._route_executable()
        self._route_binary_sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()
        remote_binary = self.ROUTE_ROOT + "/apk-research-https-route"
        self._route_attempted = True
        self.adb.make_remote_directory(self._serial, self.ROUTE_ROOT)
        self.adb.push_file(self._serial, binary, remote_binary)
        chain = self.ROUTE_CHAIN
        pid = self.ROUTE_ROOT + "/route.pid"
        log = self.ROUTE_ROOT + "/route.log"
        err = self.ROUTE_ROOT + "/route.stderr.txt"
        script = f"""
set -eu
BIN={remote_binary}
PID={pid}
LOG={log}
ERR={err}
CHAIN={chain}
chmod 700 "$BIN"
# Restore the route from a prior interrupted research session, if present.
iptables -t nat -D OUTPUT -m owner --uid-owner {self._route_uid} -j "$CHAIN" 2>/dev/null || true
iptables -t nat -F "$CHAIN" 2>/dev/null || true
iptables -t nat -X "$CHAIN" 2>/dev/null || true
if [ -f "$PID" ]; then
  PREVIOUS=$(cat "$PID" 2>/dev/null || true)
  case "$PREVIOUS" in
    ''|*[!0-9]*) ;;
    *) kill "$PREVIOUS" 2>/dev/null || true ;;
  esac
fi
rm -f "$LOG" "$ERR" "$PID"
"$BIN" {self.DEVICE_ROUTE_PORT} {self.DEVICE_PROXY_PORT} "$LOG" > /dev/null 2> "$ERR" &
echo $! > "$PID"
READY=0
for ATTEMPT in 1 2 3 4 5 6 7 8 9 10; do
  if grep -q ROUTE_READY "$LOG" 2>/dev/null; then READY=1; break; fi
  sleep 1
done
if [ "$READY" != 1 ]; then
  cat "$ERR" 2>/dev/null || true
  exit 24
fi
iptables -t nat -N "$CHAIN"
iptables -t nat -A "$CHAIN" -d 127.0.0.0/8 -j RETURN
iptables -t nat -A "$CHAIN" -p tcp --dport 443 -j REDIRECT --to-ports {self.DEVICE_ROUTE_PORT}
iptables -t nat -I OUTPUT 1 -m owner --uid-owner {self._route_uid} -j "$CHAIN"
iptables -t nat -C OUTPUT -m owner --uid-owner {self._route_uid} -j "$CHAIN"
printf '%s\\n' ROUTE_ACTIVE
"""
        result = self._shell_script(script, timeout=35.0)
        if "ROUTE_ACTIVE" not in result:
            raise HttpsInterceptionCollectorError(
                "Android не подтвердил направление прямых HTTPS-соединений"
            )
        self._route_active = True
        self._route_ever_active = True

    def _stop_direct_route(self) -> None:
        if not self._route_attempted:
            return
        chain = self.ROUTE_CHAIN
        uid = self._route_uid
        route_rule = (
            f"iptables -t nat -D OUTPUT -m owner --uid-owner {uid} "
            f"-j {chain} 2>/dev/null || true"
            if uid is not None else ":"
        )
        script = f"""
{route_rule}
iptables -t nat -F {chain} 2>/dev/null || true
iptables -t nat -X {chain} 2>/dev/null || true
PID={self.ROUTE_ROOT}/route.pid
if [ -f "$PID" ]; then
  VALUE=$(cat "$PID" 2>/dev/null || true)
  case "$VALUE" in
    ''|*[!0-9]*) ;;
    *) kill "$VALUE" 2>/dev/null || true ;;
  esac
fi
"""
        try:
            self._shell_script(script, timeout=15.0)
        except Exception:
            # The diagnostic file remains available when Android responds.
            pass
        try:
            self.adb.pull_file(
                self._serial,
                self.ROUTE_ROOT + "/route.log",
                self.session.paths.root / self.ROUTE_LOG_ARTIFACT,
                timeout=20.0,
            )
        except Exception:
            pass
        try:
            self._shell_script(
                f"rm -rf {self.ROUTE_ROOT}",
                timeout=15.0,
            )
        except Exception:
            pass
        self._route_active = False
        self._route_attempted = False

    def _cleanup_device_best_effort(self) -> None:
        self._stop_direct_route()
        serial = self._serial
        if not serial:
            return
        if self._proxy_configured:
            try:
                previous = (
                    self._previous_proxy
                    if self._previous_proxy not in {
                        None,
                        "",
                        "null",
                    }
                    else ":0"
                )
                self.adb.shell_output(
                    serial,
                    "settings",
                    "put",
                    "global",
                    "http_proxy",
                    previous,
                )
            except Exception:
                pass
            self._proxy_configured = False
        if self._reverse_configured:
            try:
                self.adb.remove_reverse_tcp(
                    serial,
                    self.DEVICE_PROXY_PORT,
                )
            except Exception:
                pass
            self._reverse_configured = False
        if self._ca_injected:
            try:
                script = """
SYSTEM=/system/etc/security/cacerts
APEX=/apex/com.android.conscrypt/cacerts
if [ -d "$APEX" ]; then
  ZYGS="$(pidof zygote 2>/dev/null || true) $(pidof zygote64 2>/dev/null || true)"
  for Z in $ZYGS; do
    for P in $(ps -A -o PID,PPID 2>/dev/null | awk -v z="$Z" '$2==z {print $1}'); do
      nsenter --mount=/proc/$P/ns/mnt -- /bin/umount "$APEX" 2>/dev/null || true
    done
    nsenter --mount=/proc/$Z/ns/mnt -- /bin/umount "$APEX" 2>/dev/null || true
  done
fi
umount "$SYSTEM" 2>/dev/null || true
rm -rf /data/local/tmp/apk-research/https-ca /data/local/tmp/apk-research/https
"""
                self._shell_script(
                    script,
                    timeout=30.0,
                )
            except Exception:
                pass
            self._ca_injected = False

    def _cleanup_best_effort(self) -> None:
        self._cleanup_device_best_effort()
        process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2.0)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        if self._stderr is not None:
            try:
                self._stderr.close()
            except Exception:
                pass
            self._stderr = None
        self._cleanup_temp_dir()

    def _cleanup_temp_dir(self) -> None:
        if self._temp_dir is not None:
            shutil.rmtree(
                self._temp_dir,
                ignore_errors=True,
            )
            self._temp_dir = None

    def _transaction_count(self) -> int:
        path = (
            self.session.paths.root
            / self.TRANSACTIONS_ARTIFACT
        )
        try:
            with path.open(
                "r",
                encoding="utf-8",
                errors="replace",
            ) as handle:
                return sum(
                    1
                    for line in handle
                    if line.strip()
                )
        except OSError:
            return 0

    def _write_metadata(
        self,
        status: str,
        *,
        error: str | None,
        proxy_returncode: int | None = None,
        transaction_count: int | None = None,
    ) -> None:
        path = (
            self.session.paths.root
            / self.METADATA_ARTIFACT
        )
        _write_json_atomic(
            path,
            {
                "schema_version": "0.1",
                "collector": self.NAME,
                "backend": self.BACKEND,
                "status": status,
                "started_utc": self._started_utc,
                "stopped_utc": self._stopped_utc,
                "host_listen_port": self._host_port,
                "device_proxy": (
                    f"127.0.0.1:{self.DEVICE_PROXY_PORT}"
                    if self._host_port is not None
                    else None
                ),
                "previous_android_proxy": self._previous_proxy,
                "system_ca_injected": self._ca_injected,
                "target_uid": self._route_uid,
                "direct_tcp443_route_configured": self._route_active,
                "direct_tcp443_route_used": self._route_ever_active,
                "direct_route_port": self.DEVICE_ROUTE_PORT,
                "direct_route_binary_sha256": self._route_binary_sha256 or None,
                "system_ca_injection_succeeded": self._ca_injection_succeeded,
                "ca_sha256": self._ca_sha256 or None,
                "ca_subject_hash_old": self._ca_subject_hash or None,
                "http3_enabled": False,
                "active_interception": True,
                "passive_pcap_independent": True,
                "transport_intervention": {
                    "android_explicit_proxy_enabled": True,
                    "device_to_proxy_via_adb_reverse": True,
                    "app_uid_direct_tcp443_route": self._route_active,
                    "other_android_apps_unmodified": True,
                    "direct_route_restricted_to_ipv4_tcp443": True,
                    "quic_udp443_not_handled": True,
                    "may_change_quic_or_http3_behavior": True,
                    "raw_pcap_describes_the_intercepted_environment": True,
                },
                "transaction_count": (
                    self._transaction_count()
                    if transaction_count is None
                    else transaction_count
                ),
                "proxy_returncode": proxy_returncode,
                "error": error,
            },
        )
