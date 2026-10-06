from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apk_research.collectors.continuous_screen import (
    ContinuousScreenCollector,
)
from apk_research.desktop.sidecar import (
    SidecarCleanup,
    SidecarHandshake,
    SidecarScreenInfo,
    SidecarScreenPacket,
    SidecarScreenStop,
)
from apk_research.session import SessionManager


class TestClock:
    def __init__(self) -> None:
        self.value = datetime(
            2026,
            10,
            6,
            0,
            0,
            tzinfo=timezone.utc,
        )

    def __call__(self) -> datetime:
        value = self.value
        self.value += timedelta(seconds=1)
        return value


class FakeAdb:
    def get_utc_time(self, serial: str) -> str:
        assert serial == "emulator-5554"
        return "2026-10-06T00:00:00Z"


class FakeStream:
    def __init__(self) -> None:
        self.info = SidecarScreenInfo(
            stream_version=1,
            codec="h264",
            width=540,
            height=960,
            bit_rate=2_000_000,
            agent_elapsed_start_ns=123456,
            transport="test",
            host_port=123,
            device_port=123,
        )
        self._finished = threading.Event()
        self._packets = [
            SidecarScreenPacket(
                sequence=1,
                flags=2,
                pts_us=0,
                payload=b"config",
            ),
            SidecarScreenPacket(
                sequence=2,
                flags=1,
                pts_us=1_000_000,
                payload=b"frame-one",
            ),
            SidecarScreenPacket(
                sequence=3,
                flags=0,
                pts_us=2_500_000,
                payload=b"frame-two",
            ),
            SidecarScreenPacket(
                sequence=4,
                flags=4,
                pts_us=0,
                payload=b"",
            ),
        ]

    def read_packet(self):
        if self._packets:
            return self._packets.pop(0)
        self._finished.wait(timeout=2.0)
        return None

    def finish(self) -> None:
        self._finished.set()


class FakeSidecar:
    running = True

    def __init__(self) -> None:
        self.stream = FakeStream()

    def start(self) -> SidecarHandshake:
        return SidecarHandshake(
            protocol_version=2,
            agent_version="0.2.0",
            transport="test",
            host_port=10,
            device_port=10,
            remote_agent="/agent.jar",
        )

    def start_screen_stream(
        self,
        *,
        width: int,
        height: int,
        bit_rate: int,
    ) -> FakeStream:
        assert (width, height, bit_rate) == (
            540,
            960,
            2_000_000,
        )
        return self.stream

    def stop_screen_stream(self) -> SidecarScreenStop:
        self.stream.finish()
        return SidecarScreenStop(
            packet_count=4,
            byte_count=25,
            first_pts_us=1_000_000,
            last_pts_us=2_500_000,
        )

    def stop(self) -> SidecarCleanup:
        return SidecarCleanup(
            graceful_protocol_stop=True,
            process_exit_code=0,
            reverse_removed=True,
            remote_agent_removed=True,
        )


def _session(tmp_path: Path) -> SessionManager:
    session = SessionManager.create(
        tmp_path,
        target={"serial": "emulator-5554"},
        package={"name": "com.example.app"},
        clock=TestClock(),
        session_id_factory=lambda: "continuous-screen",
    )
    session.begin_preflight()
    session.mark_ready()
    session.begin_start()
    return session


def test_continuous_screen_writes_lossless_packet_payloads_and_pts(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    fake = FakeSidecar()
    collector = ContinuousScreenCollector(
        FakeAdb(),  # type: ignore[arg-type]
        session,
        clock=TestClock(),
        sidecar_factory=lambda adb, serial: fake,
    )

    collector.start()

    session.mark_active()
    session.begin_stop()
    result = collector.stop()

    assert result.status == "completed"
    assert result.packet_count == 4
    assert result.media_frame_count == 2
    assert result.presentation_span_seconds == 1.5
    assert session.degraded is False

    video = (
        session.paths.root
        / ContinuousScreenCollector.RAW_VIDEO_ARTIFACT
    ).read_bytes()
    assert video == b"configframe-oneframe-two"

    records = [
        json.loads(line)
        for line in (
            session.paths.root
            / ContinuousScreenCollector.PACKET_INDEX_ARTIFACT
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert records[0]["codec_config"] is True
    assert records[1]["key_frame"] is True
    assert records[1]["raw_offset"] == len(b"config")
    assert records[2]["pts_us"] == 2_500_000
    assert records[3]["end_of_stream"] is True
    assert records[3]["size"] == 0

    metadata = json.loads(
        (
            session.paths.root
            / ContinuousScreenCollector.METADATA_ARTIFACT
        ).read_text(encoding="utf-8")
    )
    assert metadata["canonical"] is False
    assert metadata["experimental"] is True
    assert metadata["status"] == "completed"
    assert metadata["media_frame_count"] == 2


def test_continuous_screen_unavailable_does_not_degrade_session(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)

    def unavailable(adb, serial):
        raise RuntimeError("sidecar payload missing")

    collector = ContinuousScreenCollector(
        FakeAdb(),  # type: ignore[arg-type]
        session,
        clock=TestClock(),
        sidecar_factory=unavailable,
    )
    collector.start()

    assert collector.check_health() is True
    assert session.degraded is False
    assert session.manifest["collectors"][
        ContinuousScreenCollector.NAME
    ]["required"] is False
    assert session.manifest["collectors"][
        ContinuousScreenCollector.NAME
    ]["status"] == "unavailable"

    session.mark_active()
    session.begin_stop()
    result = collector.stop()
    assert result.status == "unavailable"
    assert result.availability_error == "sidecar payload missing"
    assert session.degraded is False
