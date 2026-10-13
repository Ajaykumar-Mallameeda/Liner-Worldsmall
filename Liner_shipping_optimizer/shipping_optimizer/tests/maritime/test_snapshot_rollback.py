"""Phase 3 — Snapshot rollback tests.

Covers:
    * rollback to a verified snapshot
    * rollback skips corrupted snapshots
    * rollback plan reports candidate counts
"""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from maritime.freshness_policy import FreshnessConfig
from maritime.snapshot_publisher import (
    canonical_json_bytes,
    publish_json,
    publish_jsonl,
)
from maritime.snapshot_rollback import plan_rollback


def _manifest_self_checksum(manifest: dict) -> str:
    body = dict(manifest)
    body.pop("checksum_manifest", None)
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def _publish_snapshot(root, dataset, snapshot_id, *, created_at, quality=0.9, corrupt=False):
    snap = root / dataset / snapshot_id
    snap.mkdir(parents=True, exist_ok=True)
    summary = publish_jsonl(snap / "traffic_density.jsonl", [{"id": 1}])
    manifest = {
        "schema_version": "1.0.0",
        "snapshot_id": snapshot_id,
        "dataset": dataset,
        "source": "TEST",
        "created_at": created_at.isoformat(),
        "checksum_records": summary.sha256,
        "checksum_manifest": "",
    }
    manifest["checksum_manifest"] = _manifest_self_checksum(manifest)
    publish_json(snap / "manifest.json", manifest)
    metadata = {
        "snapshot_id": snapshot_id,
        "source": "TEST",
        "dataset": dataset,
        "created_at": created_at.isoformat(),
        "schema_version": "1.0.0",
        "record_count": 1,
        "accepted_records": 1,
        "rejected_records": 0,
        "quality_score": quality,
        "source_health": {
            "source": "TEST", "status": "available",
            "last_check_at": created_at.isoformat(),
            "last_success_at": created_at.isoformat(),
            "last_failure_at": None,
            "consecutive_failures": 0, "notes": "",
        },
    }
    publish_json(snap / "metadata.json", metadata)
    if corrupt:
        # Desync the manifest so verification fails
        p = snap / "manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["source"] = "X"
        p.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")
    return snap


def test_rollback_picks_verified_snapshot(tmp_path: Path):
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    _publish_snapshot(tmp_path, "ds", "good-1", created_at=now - timedelta(hours=1))
    plan = plan_rollback(dataset="ds", snapshot_root=tmp_path)
    assert plan.candidates_considered == 1
    assert plan.candidates_verified == 1
    assert plan.candidates_rejected == 0
    assert plan.decision.snapshot_dir is not None
    assert plan.decision.snapshot_dir.name == "good-1"


def test_rollback_skips_corrupted_snapshot(tmp_path: Path):
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    _publish_snapshot(tmp_path, "ds", "good-1", created_at=now - timedelta(hours=1))
    _publish_snapshot(tmp_path, "ds", "bad-1", created_at=now - timedelta(hours=2), corrupt=True)
    plan = plan_rollback(dataset="ds", snapshot_root=tmp_path)
    assert plan.candidates_considered == 2
    assert plan.candidates_verified == 1
    assert plan.candidates_rejected == 1


def test_rollback_with_no_candidates(tmp_path: Path):
    plan = plan_rollback(dataset="missing", snapshot_root=tmp_path)
    assert plan.candidates_considered == 0
    assert plan.decision.snapshot_dir is None


def test_plan_to_dict(tmp_path: Path):
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    _publish_snapshot(tmp_path, "ds", "a", created_at=now - timedelta(hours=1))
    plan = plan_rollback(dataset="ds", snapshot_root=tmp_path)
    d = plan.to_dict()
    assert "dataset" in d
    assert "decision" in d
    assert "candidates_considered" in d
    assert "candidates_verified" in d
    assert "candidates_rejected" in d
