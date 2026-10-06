from __future__ import annotations

from pathlib import Path

import pytest

from apk_research.desktop.sidecar import (
    AGENT_VERSION,
    PROTOCOL_VERSION,
    SidecarError,
    parse_agent_banner,
    parse_pong,
    parse_ready,
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
