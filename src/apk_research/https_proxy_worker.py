from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from mitmproxy import http, options, version as mitmproxy_version
from mitmproxy.tools.dump import DumpMaster


def _headers(message) -> list[list[str]]:
    return [
        [str(name), str(value)]
        for name, value in message.headers.items(multi=True)
    ]


def _write_json_line(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


class ResearchTransactionRecorder:
    def __init__(
        self,
        transactions_path: Path,
        bodies_dir: Path,
        ready_path: Path,
        error_path: Path,
    ) -> None:
        self.transactions_path = transactions_path
        self.bodies_dir = bodies_dir
        self.ready_path = ready_path
        self.error_path = error_path
        self.transactions_path.parent.mkdir(parents=True, exist_ok=True)
        self.bodies_dir.mkdir(parents=True, exist_ok=True)
        self.sequence = 0

    def running(self) -> None:
        self.transactions_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.bodies_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.ready_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.ready_path.write_text(
            json.dumps(
                {
                    "status": "ready",
                    "mitmproxy_version": mitmproxy_version.VERSION,
                    "pid": os.getpid(),
                    "monotonic_ns": time.monotonic_ns(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def response(self, flow: http.HTTPFlow) -> None:
        self.sequence += 1
        tx_id = f"http-{self.sequence:08d}"
        request_body = self._save_body(
            tx_id,
            "request",
            flow.request,
        )
        response_body = self._save_body(
            tx_id,
            "response",
            flow.response,
        )
        response = flow.response
        request = flow.request
        started = float(request.timestamp_start or 0.0)
        ended = float(
            (
                response.timestamp_end
                if response is not None
                else None
            )
            or time.time()
        )
        value: dict[str, Any] = {
            "schema_version": "0.1",
            "transaction_id": tx_id,
            "flow_id": str(flow.id),
            "state": "response",
            "scheme": request.scheme,
            "http_version": request.http_version,
            "method": request.method,
            "url": request.pretty_url,
            "host": request.host,
            "port": int(request.port),
            "timestamp_start": started,
            "timestamp_end": ended,
            "duration_ms": max(
                0,
                round((ended - started) * 1000, 3),
            ),
            "interception": {
                "active": True,
                "tls_decrypted": request.scheme.lower() == "https",
                "backend": "mitmproxy",
            },
            "request": {
                "headers": _headers(request),
                "body": request_body,
            },
            "response": (
                {
                    "status_code": int(response.status_code),
                    "reason": response.reason,
                    "http_version": response.http_version,
                    "headers": _headers(response),
                    "body": response_body,
                }
                if response is not None
                else None
            ),
        }
        _write_json_line(
            self.transactions_path,
            value,
        )

    def error(self, flow: http.HTTPFlow) -> None:
        request = flow.request
        if request is None:
            return
        self.sequence += 1
        tx_id = f"http-{self.sequence:08d}"
        started = float(request.timestamp_start or time.time())
        value = {
            "schema_version": "0.1",
            "transaction_id": tx_id,
            "flow_id": str(flow.id),
            "state": "error",
            "scheme": request.scheme,
            "http_version": request.http_version,
            "method": request.method,
            "url": request.pretty_url,
            "host": request.host,
            "port": int(request.port),
            "timestamp_start": started,
            "timestamp_end": time.time(),
            "interception": {
                "active": True,
                "tls_decrypted": False,
                "backend": "mitmproxy",
            },
            "request": {
                "headers": _headers(request),
                "body": self._save_body(
                    tx_id,
                    "request",
                    request,
                ),
            },
            "response": None,
            "error": (
                str(flow.error)
                if flow.error is not None
                else "unknown proxy error"
            ),
        }
        _write_json_line(
            self.transactions_path,
            value,
        )

    def _save_body(
        self,
        tx_id: str,
        side: str,
        message,
    ) -> dict[str, Any]:
        if message is None:
            return {
                "present": False,
                "size": 0,
                "path": None,
                "content_type": None,
            }
        try:
            content = message.get_content(strict=False)
        except Exception:
            content = message.raw_content
        if content is None:
            return {
                "present": False,
                "size": 0,
                "path": None,
                "content_type": message.headers.get("content-type"),
            }
        body_path = self.bodies_dir / f"{tx_id}.{side}.body"
        body_path.write_bytes(content)
        relative = body_path.name
        return {
            "present": True,
            "size": len(content),
            "path": relative,
            "content_type": message.headers.get("content-type"),
            "content_encoding": message.headers.get("content-encoding"),
        }


async def _run(args: argparse.Namespace) -> int:
    transactions = Path(args.transactions).resolve()
    bodies = Path(args.bodies).resolve()
    ready = Path(args.ready_file).resolve()
    error = Path(args.error_file).resolve()
    confdir = Path(args.confdir).resolve()
    confdir.mkdir(parents=True, exist_ok=True)
    ready.unlink(missing_ok=True)
    error.unlink(missing_ok=True)

    opts = options.Options(
        listen_host="127.0.0.1",
        listen_port=int(args.listen_port),
        confdir=str(confdir),
        mode=["regular"],
    )
    master = DumpMaster(
        opts,
        with_termlog=False,
        with_dumper=False,
    )
    master.options.update(
        block_global=False,
        block_private=False,
        http2=True,
        http3=False,
        onboarding=False,
    )
    master.addons.add(
        ResearchTransactionRecorder(
            transactions,
            bodies,
            ready,
            error,
        )
    )
    try:
        await master.run()
        return 0
    except BaseException as exc:
        error.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        error.write_text(
            str(exc) or exc.__class__.__name__,
            encoding="utf-8",
        )
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="apk-research HTTPS proxy worker",
    )
    parser.add_argument(
        "--listen-port",
        type=int,
        required=True,
    )
    parser.add_argument(
        "--confdir",
        required=True,
    )
    parser.add_argument(
        "--transactions",
        required=True,
    )
    parser.add_argument(
        "--bodies",
        required=True,
    )
    parser.add_argument(
        "--ready-file",
        required=True,
    )
    parser.add_argument(
        "--error-file",
        required=True,
    )
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
