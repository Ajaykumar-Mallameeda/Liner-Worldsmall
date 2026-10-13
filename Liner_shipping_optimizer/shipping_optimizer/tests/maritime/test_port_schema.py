"""Tests for the canonical port + port-call schema."""

import pytest

from maritime.schemas.port import (
    Port,
    PortCall,
    PortCallStatus,
    PortType,
    canonicalize_port_type,
)


def _good_port():
    return {
        "port_id": "USLAX",
        "name": "Port of Los Angeles",
        "country": "US",
        "region": "us_west",
        "latitude": 33.7395,
        "longitude": -118.2610,
        "radius_nm": 1.5,
        "port_type": "cargo",
        "source": "MARINE_CADASTRE",
        "dataset": "us_port_reference_v1",
        "dataset_version": "2024.01",
        "license": "CC0",
        "attribution": "NOAA",
    }


def test_port_round_trip():
    port = Port.from_dict(_good_port())
    assert port.port_id == "USLAX"
    assert port.port_type == PortType.CARGO
    d = port.to_dict()
    assert d["port_type"] == "cargo"
    assert d["port_id"] == "USLAX"


def test_port_invalid_radius_rejected():
    bad = _good_port()
    bad["radius_nm"] = 0.0
    with pytest.raises(ValueError):
        Port.from_dict(bad)


def test_port_invalid_latitude_rejected():
    bad = _good_port()
    bad["latitude"] = 200.0
    with pytest.raises(ValueError):
        Port.from_dict(bad)


def test_canonicalize_port_type_aliases():
    assert canonicalize_port_type("container") == PortType.CARGO
    assert canonicalize_port_type("cruise") == PortType.PASSENGER
    assert canonicalize_port_type("oil") == PortType.TANKER
    assert canonicalize_port_type("made_up_label") == PortType.OTHER
    assert canonicalize_port_type(None) == PortType.UNKNOWN


def _good_call():
    return {
        "port_call_id": "pc:abc",
        "mmsi": "338000001",
        "port_id": "USLAX",
        "arrival_ts": "2024-06-01T08:00:00+00:00",
        "departure_ts": "2024-06-01T11:00:00+00:00",
        "dwell_minutes": 180.0,
        "status": "departure",
        "vessel_type": "cargo",
        "nav_status_at_arrival": "moored",
        "source": "MARINE_CADASTRE",
        "dataset": "us_port_reference_v1",
        "dataset_version": "2024.01",
        "ingested_at": "2024-06-01T08:00:01+00:00",
        "snapshot_id": "snap",
        "quality": 1.0,
        "license": "CC0",
        "attribution": "NOAA",
        "provenance": {},
    }


def test_port_call_open_state():
    pc = PortCall.from_dict(_good_call())
    assert pc.status == PortCallStatus.DEPARTURE
    assert pc.dwell_minutes == 180.0


def test_port_call_open_with_no_departure():
    raw = _good_call()
    raw["departure_ts"] = None
    raw["status"] = "confirmed"
    raw["dwell_minutes"] = 30.0
    pc = PortCall.from_dict(raw)
    assert pc.departure_ts is None
    assert pc.status == PortCallStatus.CONFIRMED


def test_port_call_rejects_negative_dwell():
    bad = _good_call()
    bad["dwell_minutes"] = -1.0
    with pytest.raises(ValueError):
        PortCall.from_dict(bad)


def test_port_call_invalid_status_rejected():
    bad = _good_call()
    bad["status"] = "not-a-status"
    with pytest.raises(ValueError):
        PortCall.from_dict(bad)