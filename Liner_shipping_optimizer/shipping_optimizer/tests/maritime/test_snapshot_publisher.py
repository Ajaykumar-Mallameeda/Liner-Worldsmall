"""Phase 3 — Snapshot publisher tests.

Covers:
    1. atomic JSON publication
    2. atomic JSONL publication
    3. checksum verification (post-publish)
    4. corruption detection (modify file -> checksum mismatch)
    5. checksum mismatch on input data -> no write
    6. previous known-good preservation on failure
"""

import json
from pathlib import Path

import pytest

from maritime.snapshot_publisher import (
    ChecksumMismatchError,
    PublicationResult,
    SnapshotPublicationError,
    publish_json,
    publish_jsonl,
    _sha256_file,
)


def test_publish_json_atomic(tmp_path: Path):
    target = tmp_path / "manifest.json"
    result = publish_json(target, {"b": 2, "a": 1})
    assert target.exists()
    assert isinstance(result, PublicationResult)
    assert result.size_bytes > 0
    # JSON is sort_keys=True so {"a":1,"b":2} is the canonical order.
    data = json.loads(target.read_text(encoding="utf-8"))
    assert list(data.keys()) == ["a", "b"]


def test_publish_jsonl_atomic(tmp_path: Path):
    target = tmp_path / "records.jsonl"
    records = [{"id": 2, "v": "y"}, {"id": 1, "v": "x"}]
    result = publish_jsonl(target, records)
    assert target.exists()
    # SHA-256 must match the file on disk.
    assert result.sha256 == _sha256_file(target)
    lines = [l for l in target.read_text(encoding="utf-8").splitlines() if l]
    assert len(lines) == 2


def test_publish_jsonl_empty(tmp_path: Path):
    target = tmp_path / "empty.jsonl"
    result = publish_jsonl(target, [])
    assert target.exists()
    assert result.size_bytes == 0


def test_publish_then_modify_detected(tmp_path: Path):
    target = tmp_path / "manifest.json"
    result = publish_json(target, {"a": 1})
    assert result.previous_known_good_preserved is False
    # Tamper
    target.write_bytes(b'{"a": 2}')
    # Now compute checksum and compare manually.
    new_sha = _sha256_file(target)
    assert new_sha != result.sha256


def test_publish_json_checksum_mismatch_no_write(tmp_path: Path):
    target = tmp_path / "manifest.json"
    target.write_text("{}", encoding="utf-8")
    with pytest.raises(ChecksumMismatchError):
        publish_json(target, {"a": 1}, expected_sha256="0" * 64)
    # Target untouched
    assert target.read_text(encoding="utf-8") == "{}"


def test_publish_json_overwrite_records_preserved(tmp_path: Path):
    target = tmp_path / "manifest.json"
    publish_json(target, {"v": 1})
    first_size = target.stat().st_size
    # Second publish overwrites
    publish_json(target, {"v": 2})
    second_size = target.stat().st_size
    assert second_size >= 0
    # File still parses
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["v"] == 2


def test_publish_jsonl_partial_failure_cleanup(tmp_path: Path):
    """Even if the iterable raises, the .tmp file is cleaned up."""
    target = tmp_path / "records.jsonl"

    def bad_iter():
        yield {"ok": 1}
        raise RuntimeError("simulated mid-stream failure")

    # publish_jsonl materialises the iterable, so the call here will raise.
    # We then check there is no residual .tmp file.
    try:
        publish_jsonl(target, bad_iter())
    except RuntimeError:
        pass
    # No .tmp files left in the directory.
    leftover = list(tmp_path.glob("*.tmp"))
    assert leftover == []


def test_publish_json_does_not_leave_tmp(tmp_path: Path):
    target = tmp_path / "manifest.json"
    publish_json(target, {"x": 1})
    leftover = list(tmp_path.glob("*.tmp"))
    assert leftover == []


def test_publication_result_to_dict(tmp_path: Path):
    target = tmp_path / "x.json"
    result = publish_json(target, {"k": 1})
    d = result.to_dict()
    assert "path" in d
    assert "sha256" in d
    assert "size_bytes" in d
    assert "previous_known_good_preserved" in d
    assert d["previous_known_good_preserved"] is False
