"""Port-intelligence snapshot schema.

The aggregate "snapshot" object that the feature adapter reads for
Phase 2 NOAA port-call intelligence. Mirrors the structure of
:class:`TrafficIntelligenceSnapshot` (Phase 1) but contains
:class:`Port` geofences, :class:`VesselPosition` records, and
:class:`PortCall` records (plus the derived features from
:mod:`maritime.intelligence.port_activity`).

Snapshots are immutable; the ``snapshot_id`` is the only handle
consumers use to refer to them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

from .intelligence import (
    QualityStatus,
    SourceHealth,
    SourceStatus,
)
from .port import Port, PortCall
from .vessel_position import VesselPosition
from ..intelligence.port_activity import (
    PortActivityFeature,
    PortCallTimelineFeature,
    PortVesselTypeMixFeature,
)


class PortIntelligenceStatus(str, Enum):
    """Lifecycle status of the port-intelligence snapshot.

    Distinct from :class:`SourceStatus` because a port snapshot can be
    structurally fine while ports/positions are degraded. The mapping
    is computed at build time by the pipeline.
    """

    AVAILABLE = "available"
    DEGRADED = "degraded"
    STALE = "stale"
    OFFLINE = "offline"
    INVALID = "invalid"


@dataclass(frozen=True)
class PortIntelligenceSnapshot:
    """An immutable, locally-stored port-intelligence snapshot.

    Contains the source metadata (license, attribution, freshness),
    the canonical records (ports, vessel positions, port-calls), and
    the derived features (port_activity, vessel_mix, timeline).
    """

    snapshot_id: str
    source: str
    dataset: str
    dataset_version: str
    license: str
    attribution: str
    created_at: str
    observed_start: str
    observed_end: str
    record_count: int
    accepted_records: int
    rejected_records: int
    duplicate_records: int
    port_count: int
    call_count: int
    quality_score: float  # 0..1
    completeness_ratio: float  # 0..1
    freshness: str  # ISO-8601 string
    source_status: SourceStatus
    quality_status: QualityStatus
    source_health: SourceHealth
    provenance: Mapping[str, Any]
    ports: List[Port]
    positions: List[VesselPosition]
    port_calls: List[PortCall]
    port_activity_features: List[PortActivityFeature]
    port_vessel_mix_features: List[PortVesselTypeMixFeature]
    port_timeline_features: List[PortCallTimelineFeature]
    schema_version: str = "1.0.0"

    def to_metadata_dict(self) -> Dict[str, Any]:
        """Snapshot metadata only (records/features excluded)."""
        return {
            "snapshot_id": self.snapshot_id,
            "source": self.source,
            "dataset": self.dataset,
            "dataset_version": self.dataset_version,
            "license": self.license,
            "attribution": self.attribution,
            "created_at": self.created_at,
            "observed_start": self.observed_start,
            "observed_end": self.observed_end,
            "record_count": self.record_count,
            "accepted_records": self.accepted_records,
            "rejected_records": self.rejected_records,
            "duplicate_records": self.duplicate_records,
            "port_count": self.port_count,
            "call_count": self.call_count,
            "quality_score": self.quality_score,
            "completeness_ratio": self.completeness_ratio,
            "freshness": self.freshness,
            "source_status": self.source_status.value,
            "quality_status": self.quality_status.value,
            "source_health": self.source_health.to_dict(),
            "provenance": dict(self.provenance),
            "schema_version": self.schema_version,
        }