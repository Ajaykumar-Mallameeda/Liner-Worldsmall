"""Phase 3 — Fallback resolver tests.

Covers:
    * empty -> tier EMPTY
    * fresh valid -> tier FRESH
    * stale within window -> tier STALE_WITHIN_WINDOW
    * known-good historical -> tier KNOWN_GOOD_HISTORICAL
    * deterministic across runs
    * no verified snapshot -> tier EMPTY
    * safe failure helper
"""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from maritime.fallback_resolver import (
    FallbackTier,
    empty_feature_dict,
    resolve_snapshot_fallback,
    safe_failure_payload,
)
from maritime.freshness_policy import FreshnessConfig
from maritime.schema_registry import SchemaRegistry
from maritime.snapshot_publisher import (
    canonical_json_bytes,
    publish_json,
    publish_jsonl,
)


def _manifest_self_checksum(manifest: dict) -> str:
    body = dict(manifest)
    body.pop("checksum_manifest", None)
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def _publish_snapshot(
    root: Path,
    dataset: str,
    snapshot_id: str,
    *,
    created_at: datetime,
    quality: float = 0.9,
    records: list = None,
):
    snap = root / dataset / snapshot_id
    snap.mkdir(parents=True, exist_ok=True)
    if records is None:
        records = [{"id": 1}]
    summary = publish_jsonl(snap / "traffic_density.jsonl", records)
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
        "record_count": len(records),
        "accepted_records": len(records),
        "rejected_records": 0,
        "quality_score": quality,
        "source_health": {
            "source": "TEST", "status": "available", "last_check_at": created_at.isoformat(),
            "last_success_at": created_at.isoformat(), "last_failure_at": None,
            "consecutive_failures": 0, "notes": "",
        },
    }
    publish_json(snap / "metadata.json", metadata)
    return snap


def test_no_candidates_returns_empty_tier(tmp_path: Path):
    decision = resolve_snapshot_fallback(
        dataset="missing",
        snapshot_root=tmp_path,
    )
    assert decision.tier == FallbackTier.EMPTY
    assert decision.snapshot_dir is None
    assert decision.notes == "no_candidates"


def test_fresh_snapshot_picks_tier_fresh(tmp_path: Path):
    ref = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    _publish_snapshot(tmp_path, "ds", "fresh-1", created_at=ref - timedelta(hours=1))
    decision = resolve_snapshot_fallback(
        dataset="ds", snapshot_root=tmp_path, now=ref,
    )
    assert decision.tier == FallbackTier.FRESH
    assert decision.snapshot_dir is not None
    assert decision.snapshot_dir.name == "fresh-1"


def test_stale_within_window_picks_stale_tier(tmp_path: Path):
    ref = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    # 5 days old -> past fresh (7d) window but within stale (30d) window
    _publish_snapshot(tmp_path, "ds", "stale-1", created_at=ref - timedelta(days=5))
    cfg = FreshnessConfig(fresh_after_seconds=60*60*24, stale_after_seconds=60*60*24*30)
    decision = resolve_snapshot_fallback(
        dataset="ds", snapshot_root=tmp_path, config=cfg, now=ref,
    )
    # 5 days > 1 day (fresh) -> DEGRADED -> tier 2 stale_within_window
    assert decision.tier == FallbackTier.STALE_WITHIN_WINDOW


def test_known_good_historical_picked_when_past_stale_window(tmp_path: Path):
    ref = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    # 100 days old -> past stale (30d) window
    _publish_snapshot(tmp_path, "ds", "old-1", created_at=ref - timedelta(days=100))
    cfg = FreshnessConfig(fresh_after_seconds=3600, stale_after_seconds=60*60*24*30)
    decision = resolve_snapshot_fallback(
        dataset="ds", snapshot_root=tmp_path, config=cfg, now=ref,
    )
    assert decision.tier == FallbackTier.KNOWN_GOOD_HISTORICAL


def test_corrupted_snapshot_is_skipped(tmp_path: Path):
    ref = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    bad = _publish_snapshot(tmp_path, "ds", "bad-1", created_at=ref - timedelta(hours=1))
    # Corrupt the manifest checksum field so verification fails
    p = bad / "manifest.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["source"] = "TAMPERED"  # will desync the self-checksum
    p.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")
    # No verified snapshot -> empty
    decision = resolve_snapshot_fallback(
        dataset="ds", snapshot_root=tmp_path, now=ref,
    )
    assert decision.tier == FallbackTier.EMPTY


def test_deterministic_fallback(tmp_path: Path):
    ref = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    _publish_snapshot(tmp_path, "ds", "a", created_at=ref - timedelta(hours=1))
    _publish_snapshot(tmp_path, "ds", "b", created_at=ref - timedelta(hours=2))
    d1 = resolve_snapshot_fallback(dataset="ds", snapshot_root=tmp_path, now=ref)
    d2 = resolve_snapshot_fallback(dataset="ds", snapshot_root=tmp_path, now=ref)
    assert d1.tier == d2.tier
    assert (d1.snapshot_dir or Path()).name == (d2.snapshot_dir or Path()).name


def test_empty_feature_dict():
    d = empty_feature_dict()
    assert d["enabled"] is False
    assert d["fresh"] is False
    assert d["state"] == "offline"
    assert d["tier"] == "empty"
    assert "no_snapshot" in d["degraded_reasons"]


def test_empty_feature_dict_with_notes():
    d = empty_feature_dict("flag_off")
    assert d["degraded_reasons"] == ["flag_off"]


def test_safe_failure_payload():
    d = safe_failure_payload("network_down")
    assert d["tier"] == "failure"
    assert "network_down" in d["degraded_reasons"]
    assert "safe_failure" in d["degraded_reasons"]


def test_decision_to_dict(tmp_path: Path):
    ref = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    _publish_snapshot(tmp_path, "ds", "a", created_at=ref - timedelta(hours=1))
    d = resolve_snapshot_fallback(dataset="ds", snapshot_root=tmp_path, now=ref)
    serialised = d.to_dict()
    assert "tier" in serialised
    assert "snapshot_dir" in serialised
    assert "freshness" in serialised
    assert "verification" in serialised


def test_schema_incompatible_snapshot_treated_as_corrupt(tmp_path: Path):
    ref = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    snap = _publish_snapshot(tmp_path, "ds", "x", created_at=ref - timedelta(hours=1))
    # Bump schema version to something not in the registry
    p = snap / "manifest.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["schema_version"] = "9.9.9"
    p.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")
    # The new SHA of the manifest will mismatch checksum_manifest in metadata,
    # so the verifier still detects the corruption.
    decision = resolve_snapshot_fallback(dataset="ds", snapshot_root=tmp_path, now=ref)
    # Either schema_incompatible or checksum_manifest_mismatch makes it invalid.
    assert decision.tier in (FallbackTier.EMPTY, FallbackTier.KNOWN_GOOD_HISTORICAL)
