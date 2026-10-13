"""Derived maritime intelligence features.

This layer takes a list of canonical records and produces the high-level
features that downstream consumers (feature_adapter, future optimizer
hooks) read. It never performs ingestion or network I/O.
"""

from .traffic import (
    compute_traffic_features,
    compute_hotspots,
)

__all__ = [
    "compute_traffic_features",
    "compute_hotspots",
]
