"""Write a bounded Research ZIP HTTPS slice from an independently running analyzer.

The analyzer remains the sole owner of Android proxy/route and its CA. This
adapter owns only the output session's artifacts; it must not stop or restart
the analyzer when recording begins or ends.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from apk_research.collectors.https_interception import HttpsInterceptionCollector
from apk_research.session import SessionManager, SessionStatus


class SharedHttpsRecording:
    NAME = HttpsInterceptionCollector.NAME
    BACKEND = "shared-running-https-analyzer+time-bounded-evidence"

    def __init__(
        self,
        analyzer: HttpsInterceptionCollector,
        session: SessionManager,
        package_name: str,
    ) -> None:
        if analyzer.package_name != package_name:
            raise ValueError("HTTPS analyzer and ZIP target packages differ")
        self.analyzer = analyzer
        self.session = session
        self._begin_offset = 0
        self._start_epoch = 0.0

    def preflight(self):
        if not self.analyzer.running:
            raise RuntimeError("HTTPS analysis must be active before ZIP recording")
        return None

    def start(self) -> None:
        if self.session.status != SessionStatus.STARTING:
            raise RuntimeError("ZIP session is not starting")
        if not self.analyzer.running:
            raise RuntimeError("HTTPS analyzer has stopped")
        self.session.register_collector(
            self.NAME, required=True, backend=self.BACKEND
        )
        entries = (
            ("http_transactions", self.analyzer.TRANSACTIONS_ARTIFACT, False),
            ("http_interception_metadata", self.analyzer.METADATA_ARTIFACT, False),
            ("http_proxy_stderr", self.analyzer.STDERR_ARTIFACT, True),
            ("https_route_diagnostics", self.analyzer.ROUTE_LOG_ARTIFACT, True),
        )
        for kind, name, raw in entries:
            self.session.register_artifact(
                kind=kind, relative_path=name, source=self.NAME, raw=raw,
            )
            self.session.update_collector(
                self.NAME, "starting", artifact_path=name
            )
            out = self.session.paths.root / name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.touch()
        journal = (
            self.analyzer.session.paths.root
            / self.analyzer.TRANSACTIONS_ARTIFACT
        )
        self._begin_offset = journal.stat().st_size if journal.exists() else 0
        self._start_epoch = time.time()
        self.session.update_collector(self.NAME, "running")

    def check_health(self) -> bool:
        return self.analyzer.running

    def stop(self, grace_period: float = 3.0) -> None:
        # A ZIP stop is strictly an evidence snapshot, not Android teardown.
        source_root = self.analyzer.session.paths.root
        output_root = self.session.paths.root
        journal = source_root / self.analyzer.TRANSACTIONS_ARTIFACT
        destination = output_root / self.analyzer.TRANSACTIONS_ARTIFACT
        count = 0
        with destination.open("wb") as out:
            if journal.exists():
                with journal.open("rb") as handle:
                    handle.seek(self._begin_offset)
                    for line in handle:
                        if not line.endswith(b"\n"):
                            break
                        try:
                            item = json.loads(line)
                        except (ValueError, UnicodeDecodeError):
                            continue
                        if not isinstance(item, dict):
                            continue
                        try:
                            timestamp = float(item.get("timestamp_start") or 0)
                        except (ValueError, TypeError):
                            continue
                        if timestamp < self._start_epoch:
                            continue
                        out.write(line)
                        count += 1
                        for part in ("request", "response"):
                            body = (item.get(part) or {}).get("body") or {}
                            if not body.get("present"):
                                continue
                            name = body.get("path")
                            if not isinstance(name, str) or not name or Path(name).name != name:
                                raise RuntimeError("Invalid HTTPS body path")
                            original = source_root / self.analyzer.BODIES_DIR / name
                            copied = output_root / self.analyzer.BODIES_DIR / name
                            copied.parent.mkdir(parents=True, exist_ok=True)
                            if not original.is_file():
                                raise RuntimeError("Recorded HTTPS body is missing: " + name)
                            shutil.copyfile(original, copied)
        for field in (
            self.analyzer.STDERR_ARTIFACT,
            self.analyzer.ROUTE_LOG_ARTIFACT,
        ):
            original = source_root / field
            dest = output_root / field
            if original.is_file():
                shutil.copyfile(original, dest)
        # The route service writes its log inside Android until analyzer stop.
        # Capture a read-only snapshot without changing the active route.
        try:
            route_log = self.analyzer.adb.shell_output(
                self.analyzer._serial,
                "cat", self.analyzer.ROUTE_ROOT + "/route.log",
                timeout=10,
            )
            (output_root / self.analyzer.ROUTE_LOG_ARTIFACT).write_text(
                route_log, encoding="utf-8"
            )
        except Exception:
            pass
        original_meta = source_root / self.analyzer.METADATA_ARTIFACT
        metadata = {}
        if original_meta.is_file():
            try:
                metadata = json.loads(original_meta.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                metadata = {}
        metadata.update({
            "status": "completed",
            "recording_mode": "shared-live-https-analyzer",
            "analyzer_owned_by_recording": False,
            "capture_window_start_epoch": self._start_epoch,
            "capture_window_end_epoch": time.time(),
            "transaction_count": count,
        })
        (output_root / self.analyzer.METADATA_ARTIFACT).write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.session.update_collector(self.NAME, "completed")
