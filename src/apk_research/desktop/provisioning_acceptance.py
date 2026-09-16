from __future__ import annotations

import json
import os
import subprocess
import traceback
from datetime import datetime, timezone
from pathlib import Path

from apk_research.desktop.components import ComponentManager


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _run(
    command: list[str],
    *,
    env: dict[str, str],
    timeout: float = 60.0,
) -> dict[str, object]:
    creation_flags = getattr(
        subprocess,
        "CREATE_NO_WINDOW",
        0,
    )
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=env,
        creationflags=creation_flags,
    )
    payload = {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed: "
            + " ".join(command)
            + "\n"
            + (result.stderr.strip() or result.stdout.strip())
        )
    return payload


def run_provisioning_acceptance() -> int:
    root = Path(
        os.environ.get(
            "APK_RESEARCH_ACCEPTANCE_ROOT",
            Path.cwd() / "windows-provisioning-acceptance",
        )
    ).resolve()
    component_root = Path(
        os.environ.get(
            "APK_RESEARCH_COMPONENT_ROOT",
            root / "components",
        )
    ).resolve()
    result_path = Path(
        os.environ.get(
            "APK_RESEARCH_ACCEPTANCE_RESULT",
            root / "result.json",
        )
    ).resolve()

    root.mkdir(parents=True, exist_ok=True)
    result_path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, object] = {
        "status": "running",
        "started_utc": _utc_now(),
        "component_root": str(component_root),
    }

    manager = ComponentManager(component_root)

    try:
        state = manager.ensure_all()
        payload["component_state"] = state.to_dict()
        payload["paths"] = manager.paths.to_dict()

        if not state.ready:
            raise RuntimeError(
                "Managed Android components are not ready"
            )

        env = manager.environment()
        commands = {
            "adb_version": _run(
                [str(manager.paths.adb), "version"],
                env=env,
            ),
            "aapt2_version": _run(
                [str(manager.paths.aapt2), "version"],
                env=env,
            ),
            "emulator_version": _run(
                [str(manager.paths.emulator), "-version"],
                env=env,
            ),
            "avd_list": _run(
                [str(manager.paths.emulator), "-list-avds"],
                env=env,
            ),
        }
        payload["commands"] = commands

        avd_stdout = str(commands["avd_list"]["stdout"])
        if "apk_research_api35" not in avd_stdout.splitlines():
            raise RuntimeError(
                "Private apk-research AVD was not listed by Emulator"
            )

        metadata_path = component_root / "components.json"
        if not metadata_path.is_file():
            raise RuntimeError(
                "components.json was not created"
            )
        payload["components_metadata"] = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )

        payload["status"] = "success"
        payload["finished_utc"] = _utc_now()
        exit_code = 0
    except Exception as exc:
        payload["status"] = "failure"
        payload["finished_utc"] = _utc_now()
        payload["error"] = str(exc) or exc.__class__.__name__
        payload["traceback"] = traceback.format_exc()
        exit_code = 1

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
