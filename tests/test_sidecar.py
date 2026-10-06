from __future__ import annotations

import socket
from pathlib import Path

import pytest

from apk_research.desktop.sidecar import (
    AGENT_VERSION,
    PROTOCOL_VERSION,
    SCREEN_STREAM_MAGIC,
    SCREEN_STREAM_VERSION,
    SidecarError,
    SidecarScreenStream,
    SidecarScreenInfo,
    parse_agent_banner,
    parse_pong,
    parse_ready,
    parse_screen_started,
    parse_screen_stopped,
    resolve_agent_jar,
)


def test_parse_agent_banner_requires_exact_shape() -> None:
    assert parse_agent_banner(
        f"APK_RESEARCH_AGENT {PROTOCOL_VERSION} {AGENT_VERSION}"
    ) == (
        PROTOCOL_VERSION,
        AGENT_VERSION,
    )

    with pytest.raises(
        SidecarError,
        match="Invalid Android sidecar banner",
    ):
        parse_agent_banner("hello")


def test_parse_ready_requires_version_fields() -> None:
    assert parse_ready(
        f"READY {PROTOCOL_VERSION} {AGENT_VERSION}"
    ) == (
        PROTOCOL_VERSION,
        AGENT_VERSION,
    )

    with pytest.raises(SidecarError):
        parse_ready("READY broken")


def test_parse_pong_binds_response_to_request_token() -> None:
    value = parse_pong(
        "PONG request-1 12345",
        expected_token="request-1",
    )

    assert value.token == "request-1"
    assert value.agent_uptime_ms == 12345

    with pytest.raises(SidecarError):
        parse_pong(
            "PONG other 12345",
            expected_token="request-1",
        )


def test_screen_control_responses_are_strict() -> None:
    assert parse_screen_started(
        "SCREEN_STARTED 540 960 h264",
        expected_width=540,
        expected_height=960,
    ) == (540, 960, "h264")

    result = parse_screen_stopped(
        "SCREEN_STOPPED 10 2048 1000000 2500000"
    )
    assert result.packet_count == 10
    assert result.byte_count == 2048
    assert result.presentation_span_seconds == 1.5

    with pytest.raises(SidecarError):
        parse_screen_started(
            "SCREEN_STARTED 720 1280 h264",
            expected_width=540,
            expected_height=960,
        )


def test_binary_screen_packet_parser_preserves_pts_and_flags() -> None:
    left, right = socket.socketpair()
    try:
        info = SidecarScreenInfo(
            stream_version=SCREEN_STREAM_VERSION,
            codec="h264",
            width=540,
            height=960,
            bit_rate=2_000_000,
            agent_elapsed_start_ns=123,
            transport="test",
            host_port=1,
            device_port=1,
        )
        stream = SidecarScreenStream(left, info)
        payload = b"\x00\x00\x00\x01test"
        right.sendall(
            (1).to_bytes(4, "big")
            + (123456).to_bytes(8, "big", signed=True)
            + len(payload).to_bytes(4, "big")
            + payload
        )
        right.shutdown(socket.SHUT_WR)

        packet = stream.read_packet()
        assert packet is not None
        assert packet.sequence == 1
        assert packet.pts_us == 123456
        assert packet.key_frame is True
        assert packet.codec_config is False
        assert packet.payload == payload
        assert stream.read_packet() is None
    finally:
        left.close()
        right.close()


def test_screen_stream_constants_are_stable() -> None:
    assert SCREEN_STREAM_MAGIC == b"APKRSCRN"
    assert SCREEN_STREAM_VERSION == 1


def test_resolve_agent_jar_accepts_explicit_existing_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "agent.jar"
    path.write_bytes(b"PK")

    assert resolve_agent_jar(path) == path.resolve()


def test_resolve_agent_jar_rejects_missing_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        SidecarError,
        match="agent is missing",
    ):
        resolve_agent_jar(
            tmp_path / "missing.jar"
        )
