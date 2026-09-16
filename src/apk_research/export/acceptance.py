from __future__ import annotations

import json
import re
import struct
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO

from apk_research.timeline import TIMELINE_ARTIFACT

from .research_zip import ExportError, verify_research_zip

_REQUIRED_COLLECTORS = (
    "device_metadata",
    "logcat",
    "screen_recording",
    "raw_network",
)
_REQUIRED_EVENT_SEQUENCE = (
    "session_created",
    "preflight_started",
    "device_metadata_completed",
    "raw_network_preflight_completed",
    "preflight_completed",
    "logcat_started",
    "screen_recording_started",
    "raw_network_started",
    "capture_active",
    "package_launched",
    "stop_requested",
    "raw_network_stopped",
    "screen_recording_stopped",
    "logcat_stopped",
    "capture_finished",
)
_LOGCAT_EPOCH_RE = re.compile(rb"^\s*(\d+\.\d+)\s")


@dataclass(frozen=True)
class CompleteResearchAudit:
    archive: str
    session_id: str
    package: str
    packet_count: int
    pcap_first_utc: str
    pcap_last_utc: str
    logcat_entries: int
    logcat_first_utc: str
    logcat_last_utc: str
    screen_frames: int
    screen_first_frame_utc: str
    screen_last_frame_utc: str
    screen_last_frame_gap_seconds: float
    screen_capture_started_utc: str
    screen_capture_stopped_utc: str
    screen_capture_span_seconds: float
    user_actions: int
    timeline_events: int
    max_clock_skew_seconds: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ExportError(
            f"Invalid UTC timestamp in Research ZIP: {value!r}"
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_from_epoch(value: float) -> str:
    return (
        datetime.fromtimestamp(value, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _read_json(
    archive: zipfile.ZipFile,
    path: str,
) -> dict[str, object]:
    try:
        return json.loads(
            archive.read(path).decode("utf-8")
        )
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExportError(
            f"Invalid required JSON entry: {path}"
        ) from exc


def _read_events(
    archive: zipfile.ZipFile,
) -> list[dict[str, object]]:
    path = "02_normalized/session-events.jsonl"
    try:
        raw = archive.read(path).decode("utf-8")
    except (KeyError, UnicodeDecodeError) as exc:
        raise ExportError(
            f"Invalid required event stream: {path}"
        ) from exc

    events: list[dict[str, object]] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ExportError(
                f"Invalid event JSON on line {line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise ExportError(
                f"Invalid event value on line {line_number}"
            )
        events.append(value)
    return events


def _read_pcap_summary(
    handle: BinaryIO,
) -> tuple[int, float, float, int]:
    header = handle.read(24)
    if len(header) != 24:
        raise ExportError("PCAP is missing its global header")

    magics = {
        b"\xd4\xc3\xb2\xa1": ("<", 1_000_000),
        b"\xa1\xb2\xc3\xd4": (">", 1_000_000),
        b"\x4d\x3c\xb2\xa1": ("<", 1_000_000_000),
        b"\xa1\xb2\x3c\x4d": (">", 1_000_000_000),
    }
    try:
        endian, fraction_scale = magics[header[:4]]
    except KeyError as exc:
        raise ExportError("Unsupported PCAP magic number") from exc

    major, minor = struct.unpack(
        f"{endian}HH",
        header[4:8],
    )
    if (major, minor) != (2, 4):
        raise ExportError(
            f"Unexpected PCAP version: {major}.{minor}"
        )

    packet_count = 0
    first_timestamp: float | None = None
    last_timestamp: float | None = None

    while True:
        record_header = handle.read(16)
        if not record_header:
            break
        if len(record_header) != 16:
            raise ExportError("Truncated PCAP packet header")

        seconds, fraction, included, original = struct.unpack(
            f"{endian}IIII",
            record_header,
        )
        if included > 32 * 1024 * 1024:
            raise ExportError(
                f"Unreasonable PCAP packet length: {included}"
            )

        payload = handle.read(included)
        if len(payload) != included:
            raise ExportError("Truncated PCAP packet payload")

        timestamp = seconds + fraction / fraction_scale
        packet_count += 1
        if first_timestamp is None:
            first_timestamp = timestamp
        last_timestamp = timestamp

    if packet_count == 0 or first_timestamp is None or last_timestamp is None:
        raise ExportError("PCAP contains no packet records")

    return (
        packet_count,
        first_timestamp,
        last_timestamp,
        original,
    )


def _read_logcat_summary(
    handle: BinaryIO,
) -> tuple[int, float, float]:
    entries = 0
    first_timestamp: float | None = None
    last_timestamp: float | None = None

    for line in handle:
        match = _LOGCAT_EPOCH_RE.match(line)
        if match is None:
            continue
        timestamp = float(match.group(1))
        entries += 1
        if first_timestamp is None:
            first_timestamp = timestamp
        last_timestamp = timestamp

    if entries == 0 or first_timestamp is None or last_timestamp is None:
        raise ExportError(
            "Logcat contains no epoch-timestamped entries"
        )

    return entries, first_timestamp, last_timestamp


def audit_complete_research_zip(
    archive_path: str | Path,
    *,
    max_clock_skew_seconds: float = 2.0,
) -> CompleteResearchAudit:
    verification = verify_research_zip(archive_path)
    path = Path(archive_path).expanduser().resolve()

    with zipfile.ZipFile(path, mode="r") as archive:
        manifest = _read_json(
            archive,
            "00_manifest/session.json",
        )
        if manifest.get("status") != "complete":
            raise ExportError(
                "Semantic audit requires session_status=complete"
            )
        if bool(manifest.get("degraded", False)):
            raise ExportError(
                "Complete session is unexpectedly degraded"
            )
        if manifest.get("errors"):
            raise ExportError(
                "Complete session contains recorded errors"
            )

        collectors = manifest.get("collectors")
        if not isinstance(collectors, dict):
            raise ExportError("Manifest collectors are invalid")
        for name in _REQUIRED_COLLECTORS:
            value = collectors.get(name)
            if not isinstance(value, dict):
                raise ExportError(
                    f"Required collector missing: {name}"
                )
            if value.get("status") != "completed":
                raise ExportError(
                    f"Required collector not completed: {name}"
                )

        events = _read_events(archive)
        names = [
            str(event.get("event") or "")
            for event in events
        ]
        cursor = -1
        event_by_name: dict[str, dict[str, object]] = {}
        for required in _REQUIRED_EVENT_SEQUENCE:
            try:
                position = names.index(required, cursor + 1)
            except ValueError as exc:
                raise ExportError(
                    f"Required lifecycle event missing/out of order: "
                    f"{required}"
                ) from exc
            cursor = position
            event_by_name[required] = events[position]

        host_times = [
            _parse_utc(str(event["host_utc"]))
            for event in events
            if event.get("host_utc")
        ]
        if any(
            later < earlier
            for earlier, later in zip(
                host_times,
                host_times[1:],
            )
        ):
            raise ExportError(
                "Lifecycle host timestamps are not monotonic"
            )

        clock_skews: list[float] = []
        for event in events:
            host_value = event.get("host_utc")
            target_value = event.get("target_utc")
            if not host_value or not target_value:
                continue
            skew = abs(
                (
                    _parse_utc(str(host_value))
                    - _parse_utc(str(target_value))
                ).total_seconds()
            )
            clock_skews.append(skew)

        target = _read_json(
            archive,
            "02_normalized/target.json",
        )
        clock = target.get("clock")
        if isinstance(clock, dict):
            for host_key, target_key in (
                ("host_started_utc", "target_started_utc"),
                ("host_finished_utc", "target_finished_utc"),
            ):
                host_value = clock.get(host_key)
                target_value = clock.get(target_key)
                if host_value and target_value:
                    clock_skews.append(
                        abs(
                            (
                                _parse_utc(str(host_value))
                                - _parse_utc(str(target_value))
                            ).total_seconds()
                        )
                    )

        observed_clock_skew = max(clock_skews, default=0.0)
        if observed_clock_skew > max_clock_skew_seconds:
            raise ExportError(
                "Host/target clock skew exceeds acceptance limit: "
                f"{observed_clock_skew:.3f}s"
            )

        launch_time = _parse_utc(
            str(event_by_name["package_launched"]["host_utc"])
        )
        capture_start = _parse_utc(
            str(event_by_name["capture_active"]["host_utc"])
        )
        stop_time = _parse_utc(
            str(event_by_name["stop_requested"]["host_utc"])
        )

        launch_text = archive.read(
            "01_raw/device/package-launch.txt"
        ).decode("utf-8", errors="replace")
        if "Status: ok" not in launch_text:
            raise ExportError(
                "Package launch evidence does not contain Status: ok"
            )

        with archive.open(
            "01_raw/network/traffic.pcap",
            mode="r",
        ) as handle:
            (
                packet_count,
                pcap_first,
                pcap_last,
                _,
            ) = _read_pcap_summary(handle)

        if not (
            pcap_first <= stop_time.timestamp()
            and pcap_last >= capture_start.timestamp()
        ):
            raise ExportError(
                "PCAP timestamps do not overlap active capture"
            )
        if not (
            pcap_first <= launch_time.timestamp() + 1.0
            and pcap_last >= launch_time.timestamp()
        ):
            raise ExportError(
                "PCAP does not cover package launch"
            )

        with archive.open(
            "01_raw/logcat/logcat.txt",
            mode="r",
        ) as handle:
            (
                logcat_entries,
                logcat_first,
                logcat_last,
            ) = _read_logcat_summary(handle)

        if logcat_first > capture_start.timestamp() + 1.0:
            raise ExportError(
                "Logcat starts too late for active capture"
            )
        if logcat_last < stop_time.timestamp() - 1.0:
            raise ExportError(
                "Logcat ends too early for active capture"
            )
        if not (
            logcat_first <= launch_time.timestamp()
            <= logcat_last
        ):
            raise ExportError(
                "Logcat does not cover package launch"
            )

        screen = _read_json(
            archive,
            "02_normalized/screen.json",
        )
        chunks = screen.get("completed_chunks")
        if not isinstance(chunks, list) or not chunks:
            raise ExportError(
                "Screen metadata has no completed chunks"
            )

        frame_count = 0
        first_frames: list[datetime] = []
        last_frames: list[datetime] = []
        capture_starts: list[datetime] = []
        capture_stops: list[datetime] = []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            if chunk.get("status") != "completed":
                continue
            host_started = chunk.get("host_started_utc")
            host_finished = chunk.get("host_finished_utc")
            if host_started and host_finished:
                capture_starts.append(
                    _parse_utc(str(host_started))
                )
                capture_stops.append(
                    _parse_utc(str(host_finished))
                )
            timing = chunk.get("frame_timing")
            if not isinstance(timing, dict):
                continue
            if timing.get("source") != "winscope-v2":
                continue
            count = int(timing.get("frame_count") or 0)
            first_value = timing.get("first_frame_utc")
            last_value = timing.get("last_frame_utc")
            if count <= 0 or not first_value or not last_value:
                continue
            frame_count += count
            first_frames.append(_parse_utc(str(first_value)))
            last_frames.append(_parse_utc(str(last_value)))

        if frame_count <= 0 or not first_frames or not last_frames:
            raise ExportError(
                "Screen video has no Winscope v2 frame timing"
            )
        if not capture_starts or not capture_stops:
            raise ExportError(
                "Screen metadata has no recorder capture interval"
            )

        capture_started = min(capture_starts)
        capture_stopped = max(capture_stops)
        if capture_started > launch_time:
            raise ExportError(
                "Screen recorder process started after package launch"
            )
        if capture_stopped < stop_time:
            raise ExportError(
                "Screen recorder process stopped before stop request"
            )

        first_frame = min(first_frames)
        last_frame = max(last_frames)
        if first_frame > launch_time + timedelta(seconds=2):
            raise ExportError(
                "Screen recording starts too late for package launch"
            )
        if last_frame < launch_time:
            raise ExportError(
                "Screen recording contains no frame after package launch"
            )

        screen_gap = max(
            0.0,
            (stop_time - last_frame).total_seconds(),
        )

        user_actions = 0
        timeline_events = 0
        if TIMELINE_ARTIFACT in archive.namelist():
            timeline = _read_json(
                archive,
                TIMELINE_ARTIFACT,
            )
            summary = timeline.get("summary")
            if isinstance(summary, dict):
                user_actions = int(
                    summary.get("user_actions")
                    or 0
                )
            timeline_values = timeline.get(
                "events"
            )
            if isinstance(
                timeline_values,
                list,
            ):
                timeline_events = len(
                    timeline_values
                )

        package = manifest.get("package")
        package_name = (
            str(package.get("name") or "")
            if isinstance(package, dict)
            else ""
        )

    return CompleteResearchAudit(
        archive=verification.archive,
        session_id=verification.session_id,
        package=package_name,
        packet_count=packet_count,
        pcap_first_utc=_iso_from_epoch(pcap_first),
        pcap_last_utc=_iso_from_epoch(pcap_last),
        logcat_entries=logcat_entries,
        logcat_first_utc=_iso_from_epoch(logcat_first),
        logcat_last_utc=_iso_from_epoch(logcat_last),
        screen_frames=frame_count,
        screen_first_frame_utc=(
            first_frame.isoformat().replace("+00:00", "Z")
        ),
        screen_last_frame_utc=(
            last_frame.isoformat().replace("+00:00", "Z")
        ),
        screen_last_frame_gap_seconds=screen_gap,
        screen_capture_started_utc=(
            capture_started.isoformat().replace("+00:00", "Z")
        ),
        screen_capture_stopped_utc=(
            capture_stopped.isoformat().replace("+00:00", "Z")
        ),
        screen_capture_span_seconds=(
            capture_stopped - capture_started
        ).total_seconds(),
        user_actions=user_actions,
        timeline_events=timeline_events,
        max_clock_skew_seconds=observed_clock_skew,
    )
