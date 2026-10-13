"""Tests for provenance + the source-health state machine."""

import pytest

from maritime.schemas.intelligence import SourceHealth, SourceStatus
from maritime import source_health


def test_initial_state_is_unknown():
    h = source_health.initial("EMODNET")
    assert h.source == "EMODNET"
    assert h.status == SourceStatus.UNKNOWN
    assert h.consecutive_failures == 0


def test_check_start_moves_to_checking():
    h = source_health.initial("EMODNET")
    h = source_health.transition(h, event="check_start", success=True)
    assert h.status == SourceStatus.CHECKING


def test_check_ok_moves_to_available():
    h = source_health.initial("EMODNET")
    h = source_health.transition(h, event="check_ok", success=True)
    assert h.status == SourceStatus.AVAILABLE
    assert h.consecutive_failures == 0
    assert h.last_success_at is not None


def test_single_failure_moves_to_degraded():
    h = source_health.initial("EMODNET")
    h = source_health.transition(h, event="check_ok", success=True)
    h = source_health.transition(h, event="check_failed", success=False)
    assert h.status == SourceStatus.DEGRADED
    assert h.consecutive_failures == 1


def test_three_failures_moves_to_offline():
    h = source_health.initial("EMODNET")
    for _ in range(3):
        h = source_health.transition(h, event="check_failed", success=False)
    assert h.status == SourceStatus.OFFLINE
    assert h.consecutive_failures == 3


def test_snapshot_loaded_resets_failures():
    h = source_health.initial("EMODNET")
    h = source_health.transition(h, event="check_failed", success=False)
    h = source_health.transition(h, event="check_failed", success=False)
    assert h.consecutive_failures == 2
    h = source_health.transition(h, event="snapshot_loaded", success=True)
    assert h.status == SourceStatus.AVAILABLE
    assert h.consecutive_failures == 0


def test_snapshot_missing_moves_to_offline():
    h = source_health.initial("EMODNET")
    h = source_health.transition(h, event="snapshot_missing", success=False)
    assert h.status == SourceStatus.OFFLINE


def test_snapshot_stale_moves_to_stale():
    h = source_health.initial("EMODNET")
    h = source_health.transition(h, event="snapshot_loaded", success=True)
    h = source_health.transition(h, event="snapshot_stale", success=False)
    assert h.status == SourceStatus.STALE


def test_no_false_live_state():
    """EMODnet data is a historical density product; the state machine
    must never report a LIVE status."""
    h = source_health.initial("EMODNET")
    for ev in ("check_start", "check_ok", "snapshot_loaded"):
        h = source_health.transition(h, event=ev, success=True)
    assert h.status != "live"
    assert h.status != SourceStatus.UNKNOWN
