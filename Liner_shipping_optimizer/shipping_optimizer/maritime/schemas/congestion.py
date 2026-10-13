"""Phase 6 — Canonical congestion record schema.

A single canonical congestion record derived from the existing
maritime intelligence layers (Phase 1 traffic density, Phase 2 port
calls, Phase 3 resilience, Phase 4 live source, Phase 5 weather).

Congestion is DERIVED DATA. The record carries the underlying
provenance chain, the component signals that produced the score,
and an explanation of the calculation. The schema is frozen,
validated at construction, and never silently coerces bad input.

Entity types:

* ``port``             — port-area congestion (port calls + nearby traffic)
* ``route_segment``    — congestion along a polyline waypoint segment
* ``geographic_cell``  — open-water traffic-density-driven cell

Congestion level taxonomy (output by the deterministic model):

* ``low``      — score < 0.40
* ``moderate`` — 0.40 <= score < 0.65
* ``high``     — 0.65 <= score < 0.85
* ``severe``   — score >= 0.85
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Mapping, Optional

from .traffic_density import _coerce_float, _coerce_str, _coerce_timestamp, _require


# --------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------


class EntityType(str, Enum):
    """Kind of geographic entity a congestion record refers to."""
    PORT = "port"
    ROUTE_SEGMENT = "route_segment"
    GEOGRAPHIC_CELL = "geographic_cell"


class CongestionLevel(str, Enum):
    """Banded classification of a congestion score."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _clamp01(value: float, name: str) -> float:
    _require(isinstance(value, (int, float)) and value == value,
             f"{name} must be a finite number")
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _optional_unit_float(name: str, value: Any,
                         *, min_value: float = -1.0e9,
                         max_value: float = 1.0e9) -> Optional[float]:
    if value is None:
        return None
    return _coerce_float(name, value, min_value=min_value, max_value=max_value)


def level_for_score(score: float) -> CongestionLevel:
    """Deterministic band mapping for a bounded score in [0, 1].

    Thresholds are documented and config-overridable; the function
    here is the canonical mapping used everywhere in the layer.
    """
    _require(isinstance(score, (int, float)) and score == score,
             f"score must be a finite number, got {score!r}")
    s = float(score)
    if s < 0.0 or s > 1.0:
        raise ValueError(f"score={s} out of [0, 1]")
    if s < 0.40:
        return CongestionLevel.LOW
    if s < 0.65:
        return CongestionLevel.MODERATE
    if s < 0.85:
        return CongestionLevel.HIGH
    return CongestionLevel.SEVERE


# --------------------------------------------------------------------
# Canonical record
# --------------------------------------------------------------------


@dataclass(frozen=True)
class CongestionRecord:
    """A single canonical congestion record (derived data).

    Each record carries:

    * **Identity** — ``record_id``, ``entity_id``, ``entity_type``.
    * **Geography + time** — ``latitude``, ``longitude``, ``observed_at``,
      ``computed_at``.
    * **Traffic metrics** — vessel counts and density per class.
    * **Port metrics** — port call intensity and dwell proxy.
    * **Weather influence** — weather observation summary, if any.
    * **Congestion output** — ``congestion_score``, ``congestion_level``,
      ``confidence``, ``freshness_state``.
    * **Explainability** — ``components`` mapping every signal that
      contributed, ``missing_inputs`` for the signals that didn't.
    * **Provenance** — underlying source, dataset, version, license,
      attribution, commercial safety, and a ``provenance`` mapping.
    * **Provenance hygiene** — ``synthetic`` flag (True when the
      record was generated from demo data and must not be confused
      with real-world congestion).
    """

    # Identity
    record_id: str
    entity_id: str
    entity_type: str  # EntityType.value

    # Geography + time
    latitude: float
    longitude: float
    observed_at: str  # ISO-8601 UTC
    computed_at: str  # ISO-8601 UTC

    # Traffic metrics
    vessel_count: Optional[float] = None
    traffic_density: Optional[float] = None
    cargo_density: Optional[float] = None
    tanker_density: Optional[float] = None
    passenger_density: Optional[float] = None
    traffic_change_ratio: Optional[float] = None  # -1..+inf; 0 == unchanged

    # Port metrics (entity_type == "port")
    port_call_count: Optional[int] = None
    utilization_proxy: Optional[float] = None  # 0..1
    average_dwell_hours: Optional[float] = None  # >= 0
    queue_proxy: Optional[float] = None  # >= 0
    arrival_rate_per_day: Optional[float] = None  # >= 0

    # Weather influence (optional)
    weather_available: bool = False
    weather_quality: Optional[float] = None  # 0..1
    weather_risk_factor: Optional[float] = None  # 0..1 (risk modifier, not absolute)

    # Congestion output
    congestion_score: float = 0.0
    congestion_level: str = CongestionLevel.LOW.value
    confidence: float = 0.0
    freshness_state: str = "unknown"

    # Provenance
    source: str = "derived"
    dataset: str = "maritime_congestion"
    dataset_version: str = "1.0.0"
    license: str = "unresolved"
    attribution: str = ""
    commercial_safe: bool = True
    provenance: Mapping[str, Any] = field(default_factory=dict)

    # Explainability
    components: Mapping[str, float] = field(default_factory=dict)
    missing_inputs: tuple = ()

    # Synthetic flag — True when built from synthetic / demo data.
    synthetic: bool = True

    # Computation version — bumped when the calculation model changes.
    computation_version: str = "1.0.0"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        for fname in ("record_id", "entity_id", "entity_type",
                      "observed_at", "computed_at",
                      "source", "dataset", "dataset_version", "license"):
            v = getattr(self, fname)
            _require(isinstance(v, str) and v.strip() != "",
                     f"{fname} is required")
        _require(self.entity_type in {e.value for e in EntityType},
                 f"unknown entity_type: {self.entity_type!r}")
        _require(isinstance(self.latitude, (int, float))
                 and -90.0 <= self.latitude <= 90.0,
                 f"latitude out of range: {self.latitude!r}")
        _require(isinstance(self.longitude, (int, float))
                 and -180.0 <= self.longitude <= 180.0,
                 f"longitude out of range: {self.longitude!r}")
        # Score and confidence must be in [0, 1]
        _require(isinstance(self.congestion_score, (int, float))
                 and 0.0 <= self.congestion_score <= 1.0,
                 f"congestion_score out of [0, 1]: {self.congestion_score!r}")
        _require(isinstance(self.confidence, (int, float))
                 and 0.0 <= self.confidence <= 1.0,
                 f"confidence out of [0, 1]: {self.confidence!r}")
        # Congestion level must be a known band
        _require(self.congestion_level in {l.value for l in CongestionLevel},
                 f"unknown congestion_level: {self.congestion_level!r}")
        # Freshness state is the standard vocabulary
        _require(self.freshness_state in {
            "available", "degraded", "stale", "offline",
            "invalid", "unknown", "checking",
        }, f"unknown freshness_state: {self.freshness_state!r}")
        # Optional numeric fields: if present, must be within sane bounds
        if self.vessel_count is not None:
            _coerce_float("vessel_count", self.vessel_count,
                          min_value=0.0, max_value=1e9)
        if self.traffic_density is not None:
            _coerce_float("traffic_density", self.traffic_density,
                          min_value=0.0, max_value=1.0)
        if self.cargo_density is not None:
            _coerce_float("cargo_density", self.cargo_density,
                          min_value=0.0, max_value=1.0)
        if self.tanker_density is not None:
            _coerce_float("tanker_density", self.tanker_density,
                          min_value=0.0, max_value=1.0)
        if self.passenger_density is not None:
            _coerce_float("passenger_density", self.passenger_density,
                          min_value=0.0, max_value=1.0)
        if self.traffic_change_ratio is not None:
            _coerce_float("traffic_change_ratio", self.traffic_change_ratio,
                          min_value=-1.0, max_value=1e6)
        if self.utilization_proxy is not None:
            _coerce_float("utilization_proxy", self.utilization_proxy,
                          min_value=0.0, max_value=1.0)
        if self.average_dwell_hours is not None:
            _coerce_float("average_dwell_hours", self.average_dwell_hours,
                          min_value=0.0, max_value=1e6)
        if self.queue_proxy is not None:
            _coerce_float("queue_proxy", self.queue_proxy,
                          min_value=0.0, max_value=1e6)
        if self.arrival_rate_per_day is not None:
            _coerce_float("arrival_rate_per_day", self.arrival_rate_per_day,
                          min_value=0.0, max_value=1e6)
        if self.weather_quality is not None:
            _coerce_float("weather_quality", self.weather_quality,
                          min_value=0.0, max_value=1.0)
        if self.weather_risk_factor is not None:
            _coerce_float("weather_risk_factor", self.weather_risk_factor,
                          min_value=0.0, max_value=1.0)
        if self.port_call_count is not None:
            _require(isinstance(self.port_call_count, int)
                     and self.port_call_count >= 0,
                     f"port_call_count must be a non-negative int: "
                     f"{self.port_call_count!r}")
        # Provenance must be a mapping
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        if not isinstance(self.components, Mapping):
            raise ValueError("components must be a mapping")
        for k, v in self.components.items():
            _require(isinstance(v, (int, float)) and v == v,
                     f"components[{k}] must be a finite number")
        if not isinstance(self.missing_inputs, tuple):
            # Accept lists / sets in __init__ but normalize to tuple.
            object.__setattr__(self, "missing_inputs", tuple(self.missing_inputs))
        for m in self.missing_inputs:
            _require(isinstance(m, str) and m.strip() != "",
                     f"missing_inputs entries must be non-empty strings: {m!r}")
        if not isinstance(self.synthetic, bool):
            raise ValueError("synthetic must be a bool")

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["entity_type"] = self.entity_type
        d["congestion_level"] = self.congestion_level
        d["freshness_state"] = self.freshness_state
        d["components"] = dict(self.components)
        d["provenance"] = dict(self.provenance)
        d["missing_inputs"] = list(self.missing_inputs)
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "CongestionRecord":
        """Construct a congestion record from a raw mapping.

        Applies strict validation and normalization. Raises
        :class:`ValueError` for invalid input; callers must catch
        and route into rejection counters.
        """
        if not isinstance(d, Mapping):
            raise ValueError(f"record must be a mapping, got {type(d).__name__}")
        record_id = _coerce_str("record_id", d.get("record_id"))
        entity_id = _coerce_str("entity_id", d.get("entity_id"))
        entity_type_raw = _coerce_str("entity_type", d.get("entity_type"))
        if entity_type_raw not in {e.value for e in EntityType}:
            raise ValueError(f"unknown entity_type: {entity_type_raw!r}")
        lat = _coerce_float("latitude", d.get("latitude"),
                            min_value=-90.0, max_value=90.0)
        lon = _coerce_float("longitude", d.get("longitude"),
                            min_value=-180.0, max_value=180.0)
        observed_at = _coerce_timestamp("observed_at", d.get("observed_at"))
        computed_at = _coerce_timestamp("computed_at", d.get("computed_at"))

        # Optional numeric fields
        def _opt(name, mn, mx):
            return _optional_unit_float(name, d.get(name), min_value=mn, max_value=mx)

        vessel_count = _opt("vessel_count", 0.0, 1e9)
        traffic_density = _opt("traffic_density", 0.0, 1.0)
        cargo_density = _opt("cargo_density", 0.0, 1.0)
        tanker_density = _opt("tanker_density", 0.0, 1.0)
        passenger_density = _opt("passenger_density", 0.0, 1.0)
        traffic_change_ratio = _opt("traffic_change_ratio", -1.0, 1e6)
        utilization_proxy = _opt("utilization_proxy", 0.0, 1.0)
        average_dwell_hours = _opt("average_dwell_hours", 0.0, 1e6)
        queue_proxy = _opt("queue_proxy", 0.0, 1e6)
        arrival_rate_per_day = _opt("arrival_rate_per_day", 0.0, 1e6)
        weather_quality = _opt("weather_quality", 0.0, 1.0)
        weather_risk_factor = _opt("weather_risk_factor", 0.0, 1.0)

        weather_available = bool(d.get("weather_available", False))

        pcc_raw = d.get("port_call_count")
        port_call_count: Optional[int]
        if pcc_raw is None:
            port_call_count = None
        else:
            if not isinstance(pcc_raw, int):
                raise ValueError(f"port_call_count must be int, got {type(pcc_raw).__name__}")
            if pcc_raw < 0:
                raise ValueError(f"port_call_count must be >= 0: {pcc_raw}")
            port_call_count = pcc_raw

        congestion_score = _coerce_float(
            "congestion_score", d.get("congestion_score", 0.0),
            min_value=0.0, max_value=1.0,
        )
        level_raw = _coerce_str("congestion_level",
                                d.get("congestion_level", CongestionLevel.LOW.value))
        if level_raw not in {l.value for l in CongestionLevel}:
            raise ValueError(f"unknown congestion_level: {level_raw!r}")
        confidence = _coerce_float("confidence", d.get("confidence", 0.0),
                                   min_value=0.0, max_value=1.0)
        freshness_state = _coerce_str("freshness_state",
                                      d.get("freshness_state", "unknown"))
        if freshness_state not in {
            "available", "degraded", "stale", "offline",
            "invalid", "unknown", "checking",
        }:
            raise ValueError(f"unknown freshness_state: {freshness_state!r}")

        source = _coerce_str("source", d.get("source", "derived"))
        dataset = _coerce_str("dataset", d.get("dataset", "maritime_congestion"))
        dataset_version = _coerce_str("dataset_version",
                                      d.get("dataset_version", "1.0.0"))
        license_str = _coerce_str("license", d.get("license", "unresolved"))
        attribution_raw = d.get("attribution", "")
        attribution = str(attribution_raw).strip() if attribution_raw is not None else ""
        commercial_safe = bool(d.get("commercial_safe", True))

        prov = d.get("provenance") or {}
        if not isinstance(prov, Mapping):
            raise ValueError("provenance must be a mapping")

        comps = d.get("components") or {}
        if not isinstance(comps, Mapping):
            raise ValueError("components must be a mapping")
        for k, v in comps.items():
            if not isinstance(v, (int, float)) or v != v:
                raise ValueError(f"components[{k}] must be a finite number")

        missing = d.get("missing_inputs") or []
        if not isinstance(missing, (list, tuple)):
            raise ValueError("missing_inputs must be a list/tuple")

        # Reject non-bool values explicitly: ``bool("yes")`` is True and
        # would silently coerce, which we do not want for a strict
        # provenance flag.
        synthetic_raw = d.get("synthetic", True)
        if not isinstance(synthetic_raw, bool):
            raise ValueError(
                f"synthetic must be a bool, got {type(synthetic_raw).__name__}"
            )
        synthetic = synthetic_raw
        computation_version = _coerce_str(
            "computation_version",
            d.get("computation_version", "1.0.0"),
        )

        return cls(
            record_id=record_id,
            entity_id=entity_id,
            entity_type=entity_type_raw,
            latitude=lat,
            longitude=lon,
            observed_at=observed_at,
            computed_at=computed_at,
            vessel_count=vessel_count,
            traffic_density=traffic_density,
            cargo_density=cargo_density,
            tanker_density=tanker_density,
            passenger_density=passenger_density,
            traffic_change_ratio=traffic_change_ratio,
            port_call_count=port_call_count,
            utilization_proxy=utilization_proxy,
            average_dwell_hours=average_dwell_hours,
            queue_proxy=queue_proxy,
            arrival_rate_per_day=arrival_rate_per_day,
            weather_available=weather_available,
            weather_quality=weather_quality,
            weather_risk_factor=weather_risk_factor,
            congestion_score=congestion_score,
            congestion_level=level_raw,
            confidence=confidence,
            freshness_state=freshness_state,
            source=source,
            dataset=dataset,
            dataset_version=dataset_version,
            license=license_str,
            attribution=attribution,
            commercial_safe=commercial_safe,
            provenance=dict(prov),
            components=dict(comps),
            missing_inputs=tuple(missing),
            synthetic=synthetic,
            computation_version=computation_version,
        )


__all__ = [
    "CongestionRecord",
    "EntityType",
    "CongestionLevel",
    "level_for_score",
]
