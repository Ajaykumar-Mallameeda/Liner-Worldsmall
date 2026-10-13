"""Tests for the canonical traffic-density record schema."""

from datetime import datetime, timezone

import pytest

from maritime.schemas.traffic_density import (
    TrafficDensityRecord,
    VesselClass,
    canonicalize_vessel_class,
)


def _good_raw():
    return {
        "spatial_id": "cell:1.0,2.0",
        "latitude": 1.0,
        "longitude": 2.0,
        "vessel_class": "cargo",
        "intensity": 100.0,
        "observation_start": "2024-01-01T00:00:00Z",
        "observation_end": "2024-01-02T00:00:00Z",
        "observed_at": "2024-01-02T00:00:00Z",
        "ingested_at": "2024-01-02T01:00:00Z",
        "snapshot_id": "snap-1",
        "quality": 0.9,
        "source": "EMODNET",
        "dataset": "vessel_density_all_ships",
        "dataset_version": "2023",
        "license": "CC BY 4.0",
        "attribution": "EMODnet",
        "provenance": {"source": "EMODNET", "dataset": "vessel_density_all_ships", "dataset_version": "2023",
                       "retrieved_at": "2024-01-02T01:00:00Z",
                       "observed_period": {"start": "2024-01-01T00:00:00Z", "end": "2024-01-02T00:00:00Z"}},
    }


def test_valid_record_round_trip():
    rec = TrafficDensityRecord.from_dict(_good_raw())
    assert rec.vessel_class == VesselClass.CARGO
    d = rec.to_dict()
    assert d["vessel_class"] == "cargo"
    assert d["latitude"] == 1.0


def test_invalid_coordinate_rejected():
    raw = _good_raw()
    raw["latitude"] = 95.0
    with pytest.raises(ValueError):
        TrafficDensityRecord.from_dict(raw)


def test_invalid_coordinate_rejected_lon():
    raw = _good_raw()
    raw["longitude"] = -200.0
    with pytest.raises(ValueError):
        TrafficDensityRecord.from_dict(raw)


def test_negative_intensity_rejected():
    raw = _good_raw()
    raw["intensity"] = -1.0
    with pytest.raises(ValueError):
        TrafficDensityRecord.from_dict(raw)


def test_nan_intensity_rejected():
    raw = _good_raw()
    raw["intensity"] = float("nan")
    with pytest.raises(ValueError):
        TrafficDensityRecord.from_dict(raw)


def test_invalid_timestamp_rejected():
    raw = _good_raw()
    raw["observation_start"] = "not-a-date"
    with pytest.raises(ValueError):
        TrafficDensityRecord.from_dict(raw)


def test_quality_out_of_range_rejected():
    raw = _good_raw()
    raw["quality"] = 1.5
    with pytest.raises(ValueError):
        TrafficDensityRecord.from_dict(raw)


def test_missing_source_rejected():
    raw = _good_raw()
    raw["source"] = ""
    with pytest.raises(ValueError):
        TrafficDensityRecord.from_dict(raw)


def test_canonicalize_vessel_class_strings():
    assert canonicalize_vessel_class("cargo") == VesselClass.CARGO
    assert canonicalize_vessel_class("TANKER") == VesselClass.TANKER
    assert canonicalize_vessel_class("unknown") == VesselClass.UNKNOWN
    assert canonicalize_vessel_class("") == VesselClass.UNKNOWN
    assert canonicalize_vessel_class(None) == VesselClass.UNKNOWN


def test_canonicalize_vessel_class_numeric_codes():
    # 70 = cargo per EMODnet convention
    assert canonicalize_vessel_class(70) == VesselClass.CARGO
    assert canonicalize_vessel_class("70") == VesselClass.CARGO
    assert canonicalize_vessel_class(90) == VesselClass.TANKER
    # 60 = passenger
    assert canonicalize_vessel_class(60) == VesselClass.PASSENGER
    # Unknown numeric -> OTHER (not UNKNOWN)
    assert canonicalize_vessel_class(123) == VesselClass.OTHER


def test_record_immutable():
    rec = TrafficDensityRecord.from_dict(_good_raw())
    with pytest.raises(Exception):
        rec.latitude = 5.0  # type: ignore[misc]


def test_epoch_timestamp_accepted():
    raw = _good_raw()
    raw["observation_start"] = 1704067200  # 2024-01-01 UTC
    raw["observation_end"] = 1704153600
    rec = TrafficDensityRecord.from_dict(raw)
    assert rec.observation_start.startswith("2024-01-01T")
