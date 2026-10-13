"""Phase 3 — Snapshot verifier tests.

Covers:
    * verification OK
    * manifest checksum mismatch detected
    * records checksum mismatch detected
    * malformed metadata rejected
    * schema mismatch rejected
    * missing records file rejected
"""

import hashlib
import json
from pathlib import Path

import pytest

from maritime.snapshot_publisher import (
    canonical_json_bytes,
    publish_json,
    publish_jsonl,
)
from maritime.snapshot_verifier import (
    REQUIRED_MANIFEST_FIELDS,
    REQUIRED_METADATA_FIELDS,
    verify_snapshot_directory,
)


def _manifest_self_checksum(manifest: dict) -> str:
    """Compute the canonical SHA-256 of ``manifest`` minus its own
    ``checksum_manifest`` field. Used to populate the self-referential
    checksum in test fixtures.
    """
    body = dict(manifest)
    body.pop("checksum_manifest", None)
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def _write_snapshot(
    base: Path,
    snapshot_id: str,
    *,
    schema_version: str = "1.0.0",
    manifest_records_checksum: str = "",
    records: list = None,
    extra_required_manifest: dict = None,
    extra_required_metadata: dict = None,
    metadata: dict = None,
    manifest: dict = None,
) -> Path:
    snap = base / "test_dataset" / snapshot_id
    snap.mkdir(parents=True, exist_ok=True)
    records_path = snap / "traffic_density.jsonl"
    if records is not None:
        summary = publish_jsonl(records_path, records)
        rec_checksum = summary.sha256
    else:
        rec_checksum = ""

    m = {
        "schema_version": schema_version,
        "snapshot_id": snapshot_id,
        "dataset": "test_dataset",
        "source": "TEST",
        "dataset_version": "1",
        "created_at": "2024-01-01T00:00:00+00:00",
        "observed_start": "2024-01-01T00:00:00+00:00",
        "observed_end": "2024-01-02T00:00:00+00:00",
        "record_count": len(records) if records else 0,
        "checksum_records": manifest_records_checksum or rec_checksum,
        "checksum_manifest": "",
    }
    if extra_required_manifest:
        m.update(extra_required_manifest)
    if manifest:
        m.update(manifest)
    # Compute self-checksum using the canonical serializer.
    m["checksum_manifest"] = _manifest_self_checksum(m)
    publish_json(snap / "manifest.json", m)

    md = metadata or {
        "snapshot_id": snapshot_id,
        "source": "TEST",
        "dataset": "test_dataset",
        "created_at": "2024-01-01T00:00:00+00:00",
        "schema_version": schema_version,
        "record_count": len(records) if records else 0,
        "accepted_records": len(records) if records else 0,
        "rejected_records": 0,
        "quality_score": 0.9,
        "source_health": {
            "source": "TEST", "status": "available", "last_check_at": "2024-01-01T00:00:00+00:00",
            "last_success_at": "2024-01-01T00:00:00+00:00", "last_failure_at": None,
            "consecutive_failures": 0, "notes": "",
        },
    }
    if extra_required_metadata:
        md.update(extra_required_metadata)
    publish_json(snap / "metadata.json", md)
    return snap


def test_verification_ok(tmp_path: Path):
    snap = _write_snapshot(tmp_path, "ok-snap", records=[{"a": 1}, {"a": 2}])
    result = verify_snapshot_directory(
        snap, compatible_schema_versions=("1.0.0",)
    )
    assert result.ok is True
    assert result.reasons == []


def test_records_checksum_mismatch(tmp_path: Path):
    # Provide a deliberately wrong checksum.
    snap = _write_snapshot(
        tmp_path,
        "bad-records",
        records=[{"a": 1}],
        manifest_records_checksum="0" * 64,
    )
    result = verify_snapshot_directory(
        snap, compatible_schema_versions=("1.0.0",)
    )
    assert result.ok is False
    assert any("checksum_records_mismatch" in r for r in result.reasons)


def test_manifest_checksum_mismatch(tmp_path: Path):
    snap = _write_snapshot(tmp_path, "ok-snap", records=[{"a": 1}])
    # Tamper with the manifest.
    p = snap / "manifest.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["source"] = "TAMPERED"
    # The canonical re-hash will no longer match the embedded
    # checksum_manifest value.
    p.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")
    result = verify_snapshot_directory(
        snap, compatible_schema_versions=("1.0.0",)
    )
    assert result.ok is False
    assert any("checksum_manifest_mismatch" in r for r in result.reasons)


def test_manifest_missing_fields(tmp_path: Path):
    snap = _write_snapshot(
        tmp_path, "missing", records=[{"a": 1}], extra_required_manifest={"dataset": ""}
    )
    result = verify_snapshot_directory(snap, compatible_schema_versions=("1.0.0",))
    assert result.ok is False
    assert any("manifest_missing_fields" in r for r in result.reasons)


def test_metadata_missing_fields(tmp_path: Path):
    snap = _write_snapshot(
        tmp_path, "missing-meta", records=[{"a": 1}],
        extra_required_metadata={"snapshot_id": ""},
    )
    result = verify_snapshot_directory(snap, compatible_schema_versions=("1.0.0",))
    assert result.ok is False
    assert any("metadata_missing_fields" in r for r in result.reasons)


def test_records_file_missing(tmp_path: Path):
    snap = _write_snapshot(tmp_path, "no-records", records=[])
    (snap / "traffic_density.jsonl").unlink()
    result = verify_snapshot_directory(snap, compatible_schema_versions=("1.0.0",))
    assert result.ok is False
    assert any("records_missing" in r for r in result.reasons)


def test_schema_incompatible(tmp_path: Path):
    snap = _write_snapshot(
        tmp_path, "old-schema", records=[{"a": 1}], schema_version="0.0.1"
    )
    result = verify_snapshot_directory(
        snap, compatible_schema_versions=("1.0.0",)
    )
    assert result.ok is False
    assert any("schema_incompatible" in r for r in result.reasons)


def test_snapshot_id_mismatch_manifest_vs_metadata(tmp_path: Path):
    snap = _write_snapshot(
        tmp_path, "mismatch", records=[{"a": 1}],
        metadata={"snapshot_id": "other-id", "source": "TEST", "dataset": "test_dataset",
                  "created_at": "2024-01-01T00:00:00+00:00", "schema_version": "1.0.0",
                  "record_count": 1, "accepted_records": 1, "rejected_records": 0,
                  "quality_score": 0.9, "source_health": {}},
    )
    result = verify_snapshot_directory(snap, compatible_schema_versions=("1.0.0",))
    assert result.ok is False
    assert any("snapshot_id_mismatch" in r for r in result.reasons)


def test_manifest_unreadable(tmp_path: Path):
    snap = tmp_path / "broken" / "x"
    snap.mkdir(parents=True, exist_ok=True)
    (snap / "manifest.json").write_text("{ not valid json", encoding="utf-8")
    result = verify_snapshot_directory(snap, compatible_schema_versions=("1.0.0",))
    assert result.ok is False
    assert "manifest_unreadable" in result.reasons
