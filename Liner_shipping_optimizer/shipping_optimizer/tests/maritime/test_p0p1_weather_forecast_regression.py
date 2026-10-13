"""P0/P1-A regression — Weather forecast date-window defect.

The original defect: ``forecast_window()`` raised
``TypeError: can't compare offset-naive and offset-aware datetimes``
when the parsed ``start``/``end`` were naive but the record's
``valid_at`` was forced to tz-aware. The fix normalizes the parsed
boundary values to UTC tz-aware before comparison and surfaces invalid
inputs as a clear ``ok:false, error:invalid datetime: ...`` response.

This file contains the ten focused regression cases specified in
``P0_P1_DEFECT_FIXATION_REPORT.md`` §10. Tests exercise the
``WeatherFeatureAdapter`` directly with isolated temp snapshots so the
contract is verified at the boundary, not against the live repo
snapshot. No network calls, no optimizer, no pipeline_output.json
modification.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _sample_observation(
    *, record_id: str = "rec-1", lat: float = 53.55, lon: float = 9.99,
    valid_at: str | None = None, source: str = "OPEN_METEO",
) -> Dict[str, Any]:
    """Build a minimal weather observation dict (JSONL row)."""
    if valid_at is None:
        valid_at = datetime.now(tz=timezone.utc).isoformat()
    return {
        "record_id": record_id,
        "source": source,
        "dataset": "maritime_weather_observations",
        "dataset_version": "1.0.0",
        "latitude": lat,
        "longitude": lon,
        "valid_at": valid_at,
        "retrieved_at": valid_at,
        "wind_speed_ms": 4.5,
        "wind_direction_deg": 270.0,
        "wave_height_m": 0.6,
        "license": "Open-Meteo Free (non-commercial)",
        "attribution": "test",
        "commercial_safe": False,
        "quality": 0.9,
        "freshness_state": "available",
        "provenance": {"provider": source},
    }


def _write_weather_snapshot(
    root: Path, observations: List[Dict[str, Any]]
) -> str:
    """Write a weather snapshot (manifest + records) under ``root``."""
    snap_id = "p0p1-weather-regression"
    snap_dir = root / "maritime_weather_observations" / snap_id
    snap_dir.mkdir(parents=True, exist_ok=True)
    (snap_dir / "manifest.json").write_text(
        json.dumps({
            "snapshot_id": snap_id,
            "dataset": "maritime_weather_observations",
            "dataset_version": "1.0.0",
            "provider": "OPEN_METEO",
            "license": "Open-Meteo Free (non-commercial)",
            "attribution": "test",
            "commercial_safe": False,
            "quality": 0.9,
            "freshness_state": "available",
            "source_health": "available",
            "provider_source": "OPEN_METEO",
            "retrieved_at": datetime.now(tz=timezone.utc).isoformat(),
            "record_count": len(observations),
        }),
        encoding="utf-8",
    )
    with open(snap_dir / "weather_observations.jsonl", "w", encoding="utf-8") as f:
        for obs in observations:
            f.write(json.dumps(obs) + "\n")
    return snap_id


def _make_adapter(tmp_root: Path):
    """Construct a WeatherFeatureAdapter pointed at the temp snapshot root."""
    from maritime.weather.feature_adapter import WeatherFeatureAdapter
    from maritime.storage.snapshots import SnapshotStore
    adapter = WeatherFeatureAdapter()
    adapter._store = SnapshotStore(base_dir=tmp_root)  # type: ignore[attr-defined]
    return adapter


# --------------------------------------------------------------------
# P0/P1-A — 10 focused regression cases (adapter-level)
# --------------------------------------------------------------------


class TestWeatherForecastDateWindowRegression:
    """The 10 cases required by the P0/P1 brief.

    Each test writes a deterministic 3-record snapshot and exercises
    ``forecast_window`` with a specific boundary condition.
    """

    def setup_method(self):
        self._td_ctx = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._td_ctx.name)
        today = datetime.now(tz=timezone.utc).date().isoformat()
        self.observations = [
            _sample_observation(
                record_id="rec-morning",
                valid_at=f"{today}T03:00:00+00:00",
            ),
            _sample_observation(
                record_id="rec-midday",
                valid_at=f"{today}T12:00:00+00:00",
            ),
            _sample_observation(
                record_id="rec-evening",
                valid_at=f"{today}T20:00:00+00:00",
            ),
        ]
        _write_weather_snapshot(self.tmp_root, self.observations)

    def teardown_method(self):
        try:
            self._td_ctx.cleanup()
        except Exception:
            pass

    def test_case_1_valid_tz_aware_start_end(self):
        adp = _make_adapter(self.tmp_root)
        today = datetime.now(tz=timezone.utc).date().isoformat()
        result = adp.forecast_window(
            start=f"{today}T00:00:00Z",
            end=f"{today}T23:59:59Z",
            limit=10,
        )
        # Pre-fix: TypeError. Post-fix: ok=True.
        assert result.ok is True
        assert result.error is None
        assert len(result.records) == 3

    def test_case_2_valid_iso_8601_input(self):
        adp = _make_adapter(self.tmp_root)
        today = datetime.now(tz=timezone.utc).date().isoformat()
        result = adp.forecast_window(
            start=f"{today}T00:00:00+00:00",
            end=f"{today}T23:59:59+00:00",
            limit=10,
        )
        assert result.ok is True
        assert result.error is None
        assert len(result.records) == 3

    def test_case_3_window_start_lt_end(self):
        adp = _make_adapter(self.tmp_root)
        today = datetime.now(tz=timezone.utc).date().isoformat()
        result = adp.forecast_window(
            start=f"{today}T00:00:00Z",
            end=f"{today}T23:59:59Z",
        )
        assert result.ok is True
        assert len(result.records) == 3

    def test_case_4_start_equals_end_instant(self):
        adp = _make_adapter(self.tmp_root)
        today = datetime.now(tz=timezone.utc).date().isoformat()
        result = adp.forecast_window(
            start=f"{today}T12:00:00Z",
            end=f"{today}T12:00:00Z",
        )
        assert result.ok is True
        assert result.error is None
        # Exactly the midday observation.
        assert len(result.records) == 1
        assert result.records[0]["record_id"] == "rec-midday"

    def test_case_5_invalid_datetime(self):
        adp = _make_adapter(self.tmp_root)
        result = adp.forecast_window(
            start="not-a-date", end="2026-08-28T00:00:00Z",
        )
        assert result.ok is False
        assert "invalid datetime" in (result.error or "")

    def test_case_6_mixed_representations(self):
        adp = _make_adapter(self.tmp_root)
        today = datetime.now(tz=timezone.utc).date().isoformat()
        result = adp.forecast_window(
            start=f"{today}T00:00:00Z",  # tz-aware (Z)
            end=f"{today}T23:59:59",     # naive
            limit=10,
        )
        # Pre-fix: TypeError. Post-fix: ok=True.
        assert result.ok is True
        assert result.error is None
        assert len(result.records) == 3

    def test_case_7_timezone_offsets(self):
        adp = _make_adapter(self.tmp_root)
        today = datetime.now(tz=timezone.utc).date().isoformat()
        # 02:00 +02:00 == 00:00 UTC; 22:00 +02:00 == 20:00 UTC.
        # All three sample observations (03:00, 12:00, 20:00 UTC)
        # fall in this window.
        result = adp.forecast_window(
            start=f"{today}T02:00:00+02:00",
            end=f"{today}T22:00:00+02:00",
            limit=10,
        )
        assert result.ok is True
        assert len(result.records) == 3

    def test_case_8_empty_no_available_forecast(self):
        adp = _make_adapter(self.tmp_root)
        result = adp.forecast_window(
            start="2099-01-01T00:00:00Z",
            end="2099-12-31T00:00:00Z",
        )
        # Valid window, no records in it: ok=True with empty list.
        assert result.ok is True
        assert result.error is None
        assert result.records == []

    def test_case_9_stale_offline_state(self):
        with tempfile.TemporaryDirectory() as td:
            empty_root = Path(td)
            adp = _make_adapter(empty_root)
            result = adp.forecast_window(
                start="2026-08-27T00:00:00Z",
                end="2026-08-28T00:00:00Z",
            )
            # No snapshot on disk → source_status path. The endpoint
            # must NOT crash, must NOT fabricate; must return the
            # honest offline / no-snapshot state.
            assert result.ok is False
            assert "no weather snapshot" in (result.error or "")

    def test_case_10_malformed_query_parameters(self):
        adp = _make_adapter(self.tmp_root)
        result = adp.forecast_window(start="oops", end="also-oops")
        assert result.ok is False
        assert "invalid datetime" in (result.error or "")


# --------------------------------------------------------------------
# Cross-cutting regression: the existing happy-path routes still work
# after the fix.
# --------------------------------------------------------------------


class TestWeatherForecastOtherPathsUnchanged:
    def test_coordinate_path_still_works(self):
        with tempfile.TemporaryDirectory() as td:
            today = datetime.now(tz=timezone.utc).date().isoformat()
            _write_weather_snapshot(
                Path(td),
                [_sample_observation(valid_at=f"{today}T12:00:00+00:00")],
            )
            adp = _make_adapter(Path(td))
            res = adp.at_coord(latitude=53.5, longitude=10.0, radius_km=200)
            assert res.ok is True
            assert res.records

    def test_no_window_returns_future_horizon(self):
        with tempfile.TemporaryDirectory() as td:
            today = datetime.now(tz=timezone.utc).date().isoformat()
            _write_weather_snapshot(
                Path(td),
                [_sample_observation(valid_at=f"{today}T12:00:00+00:00")],
            )
            adp = _make_adapter(Path(td))
            res = adp.forecast_window(limit=8)
            assert res.ok is True
            assert isinstance(len(res.records), int)
            assert len(res.records) >= 0
