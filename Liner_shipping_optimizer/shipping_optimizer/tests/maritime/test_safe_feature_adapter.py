"""Phase 3 — Safe feature adapter tests.

Covers:
    * flag-off -> empty payload, no I/O
    * no snapshot -> empty payload
    * fresh snapshot -> payload with fresh state
    * stale snapshot -> payload with stale state
    * invalid snapshot -> payload with invalid state
    * status endpoint shape
    * never raises under any combination
    * telemetry emitted
"""

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from maritime import telemetry
from maritime.fallback_resolver import FallbackTier
from maritime.freshness_policy import FreshnessState
from maritime.safe_feature_adapter import (
    EMODNET_DATASET_KEY,
    NOAA_DATASET_KEY,
    ResilientReadResult,
    SafeFeatureAdapter,
)
from maritime.snapshot_publisher import (
    canonical_json_bytes,
    publish_json,
    publish_jsonl,
)


def _manifest_self_checksum(manifest: dict) -> str:
    body = dict(manifest)
    body.pop("checksum_manifest", None)
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def _publish_snapshot(root, dataset, snapshot_id, *, created_at, quality=0.9):
    snap = root / dataset / snapshot_id
    snap.mkdir(parents=True, exist_ok=True)
    summary = publish_jsonl(snap / "traffic_density.jsonl", [{"id": 1, "v": "x"}])
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
    return snap


@pytest.fixture(autouse=True)
def _reset_telemetry():
    telemetry.reset_events()
    yield
    telemetry.reset_events()


def test_flag_off_returns_empty(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("MARITIME_INTELLIGENCE_ENABLED", raising=False)
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    assert adapter.is_master_enabled() is False
    res = adapter.get_traffic_snapshot()
    assert res.decision.tier == FallbackTier.EMPTY
    assert res.records == []
    assert res.payload["enabled"] is False


def test_no_snapshot_returns_empty(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_TRAFFIC_ENABLED", "1")
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    res = adapter.get_traffic_snapshot()
    assert res.decision.tier == FallbackTier.EMPTY
    assert res.records == []


def test_fresh_snapshot_picked(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_TRAFFIC_ENABLED", "1")
    now = datetime.now(tz=timezone.utc)
    _publish_snapshot(tmp_path, EMODNET_DATASET_KEY, "fresh-1",
                      created_at=now - timedelta(hours=1))
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    res = adapter.get_traffic_snapshot()
    assert res.decision.tier == FallbackTier.FRESH
    assert res.payload["fresh"] is True
    assert res.payload["state"] == FreshnessState.AVAILABLE.value
    assert res.payload["snapshot_id"] == "fresh-1"
    assert len(res.records) == 1


def test_stale_snapshot_picked(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_TRAFFIC_ENABLED", "1")
    now = datetime.now(tz=timezone.utc)
    _publish_snapshot(tmp_path, EMODNET_DATASET_KEY, "stale-1",
                      created_at=now - timedelta(days=10))
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    res = adapter.get_traffic_snapshot()
    # 10 days old: fresh_after=7d, stale_after=30d -> STALE_WITHIN_WINDOW
    assert res.decision.tier == FallbackTier.STALE_WITHIN_WINDOW
    assert res.payload["fresh"] is False
    assert res.payload["state"] in (FreshnessState.STALE.value, FreshnessState.DEGRADED.value)


def test_status_shape(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    status = adapter.get_status()
    assert "enabled" in status
    assert "traffic" in status
    assert "port" in status
    assert status["traffic"]["state"] == FreshnessState.OFFLINE.value
    assert status["port"]["state"] == FreshnessState.OFFLINE.value


def test_source_health_shape(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    h = adapter.get_source_health()
    assert h["enabled"] is True
    assert "traffic" in h
    assert "port" in h
    assert h["traffic"]["state"] == FreshnessState.OFFLINE.value
    assert "evaluated_at" in h


def test_telemetry_emitted(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_TRAFFIC_ENABLED", "1")
    now = datetime.now(tz=timezone.utc)
    _publish_snapshot(tmp_path, EMODNET_DATASET_KEY, "x",
                      created_at=now - timedelta(hours=1))
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    adapter.get_traffic_snapshot()
    events = [e["event"] for e in telemetry.get_events()]
    assert "maritime_snapshot_read" in events


def test_never_raises_with_garbage_directory(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_TRAFFIC_ENABLED", "1")
    # Place a non-directory where the dataset would be
    (tmp_path / EMODNET_DATASET_KEY).write_text("not a dir", encoding="utf-8")
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    res = adapter.get_traffic_snapshot()
    # Resolver catches the OSError and returns EMPTY
    assert res.decision.tier == FallbackTier.EMPTY


def test_port_flag_off_returns_empty(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.delenv("MARITIME_PORT_INTELLIGENCE_ENABLED", raising=False)
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    res = adapter.get_port_snapshot()
    assert res.decision.tier == FallbackTier.EMPTY
    assert res.records == []


def test_port_snapshot_uses_noaa_dataset_key(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_PORT_INTELLIGENCE_ENABLED", "1")
    now = datetime.now(tz=timezone.utc)
    _publish_snapshot(tmp_path, NOAA_DATASET_KEY, "p-1",
                      created_at=now - timedelta(hours=1))
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    res = adapter.get_port_snapshot()
    assert res.decision.snapshot_dir is not None
    assert res.decision.snapshot_dir.name == "p-1"


def test_invalid_payload_does_not_leak(monkeypatch, tmp_path: Path):
    """A corrupted snapshot must NEVER be reported as fresh."""
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_TRAFFIC_ENABLED", "1")
    now = datetime.now(tz=timezone.utc)
    snap = _publish_snapshot(tmp_path, EMODNET_DATASET_KEY, "bad",
                              created_at=now - timedelta(hours=1))
    # Corrupt the manifest
    p = snap / "manifest.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["source"] = "X"
    p.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    res = adapter.get_traffic_snapshot()
    # The corrupted snapshot cannot be the chosen tier.
    assert res.decision.tier in (FallbackTier.EMPTY, FallbackTier.KNOWN_GOOD_HISTORICAL)
    # In either case, fresh must be False.
    assert res.payload["fresh"] is False
