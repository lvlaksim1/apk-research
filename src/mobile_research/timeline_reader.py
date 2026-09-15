from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from mobile_research.session import SessionManager
from mobile_research.timeline_engine import build_research_timeline


_REQUIRED_PREFIXES = (
    "00_manifest/",
    "01_raw/logcat/",
    "01_raw/network/",
    "02_normalized/",
)


def read_refined_timeline_archive(
    archive_path: str | Path,
) -> dict:
    """Build the current derived timeline in a temporary workspace."""

    archive_path = Path(archive_path)
    with tempfile.TemporaryDirectory(
        prefix="mobile-research-timeline-"
    ) as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                name = info.filename.replace("\\", "/")
                if not name.startswith(_REQUIRED_PREFIXES):
                    continue
                target = (root / name).resolve()
                if root.resolve() not in target.parents:
                    continue
                target.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                target.write_bytes(
                    archive.read(info)
                )

        session = SessionManager.load(root)
        return build_research_timeline(
            session
        )
