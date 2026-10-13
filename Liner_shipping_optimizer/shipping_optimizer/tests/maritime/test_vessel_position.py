"""Tests for the canonical vessel-position schema."""

import pytest

from maritime.schemas.vessel_position import (
    NavStatus,
    VesselPosition,
    canonicalize_nav_status,
)


def _good_raw():
    return {
        "mmsi": "338000001",
        "timestamp": "2024-06-01T08:00:00+00:00",
        "latitude": 33.74,
        "longitude": -118.26,
        "sog_kn": 12.5,
        "cog_deg": 90.0,
        "heading_deg": 91.0,
        "vessel_type": "cargo",
        "nav_status": 0,
        "source": "MARINE_CADASTRE",
        "dataset": "marinecadastre_ais",
        "dataset_version": "2024.01",
        "ingested_at": "2024-06-01T08:01:00+00:00",
        "snapshot_id": "s",
        "license": "CC0",
        "attribution": "NOAA",
        "quality": 1.0,
        "provenance": {},
    }


def test_canonical_record_round_trip():
    pos = VesselPosition.from_dict(_good_raw())
    assert pos.mmsi == "338000001"
    assert pos.latitude == 33.74
    assert pos.nav_status == NavStatus.UNDERWAY_ENGINE
    out = pos.to_dict()
    assert out["mmsi"] == "338000001"
    assert out["nav_status"] == "underway_engine"


def test_invalid_mmsi_rejected():
    bad = _good_raw()
    bad["mmsi"] = "12345"  # not 9 digits
    with pytest.raises(ValueError):
        VesselPosition.from_dict(bad)


def test_invalid_latitude_rejected():
    bad = _good_raw()
    bad["latitude"] = 200.0
    with pytest.raises(ValueError):
        VesselPosition.from_dict(bad)


def test_missing_vessel_type_rejected():
    bad = _good_raw()
    bad["vessel_type"] = ""
    with pytest.raises(ValueError):
        VesselPosition.from_dict(bad)


def test_canonicalize_nav_status_codes():
    assert canonicalize_nav_status(0) == NavStatus.UNDERWAY_ENGINE
    assert canonicalize_nav_status(5) == NavStatus.MOORED
    assert canonicalize_nav_status(7) == NavStatus.FISHING
    assert canonicalize_nav_status(8) == NavStatus.UNDERWAY_SAILING
    assert canonicalize_nav_status(99) == NavStatus.UNKNOWN


def test_canonicalize_nav_status_labels():
    assert canonicalize_nav_status("at_anchor") == NavStatus.AT_ANCHOR
    assert canonicalize_nav_status("MOORED") == NavStatus.MOORED
    assert canonicalize_nav_status(None) == NavStatus.UNKNOWN
    assert canonicalize_nav_status("") == NavStatus.UNKNOWN


def test_optional_sog_cog_heading():
    raw = _good_raw()
    raw["sog_kn"] = None
    raw["cog_deg"] = None
    raw["heading_deg"] = None
    pos = VesselPosition.from_dict(raw)
    assert pos.sog_kn is None
    assert pos.cog_deg is None


def test_quality_out_of_range_rejected():
    bad = _good_raw()
    bad["quality"] = 1.5
    with pytest.raises(ValueError):
        VesselPosition.from_dict(bad)