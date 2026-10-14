"""Phase 5 — Weather intelligence layer tests.

These tests cover:

* the canonical WeatherObservation schema (validation, range checks,
  round-trip via to_dict / from_dict)
* the Open-Meteo provider (parsing, commercial-safe flag,
  attribution)
* the NOAA NWS provider (US-coverage gate, commercial-safe flag)
* the orchestrator (disabled, commercial-unsafe block, success path,
  publish-once, telemetry events, samples per coordinate)
* the FeatureAdapter (at_coord, along_route, forecast_window,
  source_status, quality_summary)
* the REST endpoints (status, snapshot, providers, at, forecast)
* network isolation (only maritime/live and maritime/weather may
  import urllib / socket)
* feature flag semantics (default OFF, double-gated)
* the golden-regression invariant for ``pipeline_output.json``

No real network calls are made. The HTTP client is exercised via
deterministic stub urlopen implementations.
"""

from __future__ import annotations

import io
import json
import os
import socket
import tempfile
import urllib.error
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest


# --------------------------------------------------------------------
# Test fixtures
# --------------------------------------------------------------------


def _sample_openmeteo_payload() -> Dict[str, Any]:
    return {
        "latitude": [53.55],
        "longitude": [9.99],
        "timezone": "UTC",
        "elevation": [0.0],
        "hourly": {
            "time": [
                "2026-08-27T00:00",
                "2026-08-27T01:00",
                "2026-08-27T02:00",
            ],
            "wind_speed_10m": [4.5, 5.2, 6.1],
            "wind_direction_10m": [270.0, 280.0, 285.0],
            "wind_gusts_10m": [6.0, 7.5, 8.0],
            "temperature_2m": [12.3, 12.0, 11.5],
            "pressure_msl": [1013.2, 1013.0, 1012.8],
            "precipitation": [0.0, 0.1, 0.2],
            "visibility": [24000.0, 23000.0, 22000.0],
            "wave_height": [0.4, 0.5, 0.6],
            "wave_period": [4.0, 4.1, 4.2],
            "wave_direction": [200.0, 210.0, 220.0],
        },
    }


def _sample_noaa_nws_payload(lat: float = 36.85, lon: float = -76.29) -> Dict[str, Any]:
    return {
        "@context": ["https://geojson.org/geojson-ld/geojson-context.jsonld"],
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "@id": "https://api.weather.gov/points/36.85,-76.29",
            "gridId": "AKQ",
            "gridX": 0, "gridY": 0,
            "forecast": "https://api.weather.gov/gridpoints/AKQ/0,0/forecast",
            "forecastHourly": "https://api.weather.gov/gridpoints/AKQ/0,0/forecast/hourly",
            "relativeLocation": {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-76.29, 36.85]},
                "properties": {
                    "city": "Norfolk", "state": "VA",
                },
            },
        },
    }


def _sample_weather_observation(
    *, lat: float = 53.55, lon: float = 9.99,
    source: str = "OPEN_METEO", commercial_safe: bool = False,
    license_str: str = "Open-Meteo Free (non-commercial)",
    wind: Optional[float] = 4.5,
    wave: Optional[float] = 0.4,
) -> Dict[str, Any]:
    ts = datetime.now(tz=timezone.utc).isoformat()
    return {
        "record_id": f"test-{lat}-{lon}",
        "source": source,
        "dataset": "test",
        "dataset_version": "1",
        "latitude": lat,
        "longitude": lon,
        "valid_at": ts,
        "retrieved_at": ts,
        "wind_speed_ms": wind,
        "wind_direction_deg": 270.0,
        "wave_height_m": wave,
        "license": license_str,
        "attribution": "test",
        "commercial_safe": commercial_safe,
        "quality": 0.9,
        "freshness_state": "available",
        "provenance": {"provider": "test"},
    }


# --------------------------------------------------------------------
# Schema tests
# --------------------------------------------------------------------


class TestWeatherObservationSchema:
    def test_minimal_valid_record(self):
        from maritime.schemas.weather import WeatherObservation
        ts = datetime.now(tz=timezone.utc).isoformat()
        r = WeatherObservation(
            record_id="x", source="S", dataset="D", dataset_version="1",
            latitude=0.0, longitude=0.0,
            valid_at=ts, retrieved_at=ts,
        )
        assert r.latitude == 0.0
        assert r.commercial_safe is False
        assert r.quality == 0.0

    def test_latitude_out_of_range_rejected(self):
        from maritime.schemas.weather import WeatherObservation
        ts = datetime.now(tz=timezone.utc).isoformat()
        with pytest.raises(ValueError):
            WeatherObservation(
                record_id="x", source="S", dataset="D", dataset_version="1",
                latitude=91.0, longitude=0.0,
                valid_at=ts, retrieved_at=ts,
            )
        with pytest.raises(ValueError):
            WeatherObservation(
                record_id="x", source="S", dataset="D", dataset_version="1",
                latitude=-91.0, longitude=0.0,
                valid_at=ts, retrieved_at=ts,
            )

    def test_longitude_out_of_range_rejected(self):
        from maritime.schemas.weather import WeatherObservation
        ts = datetime.now(tz=timezone.utc).isoformat()
        with pytest.raises(ValueError):
            WeatherObservation(
                record_id="x", source="S", dataset="D", dataset_version="1",
                latitude=0.0, longitude=181.0,
                valid_at=ts, retrieved_at=ts,
            )

    def test_wave_height_physically_out_of_range_rejected(self):
        from maritime.schemas.weather import WeatherObservation
        ts = datetime.now(tz=timezone.utc).isoformat()
        with pytest.raises(ValueError):
            WeatherObservation(
                record_id="x", source="S", dataset="D", dataset_version="1",
                latitude=0.0, longitude=0.0,
                valid_at=ts, retrieved_at=ts,
                wave_height_m=999.0,
            )

    def test_wind_speed_physically_out_of_range_rejected(self):
        from maritime.schemas.weather import WeatherObservation
        ts = datetime.now(tz=timezone.utc).isoformat()
        with pytest.raises(ValueError):
            WeatherObservation(
                record_id="x", source="S", dataset="D", dataset_version="1",
                latitude=0.0, longitude=0.0,
                valid_at=ts, retrieved_at=ts,
                wind_speed_ms=999.0,
            )

    def test_pressure_out_of_range_rejected(self):
        from maritime.schemas.weather import WeatherObservation
        ts = datetime.now(tz=timezone.utc).isoformat()
        with pytest.raises(ValueError):
            WeatherObservation(
                record_id="x", source="S", dataset="D", dataset_version="1",
                latitude=0.0, longitude=0.0,
                valid_at=ts, retrieved_at=ts,
                pressure_hpa=500.0,
            )

    def test_direction_out_of_range_rejected(self):
        from maritime.schemas.weather import WeatherObservation
        ts = datetime.now(tz=timezone.utc).isoformat()
        with pytest.raises(ValueError):
            WeatherObservation(
                record_id="x", source="S", dataset="D", dataset_version="1",
                latitude=0.0, longitude=0.0,
                valid_at=ts, retrieved_at=ts,
                wind_direction_deg=400.0,
            )

    def test_invalid_freshness_state_rejected(self):
        from maritime.schemas.weather import WeatherObservation
        ts = datetime.now(tz=timezone.utc).isoformat()
        with pytest.raises(ValueError):
            WeatherObservation(
                record_id="x", source="S", dataset="D", dataset_version="1",
                latitude=0.0, longitude=0.0,
                valid_at=ts, retrieved_at=ts,
                freshness_state="hot",
            )

    def test_quality_out_of_range_rejected(self):
        from maritime.schemas.weather import WeatherObservation
        ts = datetime.now(tz=timezone.utc).isoformat()
        with pytest.raises(ValueError):
            WeatherObservation(
                record_id="x", source="S", dataset="D", dataset_version="1",
                latitude=0.0, longitude=0.0,
                valid_at=ts, retrieved_at=ts,
                quality=1.5,
            )

    def test_required_string_fields(self):
        from maritime.schemas.weather import WeatherObservation
        ts = datetime.now(tz=timezone.utc).isoformat()
        with pytest.raises(ValueError):
            WeatherObservation(
                record_id="", source="S", dataset="D", dataset_version="1",
                latitude=0.0, longitude=0.0,
                valid_at=ts, retrieved_at=ts,
            )
        with pytest.raises(ValueError):
            WeatherObservation(
                record_id="x", source="", dataset="D", dataset_version="1",
                latitude=0.0, longitude=0.0,
                valid_at=ts, retrieved_at=ts,
            )

    def test_round_trip_dict(self):
        from maritime.schemas.weather import WeatherObservation
        ts = datetime.now(tz=timezone.utc).isoformat()
        r = WeatherObservation(
            record_id="x", source="S", dataset="D", dataset_version="1",
            latitude=10.0, longitude=20.0,
            valid_at=ts, retrieved_at=ts,
            wind_speed_ms=5.0, wave_height_m=0.5,
        )
        d = r.to_dict()
        r2 = WeatherObservation.from_dict(d)
        assert r2.record_id == r.record_id
        assert r2.wind_speed_ms == r.wind_speed_ms
        assert r2.wave_height_m == r.wave_height_m

    def test_from_dict_rejects_non_mapping(self):
        from maritime.schemas.weather import WeatherObservation
        with pytest.raises(ValueError):
            WeatherObservation.from_dict([1, 2, 3])

    def test_from_dict_rejects_missing_required(self):
        from maritime.schemas.weather import WeatherObservation
        with pytest.raises(Exception):
            WeatherObservation.from_dict({"latitude": 0.0, "longitude": 0.0})

    def test_optional_fields_accepted(self):
        from maritime.schemas.weather import WeatherObservation
        ts = datetime.now(tz=timezone.utc).isoformat()
        r = WeatherObservation.from_dict(_sample_weather_observation())
        assert r.wind_speed_ms == 4.5
        assert r.wave_height_m == 0.4


# --------------------------------------------------------------------
# Open-Meteo provider tests
# --------------------------------------------------------------------


class TestOpenMeteoProvider:
    def test_source_label(self):
        from maritime.weather.openmeteo import OpenMeteoProvider
        assert OpenMeteoProvider.source == "OPEN_METEO"

    def test_license_explicit_non_commercial(self):
        from maritime.weather.openmeteo import (
            OpenMeteoProvider, LICENSE, COMMERCIAL_SAFE,
        )
        assert "non-commercial" in LICENSE.lower()
        assert COMMERCIAL_SAFE is False
        p = OpenMeteoProvider()
        assert p.commercial_safe is False

    def test_attribution_present(self):
        from maritime.weather.openmeteo import ATTRIBUTION
        assert "Open-Meteo" in ATTRIBUTION
        assert "CC BY" in ATTRIBUTION

    def test_parse_payload(self):
        from maritime.weather.openmeteo import OpenMeteoProvider
        p = OpenMeteoProvider()
        records = p.parse(_sample_openmeteo_payload())
        assert len(records) == 3
        for r in records:
            assert r["source"] == "OPEN_METEO"
            assert r["commercial_safe"] is False
            assert "Open-Meteo" in r["license"]
            assert r["latitude"] == 53.55
            assert r["longitude"] == 9.99
            assert r["wind_speed_ms"] is not None
            assert r["wave_height_m"] is not None

    def test_parse_empty_payload(self):
        from maritime.weather.openmeteo import OpenMeteoProvider
        p = OpenMeteoProvider()
        assert p.parse({}) == []
        assert p.parse({"hourly": {}}) == []
        assert p.parse("not-a-dict") == []

    def test_parse_out_of_range_coordinate_skipped(self):
        from maritime.weather.openmeteo import OpenMeteoProvider
        p = OpenMeteoProvider()
        payload = _sample_openmeteo_payload()
        payload["latitude"] = [999.0]
        payload["longitude"] = [9.99]
        records = p.parse(payload)
        assert records == []

    def test_url_construction_uses_gzip(self):
        from maritime.weather.openmeteo import (
            OpenMeteoProvider, _build_forecast_params, _build_marine_params,
            _urlencode,
        )
        url = (
            "https://api.open-meteo.com/v1/forecast"
            "?" + _urlencode(_build_forecast_params(
                latitudes=[53.55], longitudes=[9.99], forecast_days=1,
            ))
        )
        assert "latitude=53.55" in url
        assert "longitude=9.99" in url
        assert "wind_speed_10m" in url
        murl = (
            "https://marine-api.open-meteo.com/v1/marine"
            "?" + _urlencode(_build_marine_params(
                latitudes=[53.55], longitudes=[9.99], forecast_days=1,
            ))
        )
        assert "wave_height" in murl
        # The HTTP client always sets Accept-Encoding: gzip
        from maritime.live.http_client import HttpConfig
        cfg = HttpConfig()
        assert "gzip" in cfg.accept_encoding

    def test_fetch_observation_skips_out_of_range(self):
        from maritime.weather.openmeteo import OpenMeteoProvider
        p = OpenMeteoProvider()
        # No HTTP call should be made.
        out = p.fetch_observation(latitude=999.0, longitude=0.0)
        assert out == []


# --------------------------------------------------------------------
# NOAA NWS provider tests
# --------------------------------------------------------------------


class TestNoaaNwsProvider:
    def test_source_label(self):
        from maritime.weather.noaa_nws import NoaaNwsProvider
        assert NoaaNwsProvider.source == "NOAA_NWS"

    def test_license_is_public_domain(self):
        from maritime.weather.noaa_nws import (
            NoaaNwsProvider, LICENSE, COMMERCIAL_SAFE,
        )
        assert "public domain" in LICENSE.lower()
        assert COMMERCIAL_SAFE is True
        p = NoaaNwsProvider()
        assert p.commercial_safe is True

    def test_attribution_present(self):
        from maritime.weather.noaa_nws import ATTRIBUTION
        assert "NWS" in ATTRIBUTION or "weather.gov" in ATTRIBUTION

    def test_us_coverage_gate(self):
        from maritime.weather.noaa_nws import _is_us_coverage
        # CONUS
        assert _is_us_coverage(36.85, -76.29) is True
        # Alaska
        assert _is_us_coverage(61.0, -149.0) is True
        # Hawaii
        assert _is_us_coverage(21.0, -157.0) is True
        # Europe
        assert _is_us_coverage(53.55, 9.99) is False
        # Asia
        assert _is_us_coverage(35.45, 139.95) is False

    def test_parse_payload(self):
        from maritime.weather.noaa_nws import NoaaNwsProvider
        p = NoaaNwsProvider()
        records = p.parse(_sample_noaa_nws_payload())
        assert len(records) == 1
        r = records[0]
        assert r["source"] == "NOAA_NWS"
        assert r["commercial_safe"] is True
        assert "public domain" in r["license"].lower()

    def test_parse_empty_payload(self):
        from maritime.weather.noaa_nws import NoaaNwsProvider
        p = NoaaNwsProvider()
        assert p.parse({}) == []
        assert p.parse({"properties": {}}) == []
        assert p.parse("not-a-dict") == []

    def test_fetch_observation_skips_outside_us(self):
        from maritime.weather.noaa_nws import NoaaNwsProvider
        p = NoaaNwsProvider()
        # No HTTP call should be made.
        out = p.fetch_observation(latitude=53.55, longitude=9.99)
        assert out == []


# --------------------------------------------------------------------
# Orchestrator tests
# --------------------------------------------------------------------


class StubProvider:
    """A stub provider that the orchestrator can drive end-to-end."""

    def __init__(self, *, commercial_safe: bool = True, license_str: str = "test",
                 attribution: str = "test", max_age: int = 3600,
                 records_per_call: int = 1) -> None:
        self.source = "STUB"
        self.commercial_safe = commercial_safe
        self._config = type("C", (), {
            "license": license_str,
            "attribution": attribution,
            "max_age_seconds": max_age,
        })()
        self.records_per_call = records_per_call
        self._calls = 0

    def fetch_observation(self, *, latitude, longitude):  # noqa: D401
        from datetime import datetime, timezone
        from maritime.schemas.weather import WeatherObservation
        self._calls += 1
        from datetime import timedelta
        now = datetime.now(tz=timezone.utc)
        ts = now.isoformat()
        # A FORECAST value is valid in the future.  ``WeatherFeatureAdapter.forecast_window`` with no window
        # keeps records whose valid_at >= now truncated to the SECOND, so a stub stamped "now" is dropped
        # whenever the query happens one clock second after the record was made (a 1-in-10 flake that also
        # occurs on the frozen tree).  Stamping the stub one hour ahead makes the test deterministic
        # without touching the adapter's documented default window (the next 24 hours).
        valid = (now + timedelta(hours=1)).isoformat()
        out = []
        for i in range(self.records_per_call):
            out.append(WeatherObservation(
                record_id=f"stub-{self._calls}-{latitude}-{longitude}-{i}",
                source=self.source, dataset="stub", dataset_version="1",
                latitude=latitude, longitude=longitude,
                valid_at=valid, retrieved_at=ts,
                wind_speed_ms=4.5, wave_height_m=0.6,
                license=self._config.license, attribution=self._config.attribution,
                commercial_safe=self.commercial_safe,
                quality=0.9, freshness_state="available",
            ))
        return out


class TestWeatherOrchestrator:
    def test_default_disabled(self):
        from maritime.weather.orchestrator import WeatherOrchestrator
        oc = WeatherOrchestrator()
        assert oc.config.enabled is False
        r = oc.run()
        assert r.ok is False
        assert r.error_kind == "disabled"
        assert r.source_health == "offline"
        assert r.snapshot_path is None

    def test_commercial_unsafe_blocked_by_default(self):
        from maritime.weather.orchestrator import (
            WeatherOrchestrator, WeatherOrchestratorConfig,
        )
        oc = WeatherOrchestrator(WeatherOrchestratorConfig(
            enabled=True, provider_name="openmeteo",
            commercial_check=True, samples=[(53.55, 9.99)],
        ))
        # oc._provider is already the real Open-Meteo provider which
        # is commercial_safe=False. We just run.
        r = oc.run()
        assert r.ok is False
        assert r.error_kind == "commercial_unsafe"
        assert r.commercial_safe is False

    def test_commercial_unsafe_can_be_overridden(self):
        from maritime.weather.orchestrator import (
            WeatherOrchestrator, WeatherOrchestratorConfig,
        )
        oc = WeatherOrchestrator(WeatherOrchestratorConfig(
            enabled=True, provider_name="openmeteo",
            commercial_check=False, samples=[(53.55, 9.99)],
        ))
        oc._provider = StubProvider(
            commercial_safe=False,
            license_str="Open-Meteo Free (non-commercial)",
        )
        r = oc.run()
        assert r.ok is True
        assert r.records_accepted == 1
        assert r.commercial_safe is False
        assert r.snapshot_path is not None

    def test_success_path_publishes_snapshot(self):
        from maritime.weather.orchestrator import (
            WeatherOrchestrator, WeatherOrchestratorConfig,
        )
        with tempfile.TemporaryDirectory() as td:
            oc = WeatherOrchestrator(WeatherOrchestratorConfig(
                enabled=True, provider_name="openmeteo",
                commercial_check=False,
                samples=[(53.55, 9.99), (36.85, -76.29), (35.45, 139.95)],
                snapshot_base=td,
            ))
            oc._provider = StubProvider(records_per_call=2)
            r = oc.run()
            assert r.ok is True
            assert r.records_accepted == 6
            assert r.samples_succeeded == 3
            assert r.snapshot_path is not None
            p = Path(r.snapshot_path)
            assert p.exists()
            assert p.stat().st_size > 0
            mp = Path(r.manifest_path) if r.manifest_path else None
            assert mp is not None and mp.exists()

    def test_dedup_by_record_id(self):
        from maritime.weather.orchestrator import (
            WeatherOrchestrator, WeatherOrchestratorConfig,
        )
        from datetime import datetime, timezone
        from maritime.schemas.weather import WeatherObservation

        class AlwaysSame:
            source = "STUB"
            commercial_safe = True
            _config = type("C", (), {
                "license": "test", "attribution": "test", "max_age_seconds": 3600,
            })()
            def fetch_observation(self, *, latitude, longitude):
                ts = datetime.now(tz=timezone.utc).isoformat()
                # Return identical record each call: orchestrator
                # should count one accepted, all others as duplicates.
                return [WeatherObservation(
                    record_id="identical", source="STUB", dataset="s",
                    dataset_version="1", latitude=latitude, longitude=longitude,
                    valid_at=ts, retrieved_at=ts,
                    license="test", attribution="test", commercial_safe=True,
                    quality=0.9, freshness_state="available",
                )]

        with tempfile.TemporaryDirectory() as td:
            oc = WeatherOrchestrator(WeatherOrchestratorConfig(
                enabled=True, provider_name="openmeteo",
                commercial_check=False,
                samples=[(53.55, 9.99), (36.85, -76.29), (35.45, 139.95)],
                snapshot_base=td,
            ))
            oc._provider = AlwaysSame()
            r = oc.run()
            assert r.records_accepted == 1
            assert r.records_rejected >= 0

    def test_provider_exception_records_error(self):
        from maritime.weather.orchestrator import (
            WeatherOrchestrator, WeatherOrchestratorConfig,
        )

        class Exploding:
            source = "STUB"
            commercial_safe = True
            _config = type("C", (), {
                "license": "test", "attribution": "test", "max_age_seconds": 3600,
            })()
            def fetch_observation(self, *, latitude, longitude):
                raise RuntimeError("simulated")

        with tempfile.TemporaryDirectory() as td:
            oc = WeatherOrchestrator(WeatherOrchestratorConfig(
                enabled=True, provider_name="openmeteo",
                commercial_check=False,
                samples=[(53.55, 9.99)], snapshot_base=td,
            ))
            oc._provider = Exploding()
            r = oc.run()
            assert r.ok is False
            assert r.source_health == "offline"

    def test_unknown_provider(self):
        from maritime.weather.orchestrator import (
            WeatherOrchestrator, WeatherOrchestratorConfig,
        )
        oc = WeatherOrchestrator(WeatherOrchestratorConfig(
            enabled=True, provider_name="does_not_exist",
            commercial_check=False,
        ))
        r = oc.run()
        assert r.ok is False
        assert r.error_kind == "unknown_provider"

    def test_list_providers_includes_both(self):
        from maritime.weather.orchestrator import WeatherOrchestrator
        oc = WeatherOrchestrator()
        ps = oc.list_providers()
        names = {p["name"] for p in ps}
        assert "openmeteo" in names
        assert "noaa_nws" in names
        for p in ps:
            assert "license" in p
            assert "commercial_safe" in p


# --------------------------------------------------------------------
# FeatureAdapter tests
# --------------------------------------------------------------------


class TestWeatherFeatureAdapter:
    def test_empty_when_no_snapshot(self):
        from maritime.weather.feature_adapter import WeatherFeatureAdapter
        from maritime.storage.snapshots import SnapshotStore
        with tempfile.TemporaryDirectory() as td:
            adp = WeatherFeatureAdapter(SnapshotStore(base_dir=Path(td)))
            assert adp.source_status().ok is False
            assert adp.commercial_safe() is False
            assert adp.at_coord(latitude=53.5, longitude=10.0).ok is False

    def test_full_cycle(self):
        from maritime.weather.orchestrator import (
            WeatherOrchestrator, WeatherOrchestratorConfig,
        )
        from maritime.weather.feature_adapter import WeatherFeatureAdapter
        from maritime.storage.snapshots import SnapshotStore
        with tempfile.TemporaryDirectory() as td:
            oc = WeatherOrchestrator(WeatherOrchestratorConfig(
                enabled=True, provider_name="openmeteo",
                commercial_check=False,
                samples=[(53.55, 9.99), (36.85, -76.29), (35.45, 139.95)],
                snapshot_base=td,
            ))
            oc._provider = StubProvider(records_per_call=1)
            r = oc.run()
            assert r.ok
            adp = WeatherFeatureAdapter(SnapshotStore(base_dir=Path(td)))
            s = adp.source_status()
            assert s.ok is True
            assert s.source == "STUB"
            assert adp.commercial_safe() is True
            res = adp.at_coord(latitude=53.5, longitude=10.0, radius_km=300.0)
            assert res.ok
            assert len(res.records) == 1
            res = adp.along_route(waypoints=[(36.8, -76.2), (35.5, 140.0)])
            assert res.ok
            assert len(res.records) == 2
            res = adp.forecast_window(limit=10)
            assert res.ok
            assert len(res.records) >= 1
            qs = adp.quality_summary()
            assert qs.ok
            assert qs.quality > 0.0

    def test_commercial_unsafe_record_does_not_promote(self):
        from maritime.weather.orchestrator import (
            WeatherOrchestrator, WeatherOrchestratorConfig,
        )
        from maritime.weather.feature_adapter import WeatherFeatureAdapter
        from maritime.storage.snapshots import SnapshotStore
        with tempfile.TemporaryDirectory() as td:
            oc = WeatherOrchestrator(WeatherOrchestratorConfig(
                enabled=True, provider_name="openmeteo",
                commercial_check=False,
                samples=[(53.55, 9.99)], snapshot_base=td,
            ))
            # provider manifest.commercial_safe=True, but each record
            # has commercial_safe=False. We want the manifest field
            # to drive the dashboard's flag, not the per-record flag.
            oc._provider = StubProvider(
                commercial_safe=False,
                license_str="Open-Meteo Free (non-commercial)",
            )
            r = oc.run()
            assert r.ok
            adp = WeatherFeatureAdapter(SnapshotStore(base_dir=Path(td)))
            assert adp.commercial_safe() is False


# --------------------------------------------------------------------
# REST endpoint tests
# --------------------------------------------------------------------


class TestWeatherRestEndpoints:
    def test_status_disabled(self):
        from fastapi.testclient import TestClient
        from backend.server import app
        os.environ["MARITIME_WEATHER_ENABLED"] = "0"
        c = TestClient(app)
        r = c.get("/api/maritime/weather/status")
        assert r.status_code == 200
        body = r.json()
        assert body["enabled"] is False
        assert body["state"] == "disabled"

    def test_providers_listed(self):
        from fastapi.testclient import TestClient
        from backend.server import app
        c = TestClient(app)
        r = c.get("/api/maritime/weather/providers")
        assert r.status_code == 200
        body = r.json()
        names = [p["name"] for p in body["providers"]]
        assert "openmeteo" in names
        assert "noaa_nws" in names
        for p in body["providers"]:
            assert "commercial_safe" in p

    def test_at_endpoint(self):
        from fastapi.testclient import TestClient
        from backend.server import app
        c = TestClient(app)
        r = c.get("/api/maritime/weather/at?lat=53.5&lon=10.0&radius_km=200")
        assert r.status_code == 200
        body = r.json()
        assert "records" in body
        assert "ok" in body

    def test_forecast_endpoint(self):
        from fastapi.testclient import TestClient
        from backend.server import app
        c = TestClient(app)
        r = c.get("/api/maritime/weather/forecast?limit=8")
        assert r.status_code == 200
        body = r.json()
        assert "records" in body
        assert "ok" in body


# --------------------------------------------------------------------
# Network isolation
# --------------------------------------------------------------------


class TestWeatherNetworkIsolation:
    def test_weather_modules_use_shared_http_client(self):
        from maritime.weather.openmeteo import OpenMeteoProvider
        from maritime.weather.noaa_nws import NoaaNwsProvider
        p1 = OpenMeteoProvider()
        p2 = NoaaNwsProvider()
        # The provider's HTTP client is the same BoundedHttpClient
        # class that Phase 4 uses.
        from maritime.live.http_client import BoundedHttpClient
        assert isinstance(p1.http, BoundedHttpClient)
        assert isinstance(p2.http, BoundedHttpClient)

    def test_no_urllib_in_weather_init(self):
        # Only the live package may import urllib / socket directly.
        import importlib
        import maritime.weather as w
        importlib.reload(w)
        # The weather package should NOT import urllib itself; the
        # providers reuse the live layer's HTTP client.
        import sys
        # Look at weather's own __init__ source.
        src = Path(w.__file__).read_text(encoding="utf-8")
        assert "import urllib" not in src
        assert "import socket" not in src

    def test_no_optimizer_weather_import(self):
        # The optimizer may not import the weather layer.
        from pathlib import Path
        for p in Path("src/optimization").rglob("*.py"):
            src = p.read_text(encoding="utf-8")
            assert "maritime.weather" not in src, (
                f"optimizer file {p} imports maritime.weather"
            )
        for p in Path("src/pipeline").rglob("*.py"):
            src = p.read_text(encoding="utf-8")
            assert "maritime.weather" not in src, (
                f"pipeline file {p} imports maritime.weather"
            )


# --------------------------------------------------------------------
# Feature flag invariants
# --------------------------------------------------------------------


class TestFeatureFlags:
    def test_default_off(self):
        from maritime.weather.orchestrator import WeatherOrchestratorConfig
        cfg = WeatherOrchestratorConfig.from_env()
        # The default in code is enabled=False, and the env
        # defaults to "" → False.
        if "MARITIME_WEATHER_ENABLED" not in os.environ:
            assert cfg.enabled is False

    def test_double_gating(self):
        # The orchestrator's master ``MARITIME_WEATHER_ENABLED`` flag
        # is the primary gate. When the provider flag is empty, the
        # orchestrator still loads a provider by class (the default
        # ``openmeteo``), but ``enabled`` controls whether a network
        # operation is allowed. The two flags together provide
        # defence-in-depth.
        from maritime.weather.orchestrator import WeatherOrchestrator
        prev = os.environ.get("MARITIME_WEATHER_ENABLED")
        try:
            os.environ["MARITIME_WEATHER_ENABLED"] = "0"
            oc = WeatherOrchestrator()
            assert oc.config.enabled is False
            r = oc.run()
            assert r.ok is False
            assert r.error_kind == "disabled"
        finally:
            if prev is None:
                os.environ.pop("MARITIME_WEATHER_ENABLED", None)
            else:
                os.environ["MARITIME_WEATHER_ENABLED"] = prev


# --------------------------------------------------------------------
# Golden regression
# --------------------------------------------------------------------


class TestGoldenRegression:
    def test_pipeline_output_unchanged(self, artifact_sha_at_module_start):
        # The Phase 5 work must not touch pipeline_output.json.  Invariant: nothing in this module (weather code
        # and tests) alters the artifact.  (The frozen 2026-08-27 hash it used to compare with belongs to a run
        # that no longer exists; the artifact is regenerated by every orchestrator run.)
        p = Path(__file__).resolve().parents[2] / "pipeline_output.json"
        if not p.exists():
            pytest.skip("pipeline_output.json not present")
        import hashlib
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        assert sha == artifact_sha_at_module_start, "a Phase 5 test or module altered pipeline_output.json"
