"""Incremental reader of growing HTTP transaction journals."""
from __future__ import annotations

import json
from pathlib import Path

POLL_CHUNK_BYTES = 1024 * 1024


class IncrementalHttpReader:
    """Consume complete UTF-8 JSONL records without duplicating partial lines."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.offset = 0
        self.pending = b""
        self.invalid_records = 0

    def poll(self) -> list[dict]:
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            return []
        if size < self.offset:
            self.offset = 0
            self.pending = b""
        try:
            with self.path.open("rb") as stream:
                stream.seek(self.offset)
                chunk = stream.read(POLL_CHUNK_BYTES)
        except OSError:
            return []
        self.offset += len(chunk)
        if not chunk:
            return []
        parts = (self.pending + chunk).split(b"\n")
        self.pending = parts.pop()
        result = []
        for line in parts:
            if not line.strip():
                continue
            try:
                item = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeError):
                self.invalid_records += 1
                continue
            if isinstance(item, dict):
                result.append(item)
        return result
