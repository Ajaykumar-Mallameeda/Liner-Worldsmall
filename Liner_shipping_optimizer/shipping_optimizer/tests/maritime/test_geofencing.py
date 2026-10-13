"""Tests for deterministic geofencing."""

import pytest

from maritime.geofencing import (
    EARTH_RADIUS_NM,
    haversine_nm,
    is_within_port,
    nearest_port,
    ports_containing,
)
from maritime.schemas.port import Port, PortType


def _port(lat, lon, radius=1.0, pid="P1"):
    return Port(
        port_id=pid,
        name=pid,
        country="X",
        region="r",
        latitude=lat,
        longitude=lon,
        radius_nm=radius,
        port_type=PortType.CARGO,
        source="S",
        dataset="D",
        dataset_version="0",
        license="CC0",
        attribution="",
    )


def test_haversine_zero_distance():
    assert haversine_nm(33.74, -118.26, 33.74, -118.26) == 0.0


def test_haversine_one_degree_lat_is_60_nm():
    d = haversine_nm(0.0, 0.0, 1.0, 0.0)
    assert 59.5 < d < 60.5


def test_haversine_invalid_coord_raises():
    with pytest.raises(ValueError):
        haversine_nm(91.0, 0.0, 0.0, 0.0)


def test_is_within_port_inside():
    p = _port(33.7395, -118.261, radius=1.5)
    assert is_within_port(p, 33.740, -118.260) is True


def test_is_within_port_outside():
    p = _port(33.7395, -118.261, radius=0.5)
    # ~5 nm away
    assert is_within_port(p, 33.80, -118.20) is False


def test_is_within_port_boundary_inclusive():
    # At exactly the boundary the vessel counts as inside (closed geofence).
    # 1 degree of latitude is ~60.04 nm; pick a radius slightly larger.
    p = _port(0.0, 0.0, radius=61.0)  # 61 nm radius
    # Place the point 1 degree of latitude north of the equator (~60.04 nm).
    assert is_within_port(p, 1.0, 0.0) is True


def test_is_within_port_outside_when_above_radius():
    p = _port(0.0, 0.0, radius=60.0)
    # 1 degree of latitude is ~60.04 nm > 60.0 nm radius => outside.
    assert is_within_port(p, 1.0, 0.0) is False


def test_nearest_port_returns_closest():
    a = _port(33.74, -118.26, pid="A")
    b = _port(33.80, -118.20, pid="B")
    chosen, d = nearest_port([a, b], 33.741, -118.262)
    assert chosen.port_id == "A"
    assert d < 1.0


def test_nearest_port_tie_broken_alphabetically():
    a = _port(0.0, 0.0, pid="B")
    b = _port(0.0, 0.0, pid="A")
    chosen, _ = nearest_port([a, b], 0.0, 0.0)
    assert chosen.port_id == "A"


def test_nearest_port_empty_raises():
    with pytest.raises(ValueError):
        nearest_port([], 0.0, 0.0)


def test_ports_containing_overlap():
    lax = _port(33.7395, -118.2610, radius=2.5, pid="USLAX")
    lgb = _port(33.7550, -118.2160, radius=2.5, pid="USLGB")
    # Point in the middle of the LA/LB complex.
    result = ports_containing([lax, lgb], 33.75, -118.24)
    assert len(result) >= 1


def test_earth_radius_constant_sanity():
    assert 3430 < EARTH_RADIUS_NM < 3450