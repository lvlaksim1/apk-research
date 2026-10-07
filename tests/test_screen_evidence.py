from __future__ import annotations

from apk_research.desktop.screen_evidence import (
    build_screen_evidence_index,
    locate_screen_moment,
)


def _canonical() -> dict:
    return {
        "completed_chunks": [
            {
                "index": 1,
                "local_video": "01_raw/screen/screen-0001.mp4",
                "frame_timing": {
                    "first_frame_utc": "2026-01-01T00:00:01Z",
                    "last_frame_utc": "2026-01-01T00:00:02Z",
                    "frame_count": 30,
                    "realtime_to_elapsed_offset_ns": 1_767_225_599_000_000_000,
                    "clock_domain": "device-realtime-derived-from-elapsed",
                    "source": "winscope-v2",
                },
            },
            {
                "index": 2,
                "local_video": "01_raw/screen/screen-0002.mp4",
                "frame_timing": {
                    "first_frame_utc": "2026-01-01T00:00:04Z",
                    "last_frame_utc": "2026-01-01T00:00:05Z",
                    "frame_count": 30,
                    "realtime_to_elapsed_offset_ns": 1_767_225_599_000_000_000,
                    "clock_domain": "device-realtime-derived-from-elapsed",
                    "source": "winscope-v2",
                },
            },
        ]
    }


def _continuous() -> dict:
    return {
        "status": "completed",
        "raw_video": "01_raw/screen/continuous-screen.h264",
        "packet_index": "02_normalized/continuous-screen-packets.jsonl",
        "first_pts_us": 2_000_000,
        "target_started_utc": "2026-01-01T00:00:01Z",
    }


def _packets() -> list[dict]:
    return [
        {
            "sequence": 1,
            "pts_us": 2_000_000,
            "size": 100,
            "raw_offset": 0,
            "codec_config": False,
            "key_frame": True,
            "end_of_stream": False,
        },
        {
            "sequence": 2,
            "pts_us": 3_000_000,
            "size": 50,
            "raw_offset": 100,
            "codec_config": False,
            "key_frame": False,
            "end_of_stream": False,
        },
        {
            "sequence": 3,
            "pts_us": 4_000_000,
            "size": 60,
            "raw_offset": 150,
            "codec_config": False,
            "key_frame": False,
            "end_of_stream": False,
        },
    ]


def test_screen_index_uses_device_elapsed_to_realtime_transform() -> None:
    index = build_screen_evidence_index(
        _continuous(),
        _canonical(),
        _packets(),
    )

    assert index["available"] is True
    assert index["mapping_method"] == "screenrecord-realtime-to-elapsed-offset"
    assert index["confidence"] == "HIGH"
    assert index["causal_claim"] is False

    locator = locate_screen_moment(
        index,
        "2026-01-01T00:00:02Z",
    )
    assert locator is not None
    assert locator["continuous"]["sequence"] == 1
    assert abs(locator["continuous"]["delta_seconds"]) < 0.001
    assert locator["canonical"]["covered"] is True
    assert locator["canonical"]["chunk_index"] == 1
    assert locator["causal_claim"] is False


def test_continuous_locator_survives_canonical_chunk_gap() -> None:
    index = build_screen_evidence_index(
        _continuous(),
        _canonical(),
        _packets(),
    )

    locator = locate_screen_moment(
        index,
        "2026-01-01T00:00:03Z",
    )
    assert locator is not None
    assert locator["continuous_available"] is True
    assert locator["continuous"]["sequence"] == 2
    assert locator["canonical"]["covered"] is False
    assert locator["relation_type"] == "time-aligned-navigation"


def test_codec_config_and_eos_are_not_navigation_frames() -> None:
    packets = _packets() + [
        {
            "sequence": 10,
            "pts_us": 3_000_000,
            "size": 12,
            "raw_offset": 999,
            "codec_config": True,
            "key_frame": False,
            "end_of_stream": False,
        },
        {
            "sequence": 11,
            "pts_us": 0,
            "size": 0,
            "raw_offset": 1011,
            "codec_config": False,
            "key_frame": False,
            "end_of_stream": True,
        },
    ]
    index = build_screen_evidence_index(
        _continuous(),
        _canonical(),
        packets,
    )
    assert [frame["sequence"] for frame in index["frames"]] == [1, 2, 3]
