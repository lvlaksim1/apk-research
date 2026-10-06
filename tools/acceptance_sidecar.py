from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from apk_research.desktop.sidecar import (
    AGENT_VERSION,
    PROTOCOL_VERSION,
    AndroidSidecar,
)
from apk_research.targets import AdbClient

SERIAL = os.environ.get(
    "APK_RESEARCH_ACCEPTANCE_SERIAL",
    "emulator-5554",
)


def main() -> int:
    client = AdbClient.from_environment()
    sidecar = AndroidSidecar(
        client,
        SERIAL,
    )

    try:
        handshake = sidecar.start()
        print(
            json.dumps(
                {
                    "event": "sidecar_started",
                    **handshake.to_dict(),
                },
                ensure_ascii=False,
            )
        )
        if handshake.protocol_version != PROTOCOL_VERSION:
            raise RuntimeError(
                "Sidecar protocol version mismatch"
            )
        if handshake.agent_version != AGENT_VERSION:
            raise RuntimeError(
                "Sidecar agent version mismatch"
            )

        ping = sidecar.ping("avd-acceptance")
        print(
            json.dumps(
                {
                    "event": "sidecar_ping",
                    **ping.to_dict(),
                },
                ensure_ascii=False,
            )
        )
        if ping.token != "avd-acceptance":
            raise RuntimeError(
                "Sidecar PING/PONG token mismatch"
            )

        cleanup = sidecar.stop()
        print(
            json.dumps(
                {
                    "event": "sidecar_stopped",
                    **cleanup.to_dict(),
                },
                ensure_ascii=False,
            )
        )
        if not cleanup.complete:
            raise RuntimeError(
                "Sidecar cleanup was incomplete"
            )
        return 0
    except Exception as exc:
        try:
            if sidecar.running:
                sidecar.stop()
        except Exception:
            pass
        print(
            json.dumps(
                {
                    "event": "sidecar_error",
                    "error": str(exc)
                    or exc.__class__.__name__,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
