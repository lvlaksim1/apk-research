from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from apk_research.collectors import (
    HTTPS_INTERCEPTION_ARTIFACT,
    HTTPS_TRANSACTIONS_ARTIFACT,
    HttpsInterceptCollector,
)
from apk_research.session import SessionManager, SessionPaths
from apk_research.targets import AdbClient


class _StagingSession:
    """Minimal session-shaped target used before the real session exists."""

    def __init__(self, root: Path) -> None:
        self.paths = SessionPaths.for_root(root)
        self.paths.create_layout()

    def register_artifact(self, **_kwargs: Any) -> None:
        return


class StagedHttpsCapture:
    """Start HTTPS interception before launch and attach it to a real session."""

    def __init__(
        self,
        adb: AdbClient,
        serial: str,
        package_name: str,
    ) -> None:
        parent = (
            Path(tempfile.gettempdir())
            / "apk-research"
            / "https-staging"
        )
        parent.mkdir(parents=True, exist_ok=True)
        self.root = Path(
            tempfile.mkdtemp(
                prefix="capture-",
                dir=parent,
            )
        )
        self.staging_session = _StagingSession(self.root)
        self.collector = HttpsInterceptCollector(
            adb,
            self.staging_session,  # type: ignore[arg-type]
            serial,
            package_name,
        )
        self._stopped = False

    def start(self) -> None:
        self.collector.start()

    def stop(self) -> dict[str, object]:
        if self._stopped:
            return {}
        try:
            result = self.collector.stop()
            self._stopped = True
            return result.to_dict()
        except Exception:
            self._best_effort_cleanup()
            self._stopped = True
            raise

    def _best_effort_cleanup(self) -> None:
        try:
            self.collector.restore_environment(
                best_effort=True,
            )
        except Exception:
            pass
        try:
            self.collector.shutdown_proxy(
                grace_period=3.0,
            )
        except Exception:
            pass

    def attach_to_session(
        self,
        session: SessionManager,
    ) -> None:
        artifacts = (
            (
                HTTPS_INTERCEPTION_ARTIFACT,
                "https_interception",
            ),
            (
                HTTPS_TRANSACTIONS_ARTIFACT,
                "http_transactions",
            ),
        )
        for relative_path, kind in artifacts:
            source = self.root / relative_path
            if not source.is_file():
                continue
            target = session.paths.root / relative_path
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            shutil.copy2(source, target)
            session.register_artifact(
                kind=kind,
                relative_path=relative_path,
                source="https-intercept",
                raw=False,
            )

    def cleanup(self) -> None:
        shutil.rmtree(
            self.root,
            ignore_errors=True,
        )
