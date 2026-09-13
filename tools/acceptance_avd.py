from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from mobile_research.export import verify_research_zip
from mobile_research.orchestrator import OrchestratorError, ResearchOrchestrator
from mobile_research.targets import AdbClient, AdbError


SERIAL = "emulator-5554"
PACKAGE = "com.android.settings"
OUTPUT_ROOT = Path("acceptance-output").resolve()
SESSION_ROOT = OUTPUT_ROOT / "sessions"
ARCHIVE = OUTPUT_ROOT / "mobile-research-acceptance.research.zip"


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    client = AdbClient.from_environment()

    orchestrator = ResearchOrchestrator(
        client,
        SERIAL,
        PACKAGE,
        runtime_root=SESSION_ROOT,
        output_path=ARCHIVE,
        overwrite_output=True,
        screen_chunk_seconds=30,
    )

    try:
        started = orchestrator.start()
        print(json.dumps({"event": "started", **started.to_dict()}, ensure_ascii=False))

        try:
            ping_output = client.shell_output(
                SERIAL,
                "ping",
                "-c",
                "2",
                "8.8.8.8",
                timeout=20.0,
            )
            print(json.dumps({
                "event": "network_probe",
                "status": "ok",
                "output": ping_output[-1000:],
            }, ensure_ascii=False))
        except AdbError as exc:
            print(json.dumps({
                "event": "network_probe",
                "status": "failed",
                "error": str(exc),
            }, ensure_ascii=False))

        time.sleep(3)
        health = orchestrator.health_check()
        print(json.dumps({"event": "health", **health.to_dict()}, ensure_ascii=False))

        result = orchestrator.stop_and_export()
        print(json.dumps({"event": "stopped", **result.to_dict()}, ensure_ascii=False))

        verification = verify_research_zip(result.archive)
        print(json.dumps({"event": "verified", **verification.to_dict()}, ensure_ascii=False))

        if result.session_status != "complete":
            raise RuntimeError(
                "Real AVD acceptance did not finish complete: "
                f"{result.session_status}"
            )
        if not verification.valid:
            raise RuntimeError("Research ZIP verification failed")

        return 0
    except OrchestratorError as exc:
        print(json.dumps({
            "event": "orchestrator_error",
            "error": str(exc),
            "session_root": str(exc.session_root) if exc.session_root is not None else None,
            "archive": exc.archive,
        }, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
