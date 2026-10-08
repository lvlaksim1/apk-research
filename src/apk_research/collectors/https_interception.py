from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Callable, Protocol, Sequence

from cryptography import x509

from apk_research.desktop.sidecar import resolve_agent_jar
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


def _default_router_process_factory(
    command: Sequence[str],
    stderr: BinaryIO,
) -> ProcessLike:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        list(command),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
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
    """Managed active HTTP(S) interception for the research AVD.

    Passive PCAP remains independent and authoritative. This collector routes
    Android's explicit HTTP proxy through adb reverse to an isolated mitmproxy
    worker and temporarily injects its CA into the rooted research emulator.
    """

    NAME = "https_interception"
    BACKEND = "mitmproxy-regular-adb-reverse+tproxy-connect-router"
    TRANSACTIONS_ARTIFACT = "02_normalized/http-transactions.jsonl"
    BODIES_DIR = "02_normalized/http-bodies"
    METADATA_ARTIFACT = "02_normalized/http-interception.json"
    STDERR_ARTIFACT = "01_raw/network/https-proxy.stderr.txt"
    ROUTER_STDERR_ARTIFACT = (
        "01_raw/network/https-direct-router.stderr.txt"
    )
    DEVICE_PROXY_PORT = 38887
    DIRECT_ROUTER_PORT = 38888
    DIRECT_ROUTER_PORT_V6 = 38889
    DIRECT_ROUTER_REMOTE_DIR = (
        "/data/local/tmp/apk-research/https-router"
    )
    DIRECT_ROUTER_REMOTE_JAR = (
        DIRECT_ROUTER_REMOTE_DIR + "/apk-research-agent.jar"
    )
    DIRECT_ROUTER_MAIN_CLASS = (
        "com.lvlaksim1.apkresearch.sidecar.DirectHttpsRouter"
    )
    DIRECT_ROUTE_MARK = "0x2301"
    DIRECT_ROUTE_MASK = "0xffffffff"
    DIRECT_ROUTE_TABLE = 230
    DIRECT_ROUTE_PREF = 23000
    DIRECT_OUT_CHAIN = "APKR30_OUT"
    DIRECT_PRE_CHAIN = "APKR30_PRE"

    def __init__(
        self,
        adb: AdbClient,
        session: SessionManager,
        *,
        package_name: str,
        clock: Clock = _utc_now,
        process_factory: ProcessFactory = _default_process_factory,
        router_process_factory: ProcessFactory = (
            _default_router_process_factory
        ),
    ) -> None:
        self.adb = adb
        self.session = session
        self.package_name = package_name
        self.clock = clock
        self.process_factory = process_factory
        self.router_process_factory = router_process_factory

        self._preflight: HttpsInterceptionPreflight | None = None
        self._process: ProcessLike | None = None
        self._router_process: ProcessLike | None = None
        self._stderr: BinaryIO | None = None
        self._router_stderr: BinaryIO | None = None
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
        self._package_uid: int | None = None
        self._router_pid: int | None = None
        self._direct_routing_configured = False
        self._direct_routing_succeeded = False
        self._direct_route_stats = ""

    @property
    def running(self) -> bool:
        return (
            self._process is not None
            and self._router_process is not None
            and not self._finished
            and self._process.poll() is None
            and self._router_process.poll() is None
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
            self._package_uid = self.adb.get_package_uid(
                serial,
                self.package_name,
            )
            routing_probe = self._shell_script(
                "command -v ip >/dev/null 2>&1 "
                "&& command -v iptables >/dev/null 2>&1 "
                "&& command -v ip6tables >/dev/null 2>&1 "
                "&& iptables -t mangle -j TPROXY -h "
                ">/dev/null 2>&1 "
                "&& ip6tables -t mangle -j TPROXY -h "
                ">/dev/null 2>&1 "
                "&& echo ready || echo unavailable"
            ).strip()
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
        if routing_probe != "ready":
            raise HttpsInterceptionCollectorError(
                "Android direct HTTPS routing support is unavailable"
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
            (
                "http_direct_router_stderr",
                self.ROUTER_STDERR_ARTIFACT,
                True,
            ),
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
        router_stderr_path = (
            self.session.paths.root / self.ROUTER_STDERR_ARTIFACT
        )
        transactions_path.parent.mkdir(parents=True, exist_ok=True)
        bodies_dir.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        router_stderr_path.parent.mkdir(parents=True, exist_ok=True)
        transactions_path.touch(exist_ok=True)
        self._stderr = stderr_path.open("wb")
        self._router_stderr = router_stderr_path.open("wb")

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
            self._start_direct_router()
            self._configure_direct_routing()
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

        self._capture_direct_routing_stats_best_effort()
        self._cleanup_device_best_effort()
        if self._stderr is not None:
            self._stderr.close()
            self._stderr = None
        if self._router_stderr is not None:
            self._router_stderr.close()
            self._router_stderr = None
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

    def _start_direct_router(self) -> None:
        serial = self._serial
        jar = resolve_agent_jar()
        self.adb.make_remote_directory(
            serial,
            self.DIRECT_ROUTER_REMOTE_DIR,
        )
        self.adb.push_file(
            serial,
            jar,
            self.DIRECT_ROUTER_REMOTE_JAR,
            timeout=30.0,
        )
        if self._router_stderr is None:
            raise HttpsInterceptionCollectorError(
                "Direct HTTPS router diagnostics are unavailable"
            )
        command = [
            str(self.adb.adb_path),
            "-s",
            serial,
            "shell",
            f"CLASSPATH={self.DIRECT_ROUTER_REMOTE_JAR}",
            "app_process",
            "/",
            self.DIRECT_ROUTER_MAIN_CLASS,
            "--listen-port",
            str(self.DIRECT_ROUTER_PORT),
            "--listen-port-v6",
            str(self.DIRECT_ROUTER_PORT_V6),
            "--proxy-port",
            str(self.DEVICE_PROXY_PORT),
        ]
        self._router_process = self.router_process_factory(
            command,
            self._router_stderr,
        )
        stdout = getattr(
            self._router_process,
            "stdout",
            None,
        )
        if stdout is None:
            raise HttpsInterceptionCollectorError(
                "Direct HTTPS router has no startup channel"
            )

        holder: dict[str, bytes] = {}

        def read_banner() -> None:
            try:
                holder["line"] = stdout.readline()
            except Exception:
                holder["line"] = b""

        reader = threading.Thread(
            target=read_banner,
            daemon=True,
            name="apk-research-direct-https-router-start",
        )
        reader.start()
        reader.join(timeout=10.0)
        if reader.is_alive():
            raise HttpsInterceptionCollectorError(
                "Direct HTTPS router did not become ready within 10 seconds"
            )
        raw = holder.get("line", b"")
        if isinstance(raw, str):
            line = raw.strip()
        else:
            line = raw.decode(
                "utf-8",
                errors="replace",
            ).strip()
        parts = line.split()
        if (
            len(parts) != 4
            or parts[0] != "READY"
            or not parts[1].isdigit()
            or parts[2] != str(self.DIRECT_ROUTER_PORT)
            or parts[3] != str(self.DIRECT_ROUTER_PORT_V6)
        ):
            returncode = (
                self._router_process.poll()
                if self._router_process is not None
                else None
            )
            raise HttpsInterceptionCollectorError(
                "Direct HTTPS router startup failed: "
                f"{line!r}; exit={returncode!r}"
            )
        self._router_pid = int(parts[1])

    def _configure_direct_routing(self) -> None:
        if self._package_uid is None:
            raise HttpsInterceptionCollectorError(
                "Package UID is unavailable for direct HTTPS routing"
            )
        script = f"""
set -eu
IPT=iptables
IP6T=ip6tables
OUT={self.DIRECT_OUT_CHAIN}
PRE={self.DIRECT_PRE_CHAIN}
MARK={self.DIRECT_ROUTE_MARK}
MASK={self.DIRECT_ROUTE_MASK}
TABLE={self.DIRECT_ROUTE_TABLE}
PREF={self.DIRECT_ROUTE_PREF}
UID={self._package_uid}
PORT4={self.DIRECT_ROUTER_PORT}
PORT6={self.DIRECT_ROUTER_PORT_V6}

for TOOL in "$IPT" "$IP6T"; do
  while $TOOL -w 2 -t mangle -C OUTPUT -j "$OUT" >/dev/null 2>&1; do
    $TOOL -w 2 -t mangle -D OUTPUT -j "$OUT"
  done
  while $TOOL -w 2 -t mangle -C PREROUTING -j "$PRE" >/dev/null 2>&1; do
    $TOOL -w 2 -t mangle -D PREROUTING -j "$PRE"
  done
  $TOOL -w 2 -t mangle -F "$OUT" >/dev/null 2>&1 || true
  $TOOL -w 2 -t mangle -X "$OUT" >/dev/null 2>&1 || true
  $TOOL -w 2 -t mangle -F "$PRE" >/dev/null 2>&1 || true
  $TOOL -w 2 -t mangle -X "$PRE" >/dev/null 2>&1 || true
done
while ip rule del pref "$PREF" >/dev/null 2>&1; do :; done
while ip -6 rule del pref "$PREF" >/dev/null 2>&1; do :; done
ip route flush table "$TABLE" >/dev/null 2>&1 || true
ip -6 route flush table "$TABLE" >/dev/null 2>&1 || true

$IPT -w 2 -t mangle -N "$OUT"
$IPT -w 2 -t mangle -N "$PRE"
$IPT -w 2 -t mangle -A "$OUT" \
  -p tcp --dport 443 -m owner --uid-owner "$UID" \
  -j MARK --set-xmark "$MARK/$MASK"
$IPT -w 2 -t mangle -A "$PRE" \
  -p tcp --dport 443 -m mark --mark "$MARK/$MASK" \
  -j TPROXY --on-ip 127.0.0.1 --on-port "$PORT4" \
  --tproxy-mark "$MARK/$MASK"
$IPT -w 2 -t mangle -A OUTPUT -j "$OUT"
$IPT -w 2 -t mangle -A PREROUTING -j "$PRE"

$IP6T -w 2 -t mangle -N "$OUT"
$IP6T -w 2 -t mangle -N "$PRE"
$IP6T -w 2 -t mangle -A "$OUT" \
  -p tcp --dport 443 -m owner --uid-owner "$UID" \
  -j MARK --set-xmark "$MARK/$MASK"
$IP6T -w 2 -t mangle -A "$PRE" \
  -p tcp --dport 443 -m mark --mark "$MARK/$MASK" \
  -j TPROXY --on-ip ::1 --on-port "$PORT6" \
  --tproxy-mark "$MARK/$MASK"
$IP6T -w 2 -t mangle -A OUTPUT -j "$OUT"
$IP6T -w 2 -t mangle -A PREROUTING -j "$PRE"

ip route add local 0.0.0.0/0 dev lo table "$TABLE"
ip rule add pref "$PREF" fwmark "$MARK/$MASK" lookup "$TABLE"
ip -6 route add local ::/0 dev lo table "$TABLE"
ip -6 rule add pref "$PREF" fwmark "$MARK/$MASK" lookup "$TABLE"

$IPT -w 2 -t mangle -C OUTPUT -j "$OUT"
$IPT -w 2 -t mangle -C PREROUTING -j "$PRE"
$IP6T -w 2 -t mangle -C OUTPUT -j "$OUT"
$IP6T -w 2 -t mangle -C PREROUTING -j "$PRE"
"""
        self._shell_script(
            script,
            timeout=20.0,
        )
        self._direct_routing_configured = True
        self._direct_routing_succeeded = True

    def _capture_direct_routing_stats_best_effort(self) -> None:
        if not self._serial or not self._direct_routing_configured:
            return
        script = f"""
echo '=== ipv4-output ==='
iptables -w 2 -t mangle -nvx -L {self.DIRECT_OUT_CHAIN} 2>/dev/null || true
echo '=== ipv4-prerouting ==='
iptables -w 2 -t mangle -nvx -L {self.DIRECT_PRE_CHAIN} 2>/dev/null || true
echo '=== ipv6-output ==='
ip6tables -w 2 -t mangle -nvx -L {self.DIRECT_OUT_CHAIN} 2>/dev/null || true
echo '=== ipv6-prerouting ==='
ip6tables -w 2 -t mangle -nvx -L {self.DIRECT_PRE_CHAIN} 2>/dev/null || true
echo '=== ipv4-rule ==='
ip rule show pref {self.DIRECT_ROUTE_PREF} 2>/dev/null || true
echo '=== ipv6-rule ==='
ip -6 rule show pref {self.DIRECT_ROUTE_PREF} 2>/dev/null || true
"""
        try:
            self._direct_route_stats = self._shell_script(
                script,
                timeout=10.0,
            ).strip()
        except Exception:
            self._direct_route_stats = ""

    def _cleanup_direct_routing_best_effort(self) -> None:
        if not self._serial:
            return
        script = f"""
IPT=iptables
IP6T=ip6tables
OUT={self.DIRECT_OUT_CHAIN}
PRE={self.DIRECT_PRE_CHAIN}
TABLE={self.DIRECT_ROUTE_TABLE}
PREF={self.DIRECT_ROUTE_PREF}
for TOOL in "$IPT" "$IP6T"; do
  while $TOOL -w 2 -t mangle -C OUTPUT -j "$OUT" >/dev/null 2>&1; do
    $TOOL -w 2 -t mangle -D OUTPUT -j "$OUT" || break
  done
  while $TOOL -w 2 -t mangle -C PREROUTING -j "$PRE" >/dev/null 2>&1; do
    $TOOL -w 2 -t mangle -D PREROUTING -j "$PRE" || break
  done
  $TOOL -w 2 -t mangle -F "$OUT" >/dev/null 2>&1 || true
  $TOOL -w 2 -t mangle -X "$OUT" >/dev/null 2>&1 || true
  $TOOL -w 2 -t mangle -F "$PRE" >/dev/null 2>&1 || true
  $TOOL -w 2 -t mangle -X "$PRE" >/dev/null 2>&1 || true
done
while ip rule del pref "$PREF" >/dev/null 2>&1; do :; done
while ip -6 rule del pref "$PREF" >/dev/null 2>&1; do :; done
ip route flush table "$TABLE" >/dev/null 2>&1 || true
ip -6 route flush table "$TABLE" >/dev/null 2>&1 || true
"""
        try:
            self._shell_script(
                script,
                timeout=15.0,
            )
        except Exception:
            pass
        self._direct_routing_configured = False

    def _stop_direct_router_best_effort(self) -> None:
        process = self._router_process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2.0)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        self._router_process = None
        if self._serial:
            try:
                if self._router_pid is not None:
                    self.adb.shell_output(
                        self._serial,
                        "kill",
                        str(self._router_pid),
                    )
            except Exception:
                pass
            try:
                self._shell_script(
                    f"rm -rf {self.DIRECT_ROUTER_REMOTE_DIR}",
                    timeout=10.0,
                )
            except Exception:
                pass
        self._router_pid = None

    def _cleanup_device_best_effort(self) -> None:
        serial = self._serial
        if not serial:
            return
        self._cleanup_direct_routing_best_effort()
        self._stop_direct_router_best_effort()
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
        if self._router_stderr is not None:
            try:
                self._router_stderr.close()
            except Exception:
                pass
            self._router_stderr = None
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
                "direct_https_routing": {
                    "enabled": self._direct_routing_succeeded,
                    "active_at_metadata_write": (
                        self._direct_routing_configured
                    ),
                    "package_uid": self._package_uid,
                    "target_tcp_port": 443,
                    "router_port_ipv4": self.DIRECT_ROUTER_PORT,
                    "router_port_ipv6": self.DIRECT_ROUTER_PORT_V6,
                    "address_families": ["ipv4", "ipv6"],
                    "method": "tproxy-owner-mark-connect",
                    "original_destination_preserved": True,
                    "rule_stats": self._direct_route_stats or None,
                },
                "system_ca_injected": self._ca_injected,
                "system_ca_injection_succeeded": self._ca_injection_succeeded,
                "ca_sha256": self._ca_sha256 or None,
                "ca_subject_hash_old": self._ca_subject_hash or None,
                "http3_enabled": False,
                "active_interception": True,
                "passive_pcap_independent": True,
                "transport_intervention": {
                    "android_explicit_proxy_enabled": True,
                    "device_to_proxy_via_adb_reverse": True,
                    "target_package_tcp_443_forced_through_analyzer": (
                        self._direct_routing_succeeded
                    ),
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
