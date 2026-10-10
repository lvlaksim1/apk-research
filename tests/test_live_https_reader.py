from __future__ import annotations

import json
from pathlib import Path

from apk_research.desktop.live_https_reader import IncrementalHttpReader


def record(n: int) -> bytes:
    return json.dumps(
        {"transaction_id": f"http-{n:08d}", "url": f"https://example.com/{n}"},
        ensure_ascii=False,
    ).encode("utf-8") + b"\n"


def test_feed_reads_complete_lines_without_duplication(tmp_path: Path) -> None:
    journal = tmp_path / "http-transactions.jsonl"
    reader = IncrementalHttpReader(journal)
    assert reader.poll() == []
    first = record(1)
    journal.write_bytes(first[:14])
    assert reader.poll() == []
    with journal.open("ab") as stream:
        stream.write(first[14:] + record(2))
    rows = reader.poll()
    assert [x["transaction_id"] for x in rows] == [
        "http-00000001", "http-00000002"
    ]
    assert reader.poll() == []
    with journal.open("ab") as stream:
        stream.write(record(3))
    assert [x["transaction_id"] for x in reader.poll()] == ["http-00000003"]


def test_feed_skips_malformed_but_keeps_later_records(tmp_path: Path) -> None:
    journal = tmp_path / "http-transactions.jsonl"
    journal.write_bytes(record(1) + b"not-json\n" + record(2))
    reader = IncrementalHttpReader(journal)
    assert len(reader.poll()) == 2
    assert reader.invalid_records == 1


def test_feed_detects_truncated_journal(tmp_path: Path) -> None:
    journal = tmp_path / "http-transactions.jsonl"
    journal.write_bytes(record(1) + record(2))
    reader = IncrementalHttpReader(journal)
    assert len(reader.poll()) == 2
    journal.write_bytes(record(3))
    results = reader.poll()
    assert [x["transaction_id"] for x in results] == ["http-00000003"]


def test_feed_large_journal_never_loses_records(tmp_path: Path) -> None:
    journal = tmp_path / "http-transactions.jsonl"
    expected = 9000
    journal.write_bytes(b"".join(record(i) for i in range(expected)))
    reader = IncrementalHttpReader(journal)
    results = []
    for _ in range(10):
        results.extend(reader.poll())
        if len(results) == expected:
            break
    assert len(results) == expected
    assert len({row["transaction_id"] for row in results}) == expected
    assert reader.invalid_records == 0
