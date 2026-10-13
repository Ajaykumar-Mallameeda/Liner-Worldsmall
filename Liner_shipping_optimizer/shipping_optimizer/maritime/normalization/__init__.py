"""Normalization helpers for raw EMODnet payloads.

The normalization layer converts heterogeneous raw records (JSON dicts of
varying shapes) into the canonical :class:`TrafficDensityRecord` form while
tracking every rejection/duplicate/parse-error in counters. It is the only
place in the maritime pipeline that touches raw payloads.
"""

from .coordinates import normalize_coordinate, quantize_cell
from .timestamps import normalize_observation_window, parse_period

__all__ = [
    "normalize_coordinate",
    "quantize_cell",
    "normalize_observation_window",
    "parse_period",
]
