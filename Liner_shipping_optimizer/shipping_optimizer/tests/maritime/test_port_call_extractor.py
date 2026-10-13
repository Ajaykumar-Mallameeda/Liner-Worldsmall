"""Tests for the port-call state machine."""

from datetime import datetime, timezone

from maritime.geofencing import is_within_port
from maritime.port_call_extractor import extract_port_calls
from maritime.schemas.port import Port, PortCallStatus, PortType
from maritime.schemas.vessel_position import NavStatus, VesselPosition


def _port(pid="USLAX", lat=33.7395, lon=-118.2610, radius=1.5):
    return Port(
        port_id=pid, name=pid, country="US", region="r",
        latitude=lat, longitude=lon, radius_nm=radius,
        port_type=PortType.CARGO, source="MARINE_CADASTRE",
        dataset="d", dataset_version="0", license="CC0", attribution="",
    )


def _pos(mmsi, ts, lat, lon, vt="cargo"):
    return VesselPosition(
        mmsi=mmsi, timestamp=ts, latitude=lat, longitude=lon,
        sog_kn=0.0, cog_deg=90.0, heading_deg=90.0,
        vessel_type=vt, nav_status=NavStatus.MOORED,
        source="MARINE_CADASTRE", dataset="d", dataset_version="0",
        ingested_at="2024-06-01T00:00:00+00:00", snapshot_id="s",
        quality=1.0, license="CC0", attribution="NOAA", provenance={},
    )


def test_no_ports_returns_empty():
    assert extract_port_calls(
        [_pos("338000001", "2024-06-01T08:00:00+00:00", 33.74, -118.26)],
        [], snapshot_id="s", ingested_at="2024-06-01T00:00:00+00:00",
    ) == []


def test_no_positions_returns_empty():
    assert extract_port_calls(
        [], [_port()], snapshot_id="s", ingested_at="2024-06-01T00:00:00+00:00",
    ) == []


def test_simple_confirmed_call():
    p = _port()
    positions = [
        _pos("338000001", "2024-06-01T08:00:00+00:00", 33.740, -118.262),
        _pos("338000001", "2024-06-01T09:00:00+00:00", 33.741, -118.261),
        _pos("338000001", "2024-06-01T10:00:00+00:00", 33.742, -118.260),
        _pos("338000001", "2024-06-01T11:00:00+00:00", 33.743, -118.259),
        # Vessel leaves the port at 12:00
        _pos("338000001", "2024-06-01T12:00:00+00:00", 33.80, -118.20),
    ]
    calls = extract_port_calls(
        positions, [p],
        snapshot_id="s", ingested_at="2024-06-01T00:00:00+00:00",
    )
    assert len(calls) == 1
    c = calls[0]
    assert c.mmsi == "338000001"
    assert c.port_id == "USLAX"
    assert c.status == PortCallStatus.DEPARTURE
    # Vessel was inside from 08:00 to 11:00 (180 minutes); left at 12:00.
    assert c.dwell_minutes == 180.0
    assert c.departure_ts is not None


def test_rejected_call_when_dwell_too_short():
    p = _port()
    positions = [
        # Inside for only 5 minutes (< 30 min threshold)
        _pos("338000002", "2024-06-01T08:00:00+00:00", 33.740, -118.262),
        _pos("338000002", "2024-06-01T08:05:00+00:00", 33.80, -118.20),
    ]
    calls = extract_port_calls(
        positions, [p],
        snapshot_id="s", ingested_at="2024-06-01T00:00:00+00:00",
    )
    assert len(calls) == 1
    assert calls[0].status == PortCallStatus.REJECTED


def test_open_call_when_vessel_still_inside():
    p = _port()
    positions = [
        _pos("338000003", "2024-06-01T08:00:00+00:00", 33.740, -118.262),
        _pos("338000003", "2024-06-01T09:00:00+00:00", 33.741, -118.261),
        _pos("338000003", "2024-06-01T10:00:00+00:00", 33.742, -118.260),
    ]
    calls = extract_port_calls(
        positions, [p],
        snapshot_id="s", ingested_at="2024-06-01T00:00:00+00:00",
    )
    assert len(calls) == 1
    c = calls[0]
    assert c.status == PortCallStatus.CONFIRMED
    assert c.departure_ts is None


def test_multiple_vessels_independent():
    p = _port()
    positions = [
        _pos("338000001", "2024-06-01T08:00:00+00:00", 33.740, -118.262),
        _pos("338000002", "2024-06-01T09:00:00+00:00", 33.741, -118.261),
        _pos("338000001", "2024-06-01T10:00:00+00:00", 33.742, -118.260),
        _pos("338000002", "2024-06-01T11:00:00+00:00", 33.743, -118.259),
        # Both leave
        _pos("338000001", "2024-06-01T12:00:00+00:00", 33.80, -118.20),
        _pos("338000002", "2024-06-01T12:30:00+00:00", 33.80, -118.20),
    ]
    calls = extract_port_calls(
        positions, [p],
        snapshot_id="s", ingested_at="2024-06-01T00:00:00+00:00",
    )
    assert len(calls) == 2
    mmsi_set = {c.mmsi for c in calls}
    assert mmsi_set == {"338000001", "338000002"}


def test_results_sorted_by_arrival():
    p = _port()
    positions = [
        _pos("338000001", "2024-06-01T09:00:00+00:00", 33.740, -118.262),
        _pos("338000002", "2024-06-01T08:00:00+00:00", 33.741, -118.261),
    ]
    calls = extract_port_calls(
        positions, [p],
        snapshot_id="s", ingested_at="2024-06-01T00:00:00+00:00",
    )
    # 338000002 arrived earlier; it should come first.
    assert calls[0].mmsi == "338000002"