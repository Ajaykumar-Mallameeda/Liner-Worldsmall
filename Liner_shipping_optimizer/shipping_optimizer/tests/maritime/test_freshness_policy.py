"""Phase 3 — Freshness policy tests."""

import os
from datetime import datetime, timezone, timedelta

import pytest

from maritime.freshness_policy import (
    FreshnessConfig,
    FreshnessState,
    evaluate,
)


def test_unknown_when_no_created_at():
    e = evaluate(
        snapshot_created_at=None, quality_score=0.9, verification_ok=True
    )
    # No created_at -> OFFLINE (not AVAILABLE), per the policy.
    assert e.state == FreshnessState.OFFLINE


def test_unparseable_created_at_is_invalid():
    e = evaluate(
        snapshot_created_at="not-a-date", quality_score=0.9, verification_ok=True
    )
    assert e.state == FreshnessState.INVALID


def test_fresh_when_age_below_threshold():
    cfg = FreshnessConfig(fresh_after_seconds=3600, stale_after_seconds=86400)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    created = (now - timedelta(minutes=10)).isoformat()
    e = evaluate(
        snapshot_created_at=created, quality_score=0.9, verification_ok=True,
        config=cfg, now=now,
    )
    assert e.state == FreshnessState.AVAILABLE
    assert e.is_fresh is True


def test_degraded_when_fresh_but_low_quality():
    cfg = FreshnessConfig(fresh_after_seconds=3600, stale_after_seconds=86400, degraded_quality_floor=0.5)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    created = (now - timedelta(minutes=10)).isoformat()
    e = evaluate(
        snapshot_created_at=created, quality_score=0.3, verification_ok=True,
        config=cfg, now=now,
    )
    assert e.state == FreshnessState.DEGRADED
    assert e.is_degraded_quality is True


def test_stale_when_age_above_stale_threshold():
    cfg = FreshnessConfig(fresh_after_seconds=3600, stale_after_seconds=86400)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    created = (now - timedelta(days=2)).isoformat()
    e = evaluate(
        snapshot_created_at=created, quality_score=0.9, verification_ok=True,
        config=cfg, now=now,
    )
    assert e.state == FreshnessState.STALE
    assert e.is_stale is True


def test_verification_failure_is_invalid():
    e = evaluate(
        snapshot_created_at="2024-01-01T00:00:00+00:00",
        quality_score=0.9, verification_ok=False,
    )
    assert e.state == FreshnessState.INVALID


def test_future_created_at_is_invalid():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    future = (now + timedelta(minutes=10)).isoformat()
    e = evaluate(
        snapshot_created_at=future, quality_score=0.9, verification_ok=True,
        now=now,
    )
    assert e.state == FreshnessState.INVALID


def test_between_fresh_and_stale_is_degraded():
    cfg = FreshnessConfig(fresh_after_seconds=3600, stale_after_seconds=86400)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    # 2 hours old -> between fresh and stale
    created = (now - timedelta(hours=2)).isoformat()
    e = evaluate(
        snapshot_created_at=created, quality_score=0.9, verification_ok=True,
        config=cfg, now=now,
    )
    assert e.state == FreshnessState.DEGRADED


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("MARITIME_FRESH_AFTER_SECONDS", "100")
    monkeypatch.setenv("MARITIME_STALE_AFTER_SECONDS", "200")
    monkeypatch.setenv("MARITIME_DEGRADED_QUALITY_FLOOR", "0.7")
    cfg = FreshnessConfig.from_env()
    assert cfg.fresh_after_seconds == 100
    assert cfg.stale_after_seconds == 200
    assert cfg.degraded_quality_floor == 0.7


def test_evaluation_to_dict():
    e = evaluate(snapshot_created_at=None, quality_score=None, verification_ok=False)
    d = e.to_dict()
    assert "state" in d
    assert "age_seconds" in d
    assert "is_fresh" in d
    assert "is_stale" in d
    assert "is_degraded_quality" in d
    assert "notes" in d
