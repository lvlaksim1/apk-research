from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from apk_research.desktop.sidecar import (
    AndroidSidecar,
    SidecarCleanup,
    SidecarHandshake,
    SidecarScreenInfo,
    SidecarScreenStop,
)
from apk_research.session import SessionManager, SessionStatus
from apk_research.targets import AdbClient, AdbError

Clock = Callable[[], datetime]


class SidecarLike(Protocol):
    @property
    def running(self) -> bool: ...
    def start(self) -> SidecarHandshake: ...
    def start_screen_stream(
        self,
        *,
        width: int,
        height: int,
        bit_rate: int,
    ): ...
    def stop_screen_stream(self) -> SidecarScreenStop: ...
    def stop(self) -> SidecarCleanup: ...


SidecarFactory = Callable[
    [AdbClient, str],
    SidecarLike,
]


class ContinuousScreenCollectorError(RuntimeError):
    """Raised for invalid continuous-screen collector lifecycle."""


@dataclass(frozen=True)
class ContinuousScreenResult:
    collector: str
    status: str
    raw_video: str | None
    packet_index: str | None
    metadata_artifact: str
    packet_count: int
    media_frame_count: int
    bytes_captured: int
    presentation_span_seconds: float
    availability_error: str | None
    receiver_error: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json_atomic(
    path: Path,
    value: dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
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
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _default_sidecar_factory(
    adb: AdbClient,
    serial: str,
) -> AndroidSidecar:
    return AndroidSidecar(adb, serial)


class ContinuousScreenCollector:
    """Experimental sidecar MediaCodec screen evidence captured beside screenrecord.

    The existing chunked screenrecord collector remains canonical. Failure of
    this experimental collector is preserved in metadata but does not degrade
    the Research Session.
    """

    NAME = "continuous_screen"
    BACKEND = "android-sidecar-mediacodec-h264"
    RAW_VIDEO_ARTIFACT = "01_raw/screen/continuous-screen.h264"
    PACKET_INDEX_ARTIFACT = (
        "02_normalized/continuous-screen-packets.jsonl"
    )
    METADATA_ARTIFACT = "02_normalized/continuous-screen.json"

    DEFAULT_WIDTH = 540
    DEFAULT_HEIGHT = 960
    DEFAULT_BIT_RATE = 2_000_000

    def __init__(
        self,
        adb: AdbClient,
        session: SessionManager,
        *,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        bit_rate: int = DEFAULT_BIT_RATE,
        clock: Clock = _utc_now,
        sidecar_factory: SidecarFactory = _default_sidecar_factory,
    ) -> None:
        if width < 64 or height < 64:
            raise ValueError(
                "continuous screen dimensions must be at least 64 pixels"
            )
        if bit_rate < 100_000:
            raise ValueError(
                "continuous screen bit rate must be at least 100000"
            )
        self.adb = adb
        self.session = session
        self.width = int(width)
        self.height = int(height)
        self.bit_rate = int(bit_rate)
        self.clock = clock
        self.sidecar_factory = sidecar_factory

        self._serial: str | None = None
        self._sidecar: SidecarLike | None = None
        self._stream = None
        self._receiver: threading.Thread | None = None
        self._stop_requested = False
        self._status = "new"
        self._started_utc: str | None = None
        self._stopped_utc: str | None = None
        self._target_started_utc: str | None = None
        self._target_stopped_utc: str | None = None
        self._handshake: dict[str, object] | None = None
        self._stream_info: dict[str, object] | None = None
        self._stop_info: dict[str, object] | None = None
        self._cleanup_info: dict[str, object] | None = None
        self._availability_error: str | None = None
        self._receiver_error: str | None = None
        self._packet_count = 0
        self._media_frame_count = 0
        self._bytes_captured = 0
        self._first_pts_us: int | None = None
        self._last_pts_us: int | None = None

    @property
    def running(self) -> bool:
        return (
            self._status == "running"
            and self._receiver is not None
            and self._receiver.is_alive()
        )

    def start(self) -> None:
        if self._status != "new":
            raise ContinuousScreenCollectorError(
                "Continuous screen collector was already started"
            )
        if self.session.status != SessionStatus.STARTING:
            raise ContinuousScreenCollectorError(
                "Continuous screen collector may start only while session "
                f"status is 'starting'; current status is "
                f"{self.session.status.value!r}"
            )

        serial = str(
            self.session.manifest.get("target", {}).get("serial") or ""
        ).strip()
        if not serial:
            raise ContinuousScreenCollectorError(
                "Session target serial is missing"
            )
        self._serial = serial
        self._started_utc = _iso_utc(self.clock())
        self._target_started_utc = self._target_time_best_effort()

        self.session.register_collector(
            self.NAME,
            required=False,
            backend=self.BACKEND,
        )
        self.session.register_artifact(
            kind="continuous_screen_metadata",
            relative_path=self.METADATA_ARTIFACT,
            source=self.NAME,
            raw=False,
        )

        try:
            sidecar = self.sidecar_factory(
                self.adb,
                serial,
            )
            self._sidecar = sidecar
            handshake = sidecar.start()
            self._handshake = handshake.to_dict()

            stream = sidecar.start_screen_stream(
                width=self.width,
                height=self.height,
                bit_rate=self.bit_rate,
            )
            self._stream = stream
            info: SidecarScreenInfo = stream.info
            self._stream_info = info.to_dict()

            video_path = (
                self.session.paths.root
                / self.RAW_VIDEO_ARTIFACT
            )
            index_path = (
                self.session.paths.root
                / self.PACKET_INDEX_ARTIFACT
            )
            video_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            index_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            video_path.touch()
            index_path.touch()

            self.session.register_artifact(
                kind="continuous_screen_h264",
                relative_path=self.RAW_VIDEO_ARTIFACT,
                source=self.NAME,
                raw=True,
            )
            self.session.register_artifact(
                kind="continuous_screen_packet_index",
                relative_path=self.PACKET_INDEX_ARTIFACT,
                source=self.NAME,
                raw=False,
            )

            self._status = "running"
            self.session.update_collector(
                self.NAME,
                "running",
                artifact_path=self.RAW_VIDEO_ARTIFACT,
            )
            self.session.update_collector(
                self.NAME,
                "running",
                artifact_path=self.PACKET_INDEX_ARTIFACT,
            )
            self._write_metadata()

            self._receiver = threading.Thread(
                target=self._receive_stream,
                daemon=True,
                name="apk-research-continuous-screen",
            )
            self._receiver.start()
        except Exception as exc:
            self._availability_error = (
                str(exc) or exc.__class__.__name__
            )
            self._status = "unavailable"
            self._cleanup_sidecar_best_effort()
            self.session.update_collector(
                self.NAME,
                "unavailable",
                artifact_path=self.METADATA_ARTIFACT,
            )
            self._write_metadata()

    def check_health(self) -> bool:
        if self._status in {
            "unavailable",
            "failed-experimental",
            "completed",
        }:
            return True
        if self._status != "running":
            return True

        receiver = self._receiver
        if (
            self._receiver_error is not None
            or receiver is None
            or (
                not receiver.is_alive()
                and not self._stop_requested
            )
        ):
            self._status = "failed-experimental"
            self.session.update_collector(
                self.NAME,
                "failed-experimental",
                artifact_path=self.METADATA_ARTIFACT,
            )
            self._write_metadata()
        return True

    def stop(
        self,
        grace_period: float = 3.0,
    ) -> ContinuousScreenResult:
        del grace_period

        if self._status == "new":
            raise ContinuousScreenCollectorError(
                "Continuous screen collector is not started"
            )
        if self._status in {
            "completed",
            "unavailable",
            "failed-experimental",
        } and self._stopped_utc is not None:
            return self._result()

        self._stop_requested = True
        self._stopped_utc = _iso_utc(self.clock())
        self._target_stopped_utc = self._target_time_best_effort()

        sidecar = self._sidecar
        if sidecar is not None and self._stream is not None:
            try:
                stop_info = sidecar.stop_screen_stream()
                self._stop_info = stop_info.to_dict()
            except Exception as exc:
                if self._receiver_error is None:
                    self._receiver_error = (
                        str(exc) or exc.__class__.__name__
                    )

        receiver = self._receiver
        if receiver is not None:
            receiver.join(timeout=5.0)
            if receiver.is_alive() and self._receiver_error is None:
                self._receiver_error = (
                    "continuous screen receiver did not stop"
                )

        if sidecar is not None:
            try:
                cleanup = sidecar.stop()
                self._cleanup_info = cleanup.to_dict()
            except Exception as exc:
                if self._receiver_error is None:
                    self._receiver_error = (
                        str(exc) or exc.__class__.__name__
                    )

        successful = (
            self._availability_error is None
            and self._receiver_error is None
            and self._media_frame_count > 0
            and self._bytes_captured > 0
            and self._stop_info is not None
            and bool(
                (self._cleanup_info or {}).get(
                    "complete",
                    False,
                )
            )
        )
        self._status = (
            "completed"
            if successful
            else (
                "unavailable"
                if self._availability_error is not None
                else "failed-experimental"
            )
        )
        self.session.update_collector(
            self.NAME,
            self._status,
            artifact_path=self.METADATA_ARTIFACT,
        )
        self._write_metadata()
        return self._result()

    def _receive_stream(self) -> None:
        assert self._stream is not None
        video_path = (
            self.session.paths.root
            / self.RAW_VIDEO_ARTIFACT
        )
        index_path = (
            self.session.paths.root
            / self.PACKET_INDEX_ARTIFACT
        )
        raw_offset = 0

        try:
            with video_path.open("wb") as video, index_path.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as index:
                while True:
                    packet = self._stream.read_packet()
                    if packet is None:
                        break

                    if packet.payload:
                        video.write(packet.payload)

                    record = {
                        "sequence": packet.sequence,
                        "flags": packet.flags,
                        "pts_us": packet.pts_us,
                        "size": packet.size,
                        "raw_offset": raw_offset,
                        "codec_config": packet.codec_config,
                        "key_frame": packet.key_frame,
                        "end_of_stream": packet.end_of_stream,
                    }
                    index.write(
                        json.dumps(
                            record,
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                    )
                    index.write("\n")

                    self._packet_count += 1
                    self._bytes_captured += packet.size
                    raw_offset += packet.size

                    if (
                        packet.size > 0
                        and not packet.codec_config
                    ):
                        self._media_frame_count += 1
                        if self._first_pts_us is None:
                            self._first_pts_us = packet.pts_us
                        self._last_pts_us = packet.pts_us

                video.flush()
                os.fsync(video.fileno())
                index.flush()
                os.fsync(index.fileno())
        except Exception as exc:
            self._receiver_error = (
                str(exc) or exc.__class__.__name__
            )

    def _cleanup_sidecar_best_effort(self) -> None:
        sidecar = self._sidecar
        if sidecar is None:
            return
        try:
            cleanup = sidecar.stop()
            self._cleanup_info = cleanup.to_dict()
        except Exception:
            pass

    def _target_time_best_effort(self) -> str | None:
        if self._serial is None:
            return None
        try:
            return self.adb.get_utc_time(
                self._serial
            )
        except (AdbError, AttributeError):
            return None

    def _presentation_span_seconds(self) -> float:
        if (
            self._first_pts_us is None
            or self._last_pts_us is None
            or self._last_pts_us < self._first_pts_us
        ):
            return 0.0
        return (
            self._last_pts_us - self._first_pts_us
        ) / 1_000_000

    def _write_metadata(self) -> None:
        value: dict[str, object] = {
            "schema_version": "0.1",
            "collector": self.NAME,
            "backend": self.BACKEND,
            "canonical": False,
            "experimental": True,
            "codec": "h264",
            "requested": {
                "width": self.width,
                "height": self.height,
                "bit_rate": self.bit_rate,
            },
            "timing_model": {
                "packet_pts": (
                    "MediaCodec BufferInfo.presentationTimeUs generated "
                    "on the Android target"
                ),
                "clock_domain": (
                    "device-media-presentation; not converted to UTC"
                ),
                "agent_start_clock": (
                    "Android SystemClock.elapsedRealtimeNanos"
                ),
                "host_target_boundaries": (
                    "best-effort ADB UTC samples recorded separately"
                ),
            },
            "status": self._status,
            "started_utc": self._started_utc,
            "stopped_utc": self._stopped_utc,
            "target_started_utc": self._target_started_utc,
            "target_stopped_utc": self._target_stopped_utc,
            "sidecar_handshake": self._handshake,
            "stream": self._stream_info,
            "stop": self._stop_info,
            "cleanup": self._cleanup_info,
            "raw_video": (
                self.RAW_VIDEO_ARTIFACT
                if self._stream_info is not None
                else None
            ),
            "packet_index": (
                self.PACKET_INDEX_ARTIFACT
                if self._stream_info is not None
                else None
            ),
            "packet_count": self._packet_count,
            "media_frame_count": self._media_frame_count,
            "bytes_captured": self._bytes_captured,
            "first_pts_us": self._first_pts_us,
            "last_pts_us": self._last_pts_us,
            "presentation_span_seconds": (
                self._presentation_span_seconds()
            ),
            "availability_error": self._availability_error,
            "receiver_error": self._receiver_error,
            "evidence_boundary": (
                "Experimental parallel capture. Chunked Android screenrecord "
                "remains the canonical required screen evidence."
            ),
        }
        _write_json_atomic(
            self.session.paths.root
            / self.METADATA_ARTIFACT,
            value,
        )

    def _result(self) -> ContinuousScreenResult:
        return ContinuousScreenResult(
            collector=self.NAME,
            status=self._status,
            raw_video=(
                self.RAW_VIDEO_ARTIFACT
                if self._stream_info is not None
                else None
            ),
            packet_index=(
                self.PACKET_INDEX_ARTIFACT
                if self._stream_info is not None
                else None
            ),
            metadata_artifact=self.METADATA_ARTIFACT,
            packet_count=self._packet_count,
            media_frame_count=self._media_frame_count,
            bytes_captured=self._bytes_captured,
            presentation_span_seconds=(
                self._presentation_span_seconds()
            ),
            availability_error=self._availability_error,
            receiver_error=self._receiver_error,
        )
