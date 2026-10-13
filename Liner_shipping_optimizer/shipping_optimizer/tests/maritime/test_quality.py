"""Tests for the quality system (completeness, freshness, scoring)."""

from datetime import datetime, timedelta, timezone

import pytest

from maritime.quality.completeness import (
    RejectionCounters,
    compute_completeness_ratio,
    compute_quality_score,
)
from maritime.quality.freshness import compute_freshness, is_stale
from maritime.quality.provenance import build_provenance, validate_provenance


def test_rejection_counters_total_problems():
    c = RejectionCounters(invalid_coordinates=2, invalid_values=1, other_errors=3)
    assert c.total_problems == 6


def test_completeness_ratio_no_records():
    assert compute_completeness_ratio(RejectionCounters()) == 1.0


def test_completeness_ratio_basic():
    c = RejectionCounters(records_seen=10, records_accepted=8, records_rejected=2)
    assert compute_completeness_ratio(c) == 0.8


def test_quality_score_no_records():
    assert compute_quality_score(RejectionCounters()) == 0.0


def test_quality_score_perfect():
    c = RejectionCounters(records_seen=10, records_accepted=10, records_rejected=0)
    score = compute_quality_score(c, avg_record_quality=1.0)
    assert 0.99 <= score <= 1.0


def test_quality_score_low_completeness():
    c = RejectionCounters(records_seen=10, records_accepted=3, records_rejected=7)
    score = compute_quality_score(c, avg_record_quality=1.0)
    # 0.7 * 0.3 + 0.3 * 1.0 = 0.51; assert that low completeness lowers score.
    assert score < 0.6


def test_freshness_recent_historical():
    now = datetime(2024, 6, 1, tzinfo=timezone.utc)
    created = "2024-05-30T00:00:00+00:00"
    f = compute_freshness(created, is_historical=True, now=now)
    assert f.is_historical is True
    assert f.is_stale is False


def test_freshness_old_historical_is_stale():
    now = datetime(2024, 12, 1, tzinfo=timezone.utc)
    created = "2024-01-01T00:00:00+00:00"
    f = compute_freshness(created, is_historical=True, now=now, stale_after_seconds=86400)
    assert f.is_stale is True


def test_is_stale_helper():
    now = datetime(2024, 6, 1, tzinfo=timezone.utc)
    created = "2020-01-01T00:00:00+00:00"
    assert is_stale(created, stale_after_seconds=86400) is True


def test_build_provenance_required_keys():
    p = build_provenance(
        source="EMODNET",
        dataset="x",
        dataset_version="1",
        retrieved_at="2024-01-01T00:00:00+00:00",
        observed_period={"start": "2024-01-01T00:00:00+00:00", "end": "2024-01-02T00:00:00+00:00"},
        license_str="CC BY 4.0",
        attribution="EMODnet",
    )
    ok, reason = validate_provenance(p)
    assert ok, reason


def test_validate_provenance_missing_key():
    p = {"source": "EMODNET"}
    ok, reason = validate_provenance(p)
    assert not ok
    assert "dataset" in reason


def test_validate_provenance_empty_value():
    p = {
        "source": "EMODNET", "dataset": "x", "dataset_version": "1",
        "retrieved_at": "",
        "observed_period": {"start": "a", "end": "b"},
    }
    # retrieved_at is empty => invalid
    ok, reason = validate_provenance(p)
    assert not ok
    assert "retrieved_at" in reason
