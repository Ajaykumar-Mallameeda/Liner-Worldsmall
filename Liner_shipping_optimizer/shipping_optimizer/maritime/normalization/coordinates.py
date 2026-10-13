"""Coordinate normalization.

The canonical schema uses WGS-84 lat/lon. EMODnet uses a regular lat/lon
grid; we keep the cell centroid as latitude/longitude and assign a
deterministic spatial_id via :func:`quantize_cell`.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal, ROUND_DOWN
from typing import Tuple


def normalize_coordinate(latitude: float, longitude: float) -> Tuple[float, float]:
    """Clamp coordinates to the WGS-84 range and return (lat, lon) floats.

    Raises ``ValueError`` for non-numeric or out-of-range values.
    """
    if latitude is None or longitude is None:
        raise ValueError("coordinates must not be None")
    lat = float(latitude)
    lon = float(longitude)
    if lat != lat or lon != lon:  # NaN
        raise ValueError("coordinates must not be NaN")
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"latitude out of range: {lat!r}")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(f"longitude out of range: {lon!r}")
    return lat, lon


def _truncate(value: float, precision: int) -> float:
    """Truncate a float to ``precision`` decimals (no rounding)."""
    # Use Decimal to avoid banker's rounding.
    q = Decimal(10) ** -precision
    out = Decimal(str(value)).quantize(q, rounding=ROUND_DOWN)
    return float(out)


def quantize_cell(latitude: float, longitude: float, *, precision: int = 3) -> str:
    """Return a deterministic spatial id for a coordinate at the given precision.

    The cell is identified by truncating both coordinates to ``precision``
    decimal places (~110 m at the equator for precision=3). The id is a
    ``cell:`` prefixed string so different id schemes never collide.
    """
    lat, lon = normalize_coordinate(latitude, longitude)
    q_lat = _truncate(lat, precision)
    q_lon = _truncate(lon, precision)
    return f"cell:{q_lat:.{precision}f},{q_lon:.{precision}f}"


def quantize_cell_hash(latitude: float, longitude: float, *, precision: int = 3) -> str:
    """SHA-1-based spatial id (12 chars). Useful for compact ids."""
    s = quantize_cell(latitude, longitude, precision=precision)
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]
    return f"h:{h}"
