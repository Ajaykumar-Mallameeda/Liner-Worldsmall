"""Tests for the NOAA MarineCadastre ingestion adapter."""

import json
from pathlib import Path

import pytest

from maritime.ingestion.noaa import NoaaConfig, NoaaProvider
from maritime.ingestion.base import IngestionError


FIXTURE = Path("data/maritime/synthetic/noaa_ais_sample.jsonl")


def test_local_load_jsonl_fixture():
    if not FIXTURE.exists():
        pytest.skip(f"fixture missing: {FIXTURE}")
    cfg = NoaaConfig(mode="local", local_path=str(FIXTURE))
    result = NoaaProvider(cfg).fetch()
    assert result.source == "MARINE_CADASTRE"
    assert len(result.records) > 0
    # The fixture uses NOAA field names (MMSI, BaseDateTime, LAT, LON, ...)
    # After normalization the records should have canonical field names.
    first = result.records[0]
    assert "mmsi" in first
    assert "timestamp" in first
    assert "latitude" in first
    assert "longitude" in first


def test_noaa_field_name_normalization():
    raw = {
        "MMSI": "338000001",
        "BaseDateTime": "2024-06-01T08:00:00Z",
        "LAT": 33.74,
        "LON": -118.26,
        "SOG": 0.0,
        "COG": 90.0,
        "Heading": 90.0,
        "VesselType": "cargo",
        "NavigationalStatus": 5,
    }
    p = Path("tmp_noaa.json")
    p.write_text(json.dumps([raw]), encoding="utf-8")
    try:
        cfg = NoaaConfig(mode="local", local_path=str(p))
        result = NoaaProvider(cfg).fetch()
        rec = result.records[0]
        assert rec["mmsi"] == "338000001"
        assert rec["timestamp"].startswith("2024-06-01T08:00:00")
        assert rec["latitude"] == 33.74
        assert rec["longitude"] == -118.26
        assert rec["sog_kn"] == 0.0
        assert rec["nav_status"] == 5
    finally:
        if p.exists():
            p.unlink()


def test_noaa_missing_file_raises():
    cfg = NoaaConfig(mode="local", local_path="does-not-exist.json")
    with pytest.raises(IngestionError):
        NoaaProvider(cfg).fetch()


def test_noaa_empty_records_raises():
    p = Path("tmp_noaa_empty.jsonl")
    p.write_text("\n", encoding="utf-8")
    try:
        cfg = NoaaConfig(mode="local", local_path=str(p))
        with pytest.raises(IngestionError):
            NoaaProvider(cfg).fetch()
    finally:
        if p.exists():
            p.unlink()


def test_noaa_remote_mode_rejected():
    cfg = NoaaConfig(mode="remote", source_url="http://example")
    with pytest.raises(IngestionError):
        NoaaProvider(cfg).fetch()


def test_noaa_period_extracted_from_records():
    cfg = NoaaConfig(mode="local", local_path=str(FIXTURE))
    if not FIXTURE.exists():
        pytest.skip("fixture missing")
    result = NoaaProvider(cfg).fetch()
    assert "start" in result.observed_period
    assert "end" in result.observed_period


def test_noaa_license_and_attribution_pinned():
    cfg = NoaaConfig(mode="local", local_path=str(FIXTURE))
    if not FIXTURE.exists():
        pytest.skip("fixture missing")
    result = NoaaProvider(cfg).fetch()
    assert result.license == "CC0"
    assert "NOAA" in result.attribution


def test_noaa_optional_fields_default():
    raw = {
        "MMSI": "338000001",
        "BaseDateTime": "2024-06-01T08:00:00Z",
        "LAT": 33.74,
        "LON": -118.26,
    }
    p = Path("tmp_noaa.jsonl")
    p.write_text(json.dumps(raw) + "\n", encoding="utf-8")
    try:
        cfg = NoaaConfig(mode="local", local_path=str(p))
        result = NoaaProvider(cfg).fetch()
        rec = result.records[0]
        # sog_kn, cog_deg, heading_deg, vessel_type, nav_status may be None.
        assert rec["sog_kn"] is None
        assert rec["vessel_type"] is None
        assert rec["nav_status"] is None
    finally:
        if p.exists():
            p.unlink()