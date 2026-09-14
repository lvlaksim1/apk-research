from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from mobile_research.desktop.android_runtime import AndroidRuntime
from mobile_research.desktop.components import ComponentManager
from mobile_research.export import (
    audit_complete_research_zip,
    verify_research_zip,
)
from mobile_research.orchestrator import ResearchOrchestrator
from mobile_research.targets import AdbClient


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def run_runtime_acceptance() -> int:
    root = Path(
        os.environ.get(
            "MOBILE_RESEARCH_ACCEPTANCE_ROOT",
            Path.cwd() / "windows-runtime-acceptance",
        )
    ).resolve()
    component_override = os.environ.get(
        "MOBILE_RESEARCH_COMPONENT_ROOT"
    )
    manager = (
        ComponentManager(
            Path(component_override).resolve()
        )
        if component_override
        else ComponentManager()
    )
    component_root = manager.paths.root.resolve()
    result_path = Path(
        os.environ.get(
            "MOBILE_RESEARCH_ACCEPTANCE_RESULT",
            root / "result.json",
        )
    ).resolve()
    sessions_root = root / "sessions"
    archive = root / "windows-runtime.research.zip"
    screenshot = root / "android.png"
    log_path = root / "acceptance.log"
    acceptance_apk_value = os.environ.get(
        "MOBILE_RESEARCH_ACCEPTANCE_APK"
    )
    acceptance_apk = (
        Path(acceptance_apk_value).expanduser().resolve()
        if acceptance_apk_value
        else None
    )
    expected_package = os.environ.get(
        "MOBILE_RESEARCH_ACCEPTANCE_EXPECT_PACKAGE"
    )

    root.mkdir(parents=True, exist_ok=True)
    sessions_root.mkdir(parents=True, exist_ok=True)
    result_path.parent.mkdir(parents=True, exist_ok=True)

    component_root_preexisting = component_root.exists()
    component_root_entries = (
        sorted(path.name for path in component_root.iterdir())
        if component_root_preexisting
        else []
    )
    requirements = {
        "windows": _env_flag(
            "MOBILE_RESEARCH_ACCEPTANCE_REQUIRE_WINDOWS"
        ),
        "frozen_executable": _env_flag(
            "MOBILE_RESEARCH_ACCEPTANCE_REQUIRE_FROZEN"
        ),
        "whpx": _env_flag(
            "MOBILE_RESEARCH_ACCEPTANCE_REQUIRE_WHPX"
        ),
        "clean_components": _env_flag(
            "MOBILE_RESEARCH_ACCEPTANCE_REQUIRE_CLEAN_COMPONENTS"
        ),
    }

    payload: dict[str, object] = {
        "status": "running",
        "started_utc": _utc_now(),
        "component_root": str(component_root),
        "component_root_preexisting": component_root_preexisting,
        "component_root_entries_before": component_root_entries,
        "sessions_root": str(sessions_root),
        "archive": str(archive),
        "requirements": requirements,
        "host": {
            "os_name": os.name,
            "platform": sys.platform,
            "executable": sys.executable,
            "frozen": bool(getattr(sys, "frozen", False)),
        },
    }

    def log(message: str) -> None:
        line = f"{_utc_now()} {message}"
        with log_path.open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(line + "\n")

    def progress(
        message: str,
        current: int | None,
        total: int | None,
    ) -> None:
        if current is None:
            log(message)
            return
        if total:
            log(
                f"{message}: {current}/{total}"
            )

    runtime = AndroidRuntime(manager)
    orchestrator: ResearchOrchestrator | None = None
    stopped = False

    try:
        log("Windows desktop runtime acceptance started")

        if requirements["windows"] and os.name != "nt":
            raise RuntimeError(
                "Windows hardware acceptance requires Windows"
            )

        if (
            requirements["frozen_executable"]
            and not getattr(sys, "frozen", False)
        ):
            raise RuntimeError(
                "Acceptance must run from the packaged MobileResearch.exe"
            )

        expected_executable = os.environ.get(
            "MOBILE_RESEARCH_ACCEPTANCE_EXPECT_EXECUTABLE"
        )
        if expected_executable:
            actual = os.path.normcase(
                str(Path(sys.executable).resolve())
            )
            expected = os.path.normcase(
                str(Path(expected_executable).resolve())
            )
            if actual != expected:
                raise RuntimeError(
                    "Acceptance executable mismatch: "
                    f"expected {expected}, got {actual}"
                )

        if (
            requirements["clean_components"]
            and component_root_entries
        ):
            raise RuntimeError(
                "Managed Android component root was not clean: "
                + ", ".join(component_root_entries)
            )

        if (
            requirements["whpx"]
            and os.environ.get(
                "MOBILE_RESEARCH_SOFTWARE_EMULATOR"
            )
            == "1"
        ):
            raise RuntimeError(
                "WHPX acceptance cannot use software emulation"
            )

        runtime.ensure_ready(progress)
        diagnostics = runtime.diagnostics()
        payload["diagnostics"] = diagnostics

        if requirements["whpx"]:
            acceleration = diagnostics.get("acceleration")
            if (
                not isinstance(acceleration, dict)
                or acceleration.get("available") is not True
                or acceleration.get("provider") != "whpx"
            ):
                raise RuntimeError(
                    "Windows hardware acceptance requires WHPX; "
                    f"diagnostics={acceleration!r}"
                )

        if not diagnostics.get("device_online"):
            raise RuntimeError(
                "Managed Android did not become visible through ADB"
            )
        if diagnostics.get("root") is not True:
            raise RuntimeError(
                "Managed Android does not have root ADB"
            )
        tcpdump = diagnostics.get("tcpdump") or {}
        if (
            not isinstance(tcpdump, dict)
            or tcpdump.get("available") is not True
        ):
            raise RuntimeError(
                "Managed Android does not expose tcpdump"
            )

        frame = runtime.screenshot_png()
        if not frame.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError(
                "Embedded Android framebuffer smoke-test failed"
            )
        screenshot.write_bytes(frame)
        payload["screenshot_bytes"] = len(frame)

        client = AdbClient(runtime.paths.adb)
        package = "com.android.settings"

        if acceptance_apk is not None:
            if not acceptance_apk.is_file():
                raise RuntimeError(
                    "Acceptance APK was not found: "
                    f"{acceptance_apk}"
                )
            digest = hashlib.sha256(
                acceptance_apk.read_bytes()
            ).hexdigest()
            package = runtime.install_apk(
                acceptance_apk,
                progress,
            )
            payload["acceptance_apk"] = {
                "path": str(acceptance_apk),
                "size": acceptance_apk.stat().st_size,
                "sha256": digest,
                "package": package,
                "expected_package": expected_package or "",
            }
            if (
                expected_package
                and package != expected_package
            ):
                raise RuntimeError(
                    "Acceptance APK package mismatch: "
                    f"expected {expected_package}, got {package}"
                )
            log(
                "Acceptance APK installed: "
                f"{package} sha256={digest}"
            )

        if not client.is_package_installed(
            runtime.SERIAL,
            package,
        ):
            raise RuntimeError(
                f"Acceptance package is missing: {package}"
            )

        orchestrator = ResearchOrchestrator(
            client,
            runtime.SERIAL,
            package,
            runtime_root=sessions_root,
            output_path=archive,
            overwrite_output=True,
            screen_chunk_seconds=30,
        )
        started = orchestrator.start()
        payload["session"] = started.to_dict()
        log(
            "Research session active: "
            f"{started.session_id}"
        )

        health_samples: list[dict[str, object]] = []
        for index in range(4):
            try:
                client.shell_output(
                    runtime.SERIAL,
                    "ping",
                    "-c",
                    "1",
                    "8.8.8.8",
                    timeout=12.0,
                )
            except Exception as exc:
                log(
                    "Network probe diagnostic: "
                    f"{exc}"
                )

            runtime.swipe(
                540,
                1450,
                540,
                600,
                280,
            )
            time.sleep(2.0)
            health = orchestrator.health_check()
            health_samples.append(
                health.to_dict()
            )
            log(
                "Health sample "
                f"{index + 1}: "
                f"{health.healthy}"
            )

        payload["health_samples"] = health_samples
        result = orchestrator.stop_and_export()
        stopped = True
        payload["stop"] = result.to_dict()

        verification = verify_research_zip(
            archive
        )
        payload["verification"] = (
            verification.to_dict()
        )
        audit = audit_complete_research_zip(
            archive
        )
        payload["audit"] = audit.to_dict()

        if result.session_status != "complete":
            raise RuntimeError(
                "Windows runtime session did not finish complete: "
                f"{result.session_status}"
            )
        if result.validation_issues != 0:
            raise RuntimeError(
                "Windows runtime session has validation issues: "
                f"{result.validation_issues}"
            )
        if not verification.valid:
            raise RuntimeError(
                "Windows runtime Research ZIP verification failed"
            )

        payload["status"] = "success"
        payload["finished_utc"] = _utc_now()
        log("Windows desktop runtime acceptance succeeded")
        exit_code = 0
    except Exception as exc:
        payload["status"] = "failure"
        payload["finished_utc"] = _utc_now()
        payload["error"] = (
            str(exc)
            or exc.__class__.__name__
        )
        payload["traceback"] = traceback.format_exc()
        log(
            "FAILURE: "
            + str(payload["error"])
        )
        exit_code = 1
    finally:
        if (
            orchestrator is not None
            and not stopped
        ):
            try:
                fallback = (
                    orchestrator.stop_and_export()
                )
                payload["fallback_stop"] = (
                    fallback.to_dict()
                )
            except Exception as exc:
                payload["fallback_stop_error"] = str(exc)
        try:
            runtime.stop()
        except Exception as exc:
            payload["runtime_stop_error"] = str(exc)

        result_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    return exit_code
