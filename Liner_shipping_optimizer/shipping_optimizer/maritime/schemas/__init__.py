"""Canonical maritime schemas.

These are immutable value objects (dataclasses with ``frozen=True``) that form
the contract between ingestion, normalization, storage, and feature adapters.
"""

from .traffic_density import TrafficDensityRecord, VesselClass, canonicalize_vessel_class
from .intelligence import (
    TrafficIntelligenceSnapshot,
    TrafficFeature,
    TrafficHotspot,
    SourceHealth,
    SourceStatus,
    QualityStatus,
)
from .congestion import (
    CongestionRecord,
    CongestionLevel,
    EntityType,
    level_for_score,
)

__all__ = [
    "TrafficDensityRecord",
    "VesselClass",
    "canonicalize_vessel_class",
    "TrafficIntelligenceSnapshot",
    "TrafficFeature",
    "TrafficHotspot",
    "SourceHealth",
    "SourceStatus",
    "QualityStatus",
    "CongestionRecord",
    "CongestionLevel",
    "EntityType",
    "level_for_score",
]
