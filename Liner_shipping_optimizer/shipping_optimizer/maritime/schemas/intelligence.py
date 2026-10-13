"""Intelligence-snapshot schema.

The aggregate "snapshot" object that the feature adapter reads. A snapshot
binds a deterministic set of traffic records together with quality, provenance,
freshness, and source-health metadata. Snapshots are immutable; the
``snapshot_id`` is the only handle consumers use to refer to them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

from .traffic_density import TrafficDensityRecord, VesselClass


# --------------------------------------------------------------------
# Status enums
# --------------------------------------------------------------------


class SourceStatus(str, Enum):
    """Status of the underlying source at snapshot time."""
    UNKNOWN = "unknown"
    CHECKING = "checking"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    STALE = "stale"
    OFFLINE = "offline"
    INVALID = "invalid"


class QualityStatus(str, Enum):
    """Human-readable overall quality classification of a snapshot."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STALE = "stale"
    INVALID = "invalid"
    OFFLINE = "offline"


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# --------------------------------------------------------------------
# Feature + hotspot
# --------------------------------------------------------------------


@dataclass(frozen=True)
class TrafficFeature:
    """A derived traffic feature ready for downstream consumers."""
    feature_id: str
    feature_type: str  # one of: traffic_density, cargo_density, tanker_density,
                       # traffic_hotspot_indicator
    spatial_id: str
    latitude: float
    longitude: float
    raw_intensity: float
    normalized_intensity: float
    relative_density: float  # in [0, 1] across the snapshot
    observed_at: str
    vessel_class: VesselClass

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["vessel_class"] = self.vessel_class.value if hasattr(self.vessel_class, "value") else str(self.vessel_class)
        return d


@dataclass(frozen=True)
class TrafficHotspot:
    """A traffic hotspot indicator derived from above-threshold density cells."""
    spatial_id: str
    latitude: float
    longitude: float
    score: float  # 0..1
    dominant_vessel_class: VesselClass
    observed_at: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["dominant_vessel_class"] = (
            self.dominant_vessel_class.value
            if hasattr(self.dominant_vessel_class, "value")
            else str(self.dominant_vessel_class)
        )
        return d


# --------------------------------------------------------------------
# Source health
# --------------------------------------------------------------------


@dataclass(frozen=True)
class SourceHealth:
    """Deterministic source-health record.

    Constructed by the ingestion layer. The state machine is:
        UNKNOWN -> CHECKING -> AVAILABLE -> STALE -> OFFLINE
    with DEGRADED permitted when remote failed but cached snapshot is valid.
    """
    source: str
    status: SourceStatus
    last_check_at: str
    last_success_at: Optional[str]
    last_failure_at: Optional[str]
    consecutive_failures: int
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def initial(cls, source: str) -> "SourceHealth":
        return cls(
            source=source,
            status=SourceStatus.UNKNOWN,
            last_check_at=_utcnow_iso(),
            last_success_at=None,
            last_failure_at=None,
            consecutive_failures=0,
            notes="initial state",
        )


# --------------------------------------------------------------------
# Snapshot
# --------------------------------------------------------------------


@dataclass(frozen=True)
class TrafficIntelligenceSnapshot:
    """An immutable, locally-stored maritime intelligence snapshot.

    This is the single object consumers (feature_adapter, dashboard) read.
    It is constructed by the storage layer from the canonical schema and
    contains both the raw records and pre-computed features + provenance +
    quality metadata. Once constructed it must never be mutated; new
    snapshots replace old ones.
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
    quality_score: float  # 0..1
    completeness_ratio: float  # 0..1
    freshness: str  # ISO-8601 string
    source_status: SourceStatus
    quality_status: QualityStatus
    source_health: SourceHealth
    provenance: Mapping[str, Any]
    records: List[TrafficDensityRecord]
    features: List[TrafficFeature]
    hotspots: List[TrafficHotspot]
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
            "quality_score": self.quality_score,
            "completeness_ratio": self.completeness_ratio,
            "freshness": self.freshness,
            "source_status": self.source_status.value,
            "quality_status": self.quality_status.value,
            "source_health": self.source_health.to_dict(),
            "provenance": dict(self.provenance),
            "schema_version": self.schema_version,
        }
