from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Protocol

from apk_research.targets import AdbClient, AdbError

PROTOCOL_VERSION = 1
AGENT_VERSION = "0.1.0"
AGENT_MAIN_CLASS = "com.lvlaksim1.apkresearch.sidecar.Agent"
REMOTE_DIR = "/data/local/tmp/apk-research/sidecar"
REMOTE_AGENT = (
    REMOTE_DIR
    + "/apk-research-agent-"
    + AGENT_VERSION
    + ".jar"
)
_MAX_PROTOCOL_LINE = 4096
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class SidecarError(RuntimeError):
    """Raised when the temporary Android sidecar cannot satisfy its contract."""


class ProcessLike(Protocol):
    returncode: int | None

    def poll(self) -> int | None: ...
    def wait(self, timeout: float | None = None) -> int: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...


ProcessFactory = Callable[
    [list[str]],
    ProcessLike,
]


@dataclass(frozen=True)
class SidecarHandshake:
    protocol_version: int
    agent_version: str
    transport: str
    host_port: int
    device_port: int
    remote_agent: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SidecarPing:
    token: str
    agent_uptime_ms: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SidecarCleanup:
    graceful_protocol_stop: bool
    process_exit_code: int | None
    reverse_removed: bool
    remote_agent_removed: bool

    @property
    def complete(self) -> bool:
        return (
            self.graceful_protocol_stop
            and self.process_exit_code == 0
            and self.reverse_removed
            and self.remote_agent_removed
        )

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "complete": self.complete,
        }


def resolve_agent_jar(
    explicit_path: str | os.PathLike[str] | None = None,
) -> Path:
    if explicit_path is not None:
        candidate = Path(explicit_path)
    else:
        configured = os.environ.get("APK_RESEARCH_AGENT_JAR")
        if configured:
            candidate = Path(configured)
        elif getattr(sys, "frozen", False):
            root = Path(getattr(sys, "_MEIPASS"))
            candidate = (
                root
                / "apk_research"
                / "resources"
                / "apk-research-agent.jar"
            )
        else:
            candidate = (
                Path(__file__).resolve().parents[3]
                / "build"
                / "android-sidecar"
                / "apk-research-agent.jar"
            )

    candidate = candidate.expanduser().resolve()
    if not candidate.is_file():
        raise SidecarError(
            "Android sidecar agent is missing: "
            + str(candidate)
        )
    return candidate


def parse_agent_banner(line: str) -> tuple[int, str]:
    parts = line.strip().split()
    if (
        len(parts) != 3
        or parts[0] != "APK_RESEARCH_AGENT"
    ):
        raise SidecarError(
            "Invalid Android sidecar banner"
        )
    try:
        protocol = int(parts[1])
    except ValueError as exc:
        raise SidecarError(
            "Invalid Android sidecar protocol version"
        ) from exc
    return protocol, parts[2]


def parse_ready(line: str) -> tuple[int, str]:
    parts = line.strip().split()
    if len(parts) != 3 or parts[0] != "READY":
        raise SidecarError(
            "Android sidecar did not acknowledge handshake"
        )
    try:
        protocol = int(parts[1])
    except ValueError as exc:
        raise SidecarError(
            "Invalid Android sidecar READY protocol"
        ) from exc
    return protocol, parts[2]


def parse_pong(
    line: str,
    *,
    expected_token: str,
) -> SidecarPing:
    parts = line.strip().split()
    if (
        len(parts) != 3
        or parts[0] != "PONG"
        or parts[1] != expected_token
    ):
        raise SidecarError(
            "Invalid Android sidecar PONG"
        )
    try:
        uptime = int(parts[2])
    except ValueError as exc:
        raise SidecarError(
            "Invalid Android sidecar uptime"
        ) from exc
    if uptime < 0:
        raise SidecarError(
            "Invalid Android sidecar uptime"
        )
    return SidecarPing(
        token=parts[1],
        agent_uptime_ms=uptime,
    )


def _default_process_factory(
    command: list[str],
) -> ProcessLike:
    creation_flags = getattr(
        subprocess,
        "CREATE_NO_WINDOW",
        0,
    )
    return subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creation_flags,
    )


class AndroidSidecar:
    """Bounded temporary app_process sidecar for the managed Android target."""

    def __init__(
        self,
        adb: AdbClient,
        serial: str,
        *,
        agent_jar: str | os.PathLike[str] | None = None,
        timeout: float = 8.0,
        process_factory: ProcessFactory = _default_process_factory,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.adb = adb
        self.serial = str(serial)
        self.agent_jar = resolve_agent_jar(agent_jar)
        self.timeout = float(timeout)
        self.process_factory = process_factory

        self._listener: socket.socket | None = None
        self._connection: socket.socket | None = None
        self._process: ProcessLike | None = None
        self._lock = threading.Lock()
        self._started = False
        self._reverse_port: int | None = None
        self._receive_buffer = bytearray()
        self._last_cleanup: SidecarCleanup | None = None

    @property
    def last_cleanup(self) -> SidecarCleanup | None:
        return self._last_cleanup

    @property
    def running(self) -> bool:
        return (
            self._started
            and self._connection is not None
            and self._process is not None
            and self._process.poll() is None
        )

    def __enter__(self) -> "AndroidSidecar":
        self.start()
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        self.stop()

    def start(self) -> SidecarHandshake:
        with self._lock:
            if self._started:
                raise SidecarError(
                    "Android sidecar is already started"
                )
            self._started = True

        try:
            self.adb.ensure_ready(self.serial)
            self.adb.make_remote_directory(
                self.serial,
                REMOTE_DIR,
            )
            self.adb.push_file(
                self.serial,
                self.agent_jar,
                REMOTE_AGENT,
            )

            listener = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM,
            )
            listener.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1,
            )
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(self.timeout)
            self._listener = listener

            host_port = int(
                listener.getsockname()[1]
            )
            device_port = host_port
            self.adb.reverse_tcp(
                self.serial,
                device_port=device_port,
                host_port=host_port,
            )
            self._reverse_port = device_port

            command = [
                str(self.adb.adb_path),
                "-s",
                self.serial,
                "shell",
                f"CLASSPATH={REMOTE_AGENT}",
                "app_process",
                "/",
                AGENT_MAIN_CLASS,
                "--port",
                str(device_port),
            ]
            self._process = self.process_factory(command)

            try:
                connection, _ = listener.accept()
            except socket.timeout as exc:
                raise SidecarError(
                    "Android sidecar did not connect before timeout"
                ) from exc
            connection.settimeout(self.timeout)
            connection.setsockopt(
                socket.IPPROTO_TCP,
                socket.TCP_NODELAY,
                1,
            )
            self._connection = connection

            protocol, version = parse_agent_banner(
                self._read_line()
            )
            if (
                protocol != PROTOCOL_VERSION
                or version != AGENT_VERSION
            ):
                raise SidecarError(
                    "Android sidecar version mismatch: "
                    f"protocol={protocol}, agent={version}; "
                    f"expected protocol={PROTOCOL_VERSION}, "
                    f"agent={AGENT_VERSION}"
                )

            self._write_line(
                f"HELLO {PROTOCOL_VERSION} {AGENT_VERSION}"
            )
            ready_protocol, ready_version = parse_ready(
                self._read_line()
            )
            if (
                ready_protocol != PROTOCOL_VERSION
                or ready_version != AGENT_VERSION
            ):
                raise SidecarError(
                    "Android sidecar READY version mismatch"
                )

            return SidecarHandshake(
                protocol_version=protocol,
                agent_version=version,
                transport="adb-reverse-tcp",
                host_port=host_port,
                device_port=device_port,
                remote_agent=REMOTE_AGENT,
            )
        except Exception:
            self._cleanup(
                graceful=False,
                suppress_errors=True,
            )
            raise

    def ping(
        self,
        token: str = "ping",
    ) -> SidecarPing:
        if not _TOKEN_RE.fullmatch(token):
            raise ValueError(
                "token must contain only letters, digits, '.', '_' or '-'"
            )
        if not self.running:
            raise SidecarError(
                "Android sidecar is not running"
            )
        self._write_line(f"PING {token}")
        return parse_pong(
            self._read_line(),
            expected_token=token,
        )

    def stop(self) -> SidecarCleanup:
        return self._cleanup(
            graceful=True,
            suppress_errors=False,
        )

    def _cleanup(
        self,
        *,
        graceful: bool,
        suppress_errors: bool,
    ) -> SidecarCleanup:
        graceful_protocol_stop = False
        process_exit_code: int | None = None
        reverse_removed = self._reverse_port is None
        remote_removed = False
        errors: list[Exception] = []

        connection = self._connection
        if graceful and connection is not None:
            try:
                self._write_line("STOP")
                graceful_protocol_stop = (
                    self._read_line() == "BYE"
                )
            except Exception as exc:
                errors.append(exc)

        if connection is not None:
            try:
                connection.close()
            except OSError as exc:
                errors.append(exc)
            self._connection = None

        listener = self._listener
        if listener is not None:
            try:
                listener.close()
            except OSError as exc:
                errors.append(exc)
            self._listener = None

        process = self._process
        if process is not None:
            try:
                process_exit_code = process.wait(
                    timeout=3.0
                )
            except Exception:
                try:
                    process.terminate()
                    process_exit_code = process.wait(
                        timeout=2.0
                    )
                except Exception:
                    try:
                        process.kill()
                        process_exit_code = process.wait(
                            timeout=2.0
                        )
                    except Exception as exc:
                        errors.append(exc)
            self._process = None

        if self._reverse_port is not None:
            try:
                self.adb.remove_reverse_tcp(
                    self.serial,
                    self._reverse_port,
                )
                reverse_removed = True
            except Exception as exc:
                errors.append(exc)
            self._reverse_port = None

        try:
            self.adb.remove_remote_file(
                self.serial,
                REMOTE_AGENT,
            )
            remote_removed = True
        except Exception as exc:
            errors.append(exc)

        with self._lock:
            self._started = False

        cleanup = SidecarCleanup(
            graceful_protocol_stop=graceful_protocol_stop,
            process_exit_code=process_exit_code,
            reverse_removed=reverse_removed,
            remote_agent_removed=remote_removed,
        )
        self._last_cleanup = cleanup

        if errors and not suppress_errors:
            detail = "; ".join(
                str(exc) or exc.__class__.__name__
                for exc in errors
            )
            raise SidecarError(
                "Android sidecar cleanup failed: "
                + detail
            )
        return cleanup

    def _write_line(self, value: str) -> None:
        connection = self._connection
        if connection is None:
            raise SidecarError(
                "Android sidecar socket is not connected"
            )
        try:
            connection.sendall(
                value.encode("utf-8") + b"\n"
            )
        except OSError as exc:
            raise SidecarError(
                "Unable to write Android sidecar protocol"
            ) from exc

    def _read_line(self) -> str:
        connection = self._connection
        if connection is None:
            raise SidecarError(
                "Android sidecar socket is not connected"
            )

        while True:
            newline = self._receive_buffer.find(b"\n")
            if newline >= 0:
                raw = bytes(
                    self._receive_buffer[:newline]
                )
                del self._receive_buffer[: newline + 1]
                try:
                    return raw.rstrip(b"\r").decode(
                        "utf-8",
                        errors="strict",
                    )
                except UnicodeDecodeError as exc:
                    raise SidecarError(
                        "Android sidecar sent invalid UTF-8"
                    ) from exc

            if len(self._receive_buffer) > _MAX_PROTOCOL_LINE:
                raise SidecarError(
                    "Android sidecar protocol line exceeds safety bound"
                )

            try:
                chunk = connection.recv(1024)
            except OSError as exc:
                raise SidecarError(
                    "Unable to read Android sidecar protocol"
                ) from exc
            if not chunk:
                raise SidecarError(
                    "Android sidecar closed the protocol socket"
                )
            self._receive_buffer.extend(chunk)
