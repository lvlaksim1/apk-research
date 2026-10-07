from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes

from apk_research.session import SessionManager
from apk_research.targets import AdbClient


HTTPS_TRANSACTIONS_ARTIFACT = "02_normalized/http-transactions.jsonl"
HTTPS_INTERCEPTION_ARTIFACT = "02_normalized/https-interception.json"
DEFAULT_DEVICE_PROXY_PORT = 38080


class HttpsInterceptCollectorError(RuntimeError):
    """Raised when the managed HTTPS interception path cannot start or stop."""


@dataclass(frozen=True)
class HttpsInterceptResult:
    transactions: int
    request_bytes: int
    response_bytes: int
    proxy_host_port: int
    proxy_device_port: int
    ca_subject_hash_old: str
    ca_fingerprint_sha256: str
    restored_proxy: str

    def to_dict(self) -> dict[str, object]:
        return {
            "transactions": self.transactions,
            "request_bytes": self.request_bytes,
            "response_bytes": self.response_bytes,
            "proxy_host_port": self.proxy_host_port,
            "proxy_device_port": self.proxy_device_port,
            "ca_subject_hash_old": self.ca_subject_hash_old,
            "ca_fingerprint_sha256": self.ca_fingerprint_sha256,
            "restored_proxy": self.restored_proxy,
        }


def default_https_proxy_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "apk-research" / "https-proxy"
    return Path.home() / ".apk-research" / "https-proxy"


def _iso_from_epoch(value: float | None) -> str | None:
    if value is None:
        return None
    return (
        datetime.fromtimestamp(float(value), tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _headers_list(headers: Any) -> list[list[str]]:
    try:
        items = headers.items(multi=True)
    except TypeError:
        items = headers.items()
    except AttributeError:
        return []
    return [[str(name), str(value)] for name, value in items]


def _body_value(data: bytes | bytearray | memoryview | None) -> dict[str, object]:
    if data is None:
        raw = b""
    else:
        raw = bytes(data)
    return {
        "size": len(raw),
        "base64": base64.b64encode(raw).decode("ascii"),
    }


def android_subject_hash_old(certificate: x509.Certificate) -> str:
    """Return the legacy OpenSSL subject hash used by Android CA filenames."""

    subject_der = certificate.subject.public_bytes()
    try:
        digest = hashlib.md5(
            subject_der,
            usedforsecurity=False,
        ).digest()
    except TypeError:
        digest = hashlib.md5(subject_der).digest()
    return f"{int.from_bytes(digest[:4], 'little'):08x}"


def _certificate_details(path: Path) -> tuple[str, str]:
    certificate = x509.load_pem_x509_certificate(path.read_bytes())
    return (
        android_subject_hash_old(certificate),
        certificate.fingerprint(hashes.SHA256()).hex(),
    )


def _allocate_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class _TransactionAddon:
    def __init__(
        self,
        output_path: Path,
        ready: threading.Event,
    ) -> None:
        self.output_path = output_path
        self.ready = ready
        self._lock = threading.Lock()
        self._sequence = 0
        self._recorded: set[str] = set()
        self.transactions = 0
        self.request_bytes = 0
        self.response_bytes = 0

    def running(self) -> None:
        self.ready.set()

    def response(self, flow: Any) -> None:
        self._record(flow, error=None)

    def error(self, flow: Any) -> None:
        message = ""
        flow_error = getattr(flow, "error", None)
        if flow_error is not None:
            message = str(getattr(flow_error, "msg", None) or flow_error)
        self._record(flow, error=message or "proxy-flow-error")

    def _record(self, flow: Any, *, error: str | None) -> None:
        request = getattr(flow, "request", None)
        if request is None:
            return

        flow_id = str(getattr(flow, "id", "") or "")
        if flow_id and flow_id in self._recorded:
            return

        request_body = bytes(getattr(request, "raw_content", None) or b"")
        response = getattr(flow, "response", None)
        response_body = (
            bytes(getattr(response, "raw_content", None) or b"")
            if response is not None
            else b""
        )

        with self._lock:
            self._sequence += 1
            transaction_id = f"http-{self._sequence:06d}"
            value: dict[str, object] = {
                "schema_version": "0.1",
                "transaction_id": transaction_id,
                "capture_mode": "active-explicit-proxy",
                "intervention": True,
                "flow_id": flow_id or None,
                "request_started_utc": _iso_from_epoch(
                    getattr(request, "timestamp_start", None)
                ),
                "request_ended_utc": _iso_from_epoch(
                    getattr(request, "timestamp_end", None)
                ),
                "url": str(
                    getattr(request, "pretty_url", None)
                    or getattr(request, "url", "")
                    or ""
                ),
                "scheme": str(getattr(request, "scheme", "") or ""),
                "host": str(
                    getattr(request, "pretty_host", None)
                    or getattr(request, "host", "")
                    or ""
                ),
                "port": int(getattr(request, "port", 0) or 0),
                "method": str(getattr(request, "method", "") or ""),
                "path": str(getattr(request, "path", "") or ""),
                "http_version": str(
                    getattr(request, "http_version", "") or ""
                ),
                "request_headers": _headers_list(
                    getattr(request, "headers", None)
                ),
                "request_body": _body_value(request_body),
                "response": None,
                "error": error,
            }

            client_conn = getattr(flow, "client_conn", None)
            server_conn = getattr(flow, "server_conn", None)
            value["tls"] = {
                "client_tls_version": str(
                    getattr(client_conn, "tls_version", "") or ""
                ),
                "client_cipher": str(
                    getattr(client_conn, "cipher", "") or ""
                ),
                "server_tls_version": str(
                    getattr(server_conn, "tls_version", "") or ""
                ),
                "server_cipher": str(
                    getattr(server_conn, "cipher", "") or ""
                ),
                "server_sni": str(
                    getattr(server_conn, "sni", "") or ""
                ),
            }

            if response is not None:
                value["response"] = {
                    "started_utc": _iso_from_epoch(
                        getattr(response, "timestamp_start", None)
                    ),
                    "ended_utc": _iso_from_epoch(
                        getattr(response, "timestamp_end", None)
                    ),
                    "status_code": int(
                        getattr(response, "status_code", 0) or 0
                    ),
                    "reason": str(
                        getattr(response, "reason", "") or ""
                    ),
                    "http_version": str(
                        getattr(response, "http_version", "") or ""
                    ),
                    "headers": _headers_list(
                        getattr(response, "headers", None)
                    ),
                    "body": _body_value(response_body),
                }

            with self.output_path.open(
                "a",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            if flow_id:
                self._recorded.add(flow_id)
            self.transactions += 1
            self.request_bytes += len(request_body)
            self.response_bytes += len(response_body)


class HttpsInterceptCollector:
    """Managed mitmproxy + Android trust/proxy setup for one research session."""

    def __init__(
        self,
        adb: AdbClient,
        session: SessionManager,
        serial: str,
        package_name: str,
        *,
        proxy_root: str | os.PathLike[str] | None = None,
        device_port: int = DEFAULT_DEVICE_PROXY_PORT,
        host_port: int | None = None,
    ) -> None:
        self.adb = adb
        self.session = session
        self.serial = serial
        self.package_name = package_name
        self.proxy_root = (
            Path(proxy_root)
            if proxy_root is not None
            else default_https_proxy_root()
        ).expanduser().resolve()
        self.device_port = int(device_port)
        self.host_port = int(host_port or _allocate_loopback_port())

        self.transactions_path = (
            self.session.paths.root / HTTPS_TRANSACTIONS_ARTIFACT
        )
        self.state_path = (
            self.session.paths.root / HTTPS_INTERCEPTION_ARTIFACT
        )
        self.confdir = self.proxy_root / "mitmproxy"
        self.ca_path = self.confdir / "mitmproxy-ca-cert.cer"

        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._master: Any = None
        self._addon: _TransactionAddon | None = None
        self._thread_error: BaseException | None = None
        self._started = False
        self._previous_proxy = ""
        self._ca_subject_hash_old = ""
        self._ca_fingerprint_sha256 = ""
        self._sdk_level: int | None = None
        self._trust_method = ""

    def start(self) -> None:
        if self._started:
            raise HttpsInterceptCollectorError(
                "HTTPS interception collector is already started"
            )

        self.proxy_root.mkdir(parents=True, exist_ok=True)
        self.confdir.mkdir(parents=True, exist_ok=True)
        self.transactions_path.parent.mkdir(parents=True, exist_ok=True)
        self.transactions_path.touch(exist_ok=True)

        self._thread = threading.Thread(
            target=self._proxy_thread_main,
            name="apk-research-https-proxy",
            daemon=True,
        )
        self._thread.start()

        if not self._ready.wait(20.0):
            self._shutdown_proxy()
            raise HttpsInterceptCollectorError(
                "HTTPS proxy did not become ready within 20 seconds"
            )
        if self._thread_error is not None:
            raise HttpsInterceptCollectorError(
                "HTTPS proxy failed to start: "
                + (
                    str(self._thread_error)
                    or self._thread_error.__class__.__name__
                )
            )

        deadline = time.monotonic() + 10.0
        while not self.ca_path.is_file() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not self.ca_path.is_file():
            self._shutdown_proxy()
            raise HttpsInterceptCollectorError(
                "mitmproxy did not create its CA certificate"
            )

        (
            self._ca_subject_hash_old,
            self._ca_fingerprint_sha256,
        ) = _certificate_details(self.ca_path)

        details = self.adb.get_target_details(self.serial)
        self._sdk_level = details.sdk_level
        if not details.is_root:
            self._shutdown_proxy()
            raise HttpsInterceptCollectorError(
                "Managed HTTPS interception requires the rooted research emulator"
            )

        try:
            self._install_system_ca()
            self._configure_android_proxy()
        except Exception:
            self._restore_android_proxy(best_effort=True)
            self._shutdown_proxy()
            raise

        self._write_state(
            status="active",
            restored_proxy=None,
        )
        self.session.register_artifact(
            kind="https_interception",
            relative_path=HTTPS_INTERCEPTION_ARTIFACT,
            source="https-intercept",
            raw=False,
        )
        self.session.register_artifact(
            kind="http_transactions",
            relative_path=HTTPS_TRANSACTIONS_ARTIFACT,
            source="https-intercept",
            raw=False,
        )
        self._started = True

    def check_health(self) -> bool:
        thread = self._thread
        return bool(
            self._started
            and thread is not None
            and thread.is_alive()
            and self._thread_error is None
        )

    def stop(
        self,
        grace_period: float = 3.0,
    ) -> HttpsInterceptResult:
        restored = self._restore_android_proxy(
            best_effort=False
        )
        self._shutdown_proxy(
            grace_period=max(1.0, float(grace_period))
        )

        addon = self._addon
        result = HttpsInterceptResult(
            transactions=(
                addon.transactions if addon is not None else 0
            ),
            request_bytes=(
                addon.request_bytes if addon is not None else 0
            ),
            response_bytes=(
                addon.response_bytes if addon is not None else 0
            ),
            proxy_host_port=self.host_port,
            proxy_device_port=self.device_port,
            ca_subject_hash_old=self._ca_subject_hash_old,
            ca_fingerprint_sha256=self._ca_fingerprint_sha256,
            restored_proxy=restored,
        )
        self._write_state(
            status="stopped",
            restored_proxy=restored,
            result=result.to_dict(),
        )
        self._started = False
        return result

    def _proxy_thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self._run_proxy()
            )
        except BaseException as exc:
            self._thread_error = exc
            self._ready.set()
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(
                            *pending,
                            return_exceptions=True,
                        )
                    )
            except Exception:
                pass
            loop.close()

    async def _run_proxy(self) -> None:
        try:
            from mitmproxy import options
            from mitmproxy.tools.dump import DumpMaster
        except Exception as exc:
            raise HttpsInterceptCollectorError(
                "mitmproxy runtime is unavailable"
            ) from exc

        opts = options.Options(
            listen_host="127.0.0.1",
            listen_port=self.host_port,
            http2=True,
            confdir=str(self.confdir),
        )
        master = DumpMaster(
            opts,
            loop=asyncio.get_running_loop(),
            with_termlog=False,
            with_dumper=False,
        )
        addon = _TransactionAddon(
            self.transactions_path,
            self._ready,
        )
        master.addons.add(addon)
        self._master = master
        self._addon = addon
        await master.run()

    def _shutdown_proxy(
        self,
        *,
        grace_period: float = 5.0,
    ) -> None:
        loop = self._loop
        master = self._master
        if loop is not None and master is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(master.shutdown)
            except Exception:
                pass
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=grace_period)
        if thread is not None and thread.is_alive():
            raise HttpsInterceptCollectorError(
                "HTTPS proxy did not stop cleanly"
            )

    def _configure_android_proxy(self) -> None:
        self._previous_proxy = (
            self.adb.shell_output(
                self.serial,
                "settings",
                "get",
                "global",
                "http_proxy",
            ).strip()
        )
        self.adb.reverse_tcp(
            self.serial,
            device_port=self.device_port,
            host_port=self.host_port,
        )
        self.adb.shell_output(
            self.serial,
            "settings",
            "put",
            "global",
            "http_proxy",
            f"127.0.0.1:{self.device_port}",
        )
        observed = (
            self.adb.shell_output(
                self.serial,
                "settings",
                "get",
                "global",
                "http_proxy",
            ).strip()
        )
        expected = f"127.0.0.1:{self.device_port}"
        if observed != expected:
            raise HttpsInterceptCollectorError(
                "Android global proxy setting was not applied "
                f"(expected {expected!r}, observed {observed!r})"
            )

    def _restore_android_proxy(
        self,
        *,
        best_effort: bool,
    ) -> str:
        target = self._previous_proxy.strip()
        if target.lower() in {"", "null", ":0"}:
            target = ":0"
        errors: list[str] = []
        try:
            self.adb.shell_output(
                self.serial,
                "settings",
                "put",
                "global",
                "http_proxy",
                target,
            )
        except Exception as exc:
            errors.append(str(exc) or exc.__class__.__name__)
        try:
            self.adb.remove_reverse_tcp(
                self.serial,
                self.device_port,
            )
        except Exception as exc:
            errors.append(str(exc) or exc.__class__.__name__)

        if errors and not best_effort:
            raise HttpsInterceptCollectorError(
                "Unable to restore Android proxy state: "
                + "; ".join(errors)
            )
        return target

    def _install_system_ca(self) -> None:
        cert_name = f"{self._ca_subject_hash_old}.0"
        remote_root = "/data/local/tmp/apk-research/https-ca"
        remote_cert = f"{remote_root}/{cert_name}"
        self.adb.shell_output(
            self.serial,
            "mkdir",
            "-p",
            remote_root,
        )

        local_hashed = self.proxy_root / cert_name
        local_hashed.write_bytes(self.ca_path.read_bytes())
        try:
            self.adb.push_file(
                self.serial,
                local_hashed,
                remote_cert,
                timeout=60.0,
            )
        finally:
            try:
                local_hashed.unlink()
            except OSError:
                pass

        sdk = int(self._sdk_level or 0)
        apex_path = "/apex/com.android.conscrypt/cacerts"
        system_path = "/system/etc/security/cacerts"
        if sdk >= 34:
            source_path = apex_path
            self._trust_method = (
                "root-tmpfs-system-ca+zygote-apex-bind"
            )
        else:
            source_path = system_path
            self._trust_method = "root-tmpfs-system-ca"

        work = "/data/local/tmp/apk-research/https-ca-overlay"
        setup = f"""
set -e
CERT='{remote_cert}'
NAME='{cert_name}'
SOURCE='{source_path}'
SYSTEM='{system_path}'
WORK='{work}'
mkdir -p "$WORK/original"
if [ ! -f "$SYSTEM/$NAME" ]; then
  rm -f "$WORK/original"/*
  cp "$SOURCE"/* "$WORK/original"/
  mount -t tmpfs tmpfs "$SYSTEM"
  cp "$WORK/original"/* "$SYSTEM"/
  cp "$CERT" "$SYSTEM/$NAME"
fi
chown root:root "$SYSTEM"/*
chmod 644 "$SYSTEM"/*
chcon u:object_r:system_file:s0 "$SYSTEM" 2>/dev/null || true
chcon u:object_r:system_file:s0 "$SYSTEM"/* 2>/dev/null || true
test -f "$SYSTEM/$NAME"
"""
        self.adb.shell_output(
            self.serial,
            "sh",
            "-c",
            setup,
            timeout=30.0,
        )

        if sdk >= 34:
            rebind = (
                "for i in 1 2 3 4 5; do "
                f"umount -l {apex_path} 2>/dev/null || break; "
                "done; "
                f"mount --bind {system_path} {apex_path}"
            )
            bind_script = f"""
set -e
REBIND='{rebind}'
/bin/sh -c "$REBIND"
for Z in $(pidof zygote 2>/dev/null || true) $(pidof zygote64 2>/dev/null || true); do
  [ -n "$Z" ] || continue
  nsenter --mount=/proc/$Z/ns/mnt -- /bin/sh -c "$REBIND"
done
for P in $(pidof '{self.package_name}' 2>/dev/null || true); do
  [ -n "$P" ] || continue
  nsenter --mount=/proc/$P/ns/mnt -- /bin/sh -c "$REBIND"
done
test -f {apex_path}/{cert_name}
"""
            self.adb.shell_output(
                self.serial,
                "sh",
                "-c",
                bind_script,
                timeout=30.0,
            )

    def _write_state(
        self,
        *,
        status: str,
        restored_proxy: str | None,
        result: dict[str, object] | None = None,
    ) -> None:
        value: dict[str, object] = {
            "schema_version": "0.1",
            "status": status,
            "capture_mode": "active-explicit-proxy",
            "intervention": True,
            "scope": "managed-emulator-global-http-proxy",
            "target_package": self.package_name,
            "serial": self.serial,
            "proxy": {
                "device": f"127.0.0.1:{self.device_port}",
                "host": f"127.0.0.1:{self.host_port}",
                "adb_reverse": True,
                "previous": self._previous_proxy or None,
                "restored": restored_proxy,
            },
            "ca": {
                "subject_hash_old": self._ca_subject_hash_old,
                "fingerprint_sha256": self._ca_fingerprint_sha256,
                "trust_method": self._trust_method,
                "private_key_archived": False,
            },
            "android_sdk": self._sdk_level,
            "evidence_semantics": {
                "raw_pcap_remains_authoritative_for_observed_packets": True,
                "http_transactions_are_active_interception_evidence": True,
                "transaction_package_ownership_proven": False,
                "global_proxy_may_change_transport_selection": True,
                "quic_may_fallback_to_tcp": True,
                "certificate_pinning_may_block_decryption": True,
            },
        }
        if result is not None:
            value["result"] = result

        temporary = self.state_path.with_suffix(
            self.state_path.suffix + ".tmp"
        )
        with temporary.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
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
        os.replace(temporary, self.state_path)
