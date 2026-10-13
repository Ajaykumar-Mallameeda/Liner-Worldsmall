"""Deterministic geofencing for port-call detection.

A port geofence is a circle on WGS-84 defined by a center coordinate
and a radius in nautical miles. The :func:`is_within_port` helper uses
the standard haversine formula for great-circle distance and returns a
strict boolean: ``True`` iff the distance from the point to the port
center is **less than or equal to** the radius.

The module is intentionally tiny and pure (no I/O, no network) so it
can be reused by the port-call extractor and by tests.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

from .schemas.port import Port


# Mean Earth radius in nautical miles.
EARTH_RADIUS_NM = 3440.065


def haversine_nm(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Great-circle distance between two WGS-84 points in nautical miles."""
    if not (-90.0 <= lat1 <= 90.0) or not (-90.0 <= lat2 <= 90.0):
        raise ValueError(f"latitude out of range: {lat1!r}, {lat2!r}")
    if not (-180.0 <= lon1 <= 180.0) or not (-180.0 <= lon2 <= 180.0):
        raise ValueError(f"longitude out of range: {lon1!r}, {lon2!r}")
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2.0) ** 2
    )
    c = 2.0 * math.asin(min(1.0, math.sqrt(a)))
    return EARTH_RADIUS_NM * c


def is_within_port(port: Port, latitude: float, longitude: float) -> bool:
    """Return ``True`` if the point is inside the port geofence.

    Distance is computed with :func:`haversine_nm`. Comparison is
    ``<= radius_nm`` (a vessel sitting exactly on the boundary counts
    as inside the port).
    """
    d = haversine_nm(port.latitude, port.longitude, latitude, longitude)
    return d <= float(port.radius_nm)


def nearest_port(
    ports: Sequence[Port], latitude: float, longitude: float
) -> Tuple[Port, float]:
    """Return ``(port, distance_nm)`` for the closest port. Ties broken by
    ``port_id`` ascending (deterministic)."""
    if not ports:
        raise ValueError("ports must be a non-empty sequence")
    best_port: Port = ports[0]
    best_d = haversine_nm(best_port.latitude, best_port.longitude,
                          latitude, longitude)
    for p in ports[1:]:
        d = haversine_nm(p.latitude, p.longitude, latitude, longitude)
        if d < best_d or (d == best_d and p.port_id < best_port.port_id):
            best_port = p
            best_d = d
    return best_port, best_d


def ports_containing(
    ports: Iterable[Port], latitude: float, longitude: float
) -> List[Port]:
    """Return all ports whose geofence contains the given point.

    Useful when port geofences overlap (e.g. Los Angeles / Long Beach).
    Returns ports sorted by ``port_id`` for determinism.
    """
    out = [p for p in ports if is_within_port(p, latitude, longitude)]
    out.sort(key=lambda p: p.port_id)
    return out