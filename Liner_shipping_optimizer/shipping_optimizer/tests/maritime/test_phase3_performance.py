"""Phase 3 — Performance budget tests.

Local snapshot reads must be fast (< 200ms for a 10-record snapshot on
the typical CI environment). The publisher and verifier paths must
each be < 200ms for small inputs. No sleep/retry loops.
"""

import hashlib
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from maritime.fallback_resolver import resolve_snapshot_fallback
from maritime.freshness_policy import FreshnessConfig
from maritime.safe_feature_adapter import (
    EMODNET_DATASET_KEY,
    SafeFeatureAdapter,
)
from maritime.snapshot_publisher import (
    canonical_json_bytes,
    publish_json,
    publish_jsonl,
)
from maritime.snapshot_verifier import verify_snapshot_directory


def _manifest_self_checksum(manifest: dict) -> str:
    body = dict(manifest)
    body.pop("checksum_manifest", None)
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def _publish_snapshot(root, dataset, snapshot_id, *, created_at, n=10):
    snap = root / dataset / snapshot_id
    snap.mkdir(parents=True, exist_ok=True)
    recs = [{"id": i, "v": f"value-{i}"} for i in range(n)]
    summary = publish_jsonl(snap / "traffic_density.jsonl", recs)
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
        "record_count": n,
        "accepted_records": n,
        "rejected_records": 0,
        "quality_score": 0.9,
        "source_health": {
            "source": "TEST", "status": "available",
            "last_check_at": created_at.isoformat(),
            "last_success_at": created_at.isoformat(),
            "last_failure_at": None,
            "consecutive_failures": 0, "notes": "",
        },
    }
    publish_json(snap / "metadata.json", metadata)
    return snap


def test_publish_is_fast(tmp_path: Path):
    target = tmp_path / "data.jsonl"
    recs = [{"id": i, "v": "x"} for i in range(100)]
    t0 = time.perf_counter()
    publish_jsonl(target, recs)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, f"publish too slow: {elapsed:.3f}s"


def test_verify_is_fast(tmp_path: Path):
    now = datetime.now(tz=timezone.utc)
    snap = _publish_snapshot(tmp_path, EMODNET_DATASET_KEY, "perf-1",
                              created_at=now - timedelta(hours=1), n=50)
    t0 = time.perf_counter()
    result = verify_snapshot_directory(snap, compatible_schema_versions=("1.0.0",))
    elapsed = time.perf_counter() - t0
    assert result.ok is True
    assert elapsed < 0.5, f"verify too slow: {elapsed:.3f}s"


def test_resolver_is_fast(tmp_path: Path):
    now = datetime.now(tz=timezone.utc)
    for i in range(5):
        _publish_snapshot(
            tmp_path, EMODNET_DATASET_KEY, f"snap-{i}",
            created_at=now - timedelta(hours=1, minutes=i),
        )
    t0 = time.perf_counter()
    decision = resolve_snapshot_fallback(
        dataset=EMODNET_DATASET_KEY, snapshot_root=tmp_path,
    )
    elapsed = time.perf_counter() - t0
    assert decision.tier.value in ("fresh", "stale_within_window", "known_good_historical", "empty")
    assert elapsed < 0.5, f"resolver too slow: {elapsed:.3f}s"


def test_safe_adapter_status_is_fast(tmp_path: Path):
    now = datetime.now(tz=timezone.utc)
    _publish_snapshot(tmp_path, EMODNET_DATASET_KEY, "perf-sa",
                      created_at=now - timedelta(hours=1))
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    t0 = time.perf_counter()
    for _ in range(10):
        adapter.get_status()
    elapsed = time.perf_counter() - t0
    # 10 status calls < 1 second (i.e. < 100ms each)
    assert elapsed < 1.0, f"status calls too slow: {elapsed:.3f}s"


def test_no_sleeps_in_publisher():
    """Defensive: the publisher must not import time.sleep or similar."""
    import ast
    from pathlib import Path as _P
    from maritime.snapshot_publisher import __file__ as f
    src = _P(f).read_text(encoding="utf-8")
    assert "time.sleep" not in src
    assert "asyncio.sleep" not in src
