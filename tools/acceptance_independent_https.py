"""Android 15 acceptance: analyzer persists across independent ZIP recording."""
from __future__ import annotations

import json
import tempfile
import time
import zipfile
from pathlib import Path

from acceptance_https import _build_apk, _run, _sdk_root, PACKAGE, SERIAL
from apk_research.collectors.https_interception import HttpsInterceptionCollector
from apk_research.desktop.shared_https_recording import SharedHttpsRecording
from apk_research.export import verify_research_zip
from apk_research.orchestrator import ResearchOrchestrator
from apk_research.session import SessionManager
from apk_research.targets import AdbClient

RESULT_ROOT = Path("acceptance-output").resolve()
ARCHIVE = RESULT_ROOT / "independent-https.research.zip"


def _count(journal: Path) -> int:
    if not journal.is_file():
        return 0
    return sum(1 for line in journal.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines() if line.strip())


def _wait_for_new(journal: Path, old: int, *, timeout: float = 65) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        count = _count(journal)
        if count >= old + 2:
            return count
        time.sleep(0.5)
    raise RuntimeError(
        "HTTPS analyzer did not receive two new requests after launch"
    )


def main() -> int:
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    adb = AdbClient.from_environment()
    adb_binary = _sdk_root() / "platform-tools" / "adb"
    with tempfile.TemporaryDirectory(prefix="apk-research-live-e2e-") as name:
        folder = Path(name)
        apk = _build_apk(folder)
        _run([
            str(adb_binary), "-s", SERIAL,
            "install", "-r", "-t", "-g", str(apk),
        ], timeout=180)
        source: HttpsInterceptionCollector | None = None
        session: SessionManager | None = None
        try:
            session = SessionManager.create(
                folder / "live",
                target=adb.get_target_details(SERIAL).to_dict(),
                package={"name": PACKAGE},
            )
            session.begin_preflight()
            source = HttpsInterceptionCollector(
                adb, session, package_name=PACKAGE,
            )
            source.preflight()
            session.mark_ready()
            session.begin_start()
            source.start()
            session.mark_active()
            journal = session.paths.root / source.TRANSACTIONS_ARTIFACT
            if ARCHIVE.exists():
                ARCHIVE.unlink()

            # Merely enabling analysis must not create a Research ZIP.
            assert not ARCHIVE.exists()
            adb.clean_launch_package(SERIAL, PACKAGE)
            before = _wait_for_new(journal, 0)
            assert source.running and not ARCHIVE.exists()

            recording = ResearchOrchestrator(
                adb, SERIAL, PACKAGE,
                runtime_root=RESULT_ROOT / "independent-https-sessions",
                output_path=ARCHIVE,
                overwrite_output=True,
                screen_chunk_seconds=30,
                launch_mode="observe",
                https_factory=lambda _adb, rec, package: SharedHttpsRecording(
                    source, rec, package,
                ),
            )
            recording.start()
            assert source.running
            adb.clean_launch_package(SERIAL, PACKAGE)
            during = _wait_for_new(journal, before)
            time.sleep(5)
            if not recording.health_check().healthy:
                raise RuntimeError("Collectors degraded during shared HTTPS capture")
            result = recording.stop_and_export()
            if result.session_status != "complete":
                raise RuntimeError(
                    "Independent ZIP capture was not complete: "
                    + result.session_status
                )
            assert verify_research_zip(ARCHIVE).valid
            with zipfile.ZipFile(ARCHIVE) as archive:
                items = [
                    json.loads(line)
                    for line in archive.read(
                        source.TRANSACTIONS_ARTIFACT
                    ).decode("utf-8").splitlines() if line.strip()
                ]
                meta = json.loads(archive.read(source.METADATA_ARTIFACT))
                launch = archive.read(recording.LAUNCH_ARTIFACT).decode("utf-8")
                assert "Activity launch: not requested" in launch
                assert meta["recording_mode"] == "shared-live-https-analyzer"
                if len(items) < 2:
                    raise RuntimeError(
                        "Recording period did not include two HTTPS responses"
                    )
                assert all(
                    float(x["timestamp_start"])
                    >= meta["capture_window_start_epoch"]
                    for x in items
                )
            if not source.running:
                raise RuntimeError("Stopping the ZIP shut down the analyzer")
            adb.clean_launch_package(SERIAL, PACKAGE)
            after = _wait_for_new(journal, during)
            if after <= during:
                raise RuntimeError("No HTTPS traffic observed after ZIP completion")
            print(json.dumps({
                "event": "independent_https_acceptance",
                "status": "ok",
                "before_record": before,
                "through_record": during,
                "after_record": after,
                "recorded": len(items),
                "archive": str(ARCHIVE),
            }))
            return 0
        finally:
            if session is not None and source is not None:
                try:
                    if session.status.value == "active":
                        session.begin_stop()
                    if not source._finished:
                        source.stop()
                    if session.status.value == "stopping":
                        session.finish()
                except Exception:
                    pass
            try:
                _run([str(adb_binary), "-s", SERIAL, "uninstall", PACKAGE])
            except RuntimeError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
