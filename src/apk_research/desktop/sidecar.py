from __future__ import annotations

import os
import re
import socket
import struct
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Protocol

from apk_research.targets import AdbClient

PROTOCOL_VERSION = 2
AGENT_VERSION = "0.2.0"
AGENT_MAIN_CLASS = "com.lvlaksim1.apkresearch.sidecar.Agent"
REMOTE_DIR = "/data/local/tmp/apk-research/sidecar"
REMOTE_AGENT = (
    REMOTE_DIR
    + "/apk-research-agent-"
    + AGENT_VERSION
    + ".jar"
)

SCREEN_STREAM_MAGIC = b"APKRSCRN"
SCREEN_STREAM_VERSION = 1
_SCREEN_STREAM_HEADER = struct.Struct("!8sIIIIQ")
_SCREEN_PACKET_HEADER = struct.Struct("!IqI")
_MAX_PROTOCOL_LINE = 4096
_MAX_SCREEN_PACKET = 16 * 1024 * 1024
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
class SidecarScreenInfo:
    stream_version: int
    codec: str
    width: int
    height: int
    bit_rate: int
    agent_elapsed_start_ns: int
    transport: str
    host_port: int
    device_port: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SidecarScreenPacket:
    sequence: int
    flags: int
    pts_us: int
    payload: bytes

    @property
    def size(self) -> int:
        return len(self.payload)

    @property
    def codec_config(self) -> bool:
        return bool(self.flags & 2)

    @property
    def key_frame(self) -> bool:
        return bool(self.flags & 1)

    @property
    def end_of_stream(self) -> bool:
        return bool(self.flags & 4)


@dataclass(frozen=True)
class SidecarScreenStop:
    packet_count: int
    byte_count: int
    first_pts_us: int
    last_pts_us: int

    @property
    def presentation_span_seconds(self) -> float:
        if self.first_pts_us < 0 or self.last_pts_us < self.first_pts_us:
            return 0.0
        return (
            self.last_pts_us - self.first_pts_us
        ) / 1_000_000

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "presentation_span_seconds": self.presentation_span_seconds,
        }


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


class SidecarScreenStream:
    """Binary MediaCodec stream on a dedicated adb-reverse socket."""

    def __init__(
        self,
        connection: socket.socket,
        info: SidecarScreenInfo,
    ) -> None:
        self._connection = connection
        self.info = info
        self._sequence = 0
        self._closed = False

    def read_packet(self) -> SidecarScreenPacket | None:
        if self._closed:
            return None
        header = _recv_exact(
            self._connection,
            _SCREEN_PACKET_HEADER.size,
            allow_eof=True,
        )
        if header is None:
            self._closed = True
            return None

        flags, pts_us, size = _SCREEN_PACKET_HEADER.unpack(
            header
        )
        if size > _MAX_SCREEN_PACKET:
            raise SidecarError(
                "Android sidecar screen packet exceeds safety bound"
            )
        payload = (
            _recv_exact(
                self._connection,
                size,
                allow_eof=False,
            )
            if size
            else b""
        )
        assert payload is not None

        self._sequence += 1
        return SidecarScreenPacket(
            sequence=self._sequence,
            flags=int(flags),
            pts_us=int(pts_us),
            payload=payload,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._connection.close()
        except OSError:
            pass


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


def parse_screen_started(
    line: str,
    *,
    expected_width: int,
    expected_height: int,
) -> tuple[int, int, str]:
    parts = line.strip().split()
    if len(parts) != 4 or parts[0] != "SCREEN_STARTED":
        raise SidecarError(
            "Android sidecar did not start screen stream"
        )
    try:
        width = int(parts[1])
        height = int(parts[2])
    except ValueError as exc:
        raise SidecarError(
            "Invalid Android sidecar screen geometry"
        ) from exc
    codec = parts[3].lower()
    if (
        width != expected_width
        or height != expected_height
        or codec != "h264"
    ):
        raise SidecarError(
            "Android sidecar screen stream parameters mismatch"
        )
    return width, height, codec


def parse_screen_stopped(line: str) -> SidecarScreenStop:
    parts = line.strip().split()
    if len(parts) != 5 or parts[0] != "SCREEN_STOPPED":
        raise SidecarError(
            "Android sidecar did not stop screen stream cleanly"
        )
    try:
        values = [int(value) for value in parts[1:]]
    except ValueError as exc:
        raise SidecarError(
            "Invalid Android sidecar screen stop statistics"
        ) from exc
    packet_count, byte_count, first_pts_us, last_pts_us = values
    if packet_count < 0 or byte_count < 0:
        raise SidecarError(
            "Invalid Android sidecar screen stop statistics"
        )
    return SidecarScreenStop(
        packet_count=packet_count,
        byte_count=byte_count,
        first_pts_us=first_pts_us,
        last_pts_us=last_pts_us,
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


def _recv_exact(
    connection: socket.socket,
    size: int,
    *,
    allow_eof: bool,
) -> bytes | None:
    if size == 0:
        return b""
    value = bytearray()
    while len(value) < size:
        try:
            chunk = connection.recv(size - len(value))
        except OSError as exc:
            raise SidecarError(
                "Unable to read Android sidecar media stream"
            ) from exc
        if not chunk:
            if allow_eof and not value:
                return None
            raise SidecarError(
                "Android sidecar media stream ended mid-record"
            )
        value.extend(chunk)
    return bytes(value)


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

        self._screen_listener: socket.socket | None = None
        self._screen_stream: SidecarScreenStream | None = None
        self._screen_reverse_port: int | None = None

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

    @property
    def screen_running(self) -> bool:
        return self._screen_stream is not None

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

    def start_screen_stream(
        self,
        *,
        width: int = 540,
        height: int = 960,
        bit_rate: int = 2_000_000,
    ) -> SidecarScreenStream:
        if not self.running:
            raise SidecarError(
                "Android sidecar is not running"
            )
        if self._screen_stream is not None:
            raise SidecarError(
                "Android sidecar screen stream is already running"
            )
        if not 64 <= int(width) <= 4096:
            raise ValueError("screen width must be between 64 and 4096")
        if not 64 <= int(height) <= 4096:
            raise ValueError("screen height must be between 64 and 4096")
        if not 100_000 <= int(bit_rate) <= 50_000_000:
            raise ValueError(
                "screen bit rate must be between 100000 and 50000000"
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
        self._screen_listener = listener

        host_port = int(listener.getsockname()[1])
        device_port = host_port
        try:
            self.adb.reverse_tcp(
                self.serial,
                device_port=device_port,
                host_port=host_port,
            )
            self._screen_reverse_port = device_port

            self._write_line(
                "SCREEN_START "
                f"{device_port} {int(width)} {int(height)} {int(bit_rate)}"
            )

            try:
                connection, _ = listener.accept()
            except socket.timeout as exc:
                raise SidecarError(
                    "Android sidecar screen stream did not connect before timeout"
                ) from exc
            connection.settimeout(self.timeout)
            connection.setsockopt(
                socket.IPPROTO_TCP,
                socket.TCP_NODELAY,
                1,
            )

            raw_header = _recv_exact(
                connection,
                _SCREEN_STREAM_HEADER.size,
                allow_eof=False,
            )
            assert raw_header is not None
            (
                magic,
                stream_version,
                stream_width,
                stream_height,
                stream_bit_rate,
                start_elapsed_ns,
            ) = _SCREEN_STREAM_HEADER.unpack(
                raw_header
            )
            if magic != SCREEN_STREAM_MAGIC:
                raise SidecarError(
                    "Android sidecar screen stream has invalid magic"
                )
            if stream_version != SCREEN_STREAM_VERSION:
                raise SidecarError(
                    "Android sidecar screen stream version mismatch"
                )

            _, _, codec = parse_screen_started(
                self._read_line(),
                expected_width=int(width),
                expected_height=int(height),
            )
            if (
                stream_width != int(width)
                or stream_height != int(height)
                or stream_bit_rate != int(bit_rate)
            ):
                raise SidecarError(
                    "Android sidecar binary screen header mismatch"
                )

            info = SidecarScreenInfo(
                stream_version=int(stream_version),
                codec=codec,
                width=int(stream_width),
                height=int(stream_height),
                bit_rate=int(stream_bit_rate),
                agent_elapsed_start_ns=int(start_elapsed_ns),
                transport="adb-reverse-tcp-binary",
                host_port=host_port,
                device_port=device_port,
            )
            stream = SidecarScreenStream(
                connection,
                info,
            )
            self._screen_stream = stream
            return stream
        except Exception:
            self._cleanup_screen_transport()
            raise

    def stop_screen_stream(self) -> SidecarScreenStop:
        if self._screen_stream is None:
            raise SidecarError(
                "Android sidecar screen stream is not running"
            )

        try:
            self._write_line("SCREEN_STOP")
            result = parse_screen_stopped(
                self._read_line()
            )
            return result
        finally:
            self._cleanup_screen_transport()

    def stop(self) -> SidecarCleanup:
        return self._cleanup(
            graceful=True,
            suppress_errors=False,
        )

    def _cleanup_screen_transport(self) -> bool:
        removed = self._screen_reverse_port is None

        stream = self._screen_stream
        if stream is not None:
            stream.close()
            self._screen_stream = None

        listener = self._screen_listener
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
            self._screen_listener = None

        if self._screen_reverse_port is not None:
            try:
                self.adb.remove_reverse_tcp(
                    self.serial,
                    self._screen_reverse_port,
                )
                removed = True
            except Exception:
                removed = False
            self._screen_reverse_port = None
        return removed

    def _cleanup(
        self,
        *,
        graceful: bool,
        suppress_errors: bool,
    ) -> SidecarCleanup:
        graceful_protocol_stop = False
        process_exit_code: int | None = None
        reverse_removed = (
            self._reverse_port is None
            and self._screen_reverse_port is None
        )
        remote_removed = False
        errors: list[Exception] = []

        if self._screen_stream is not None:
            if graceful:
                try:
                    self.stop_screen_stream()
                except Exception as exc:
                    errors.append(exc)
                    if self._cleanup_screen_transport():
                        reverse_removed = self._reverse_port is None
            else:
                if self._cleanup_screen_transport():
                    reverse_removed = self._reverse_port is None

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
                reverse_removed = (
                    self._screen_reverse_port is None
                )
            except Exception as exc:
                errors.append(exc)
            self._reverse_port = None
        elif self._screen_reverse_port is None:
            reverse_removed = True

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
