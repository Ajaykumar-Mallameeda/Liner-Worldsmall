"""Phase 6 — Deterministic congestion calculation model.

This module is the only place in the system that computes a
congestion score. The model is:

* **Deterministic** — same inputs → same output, no randomness.
* **Bounded** — score in ``[0, 1]``, level in
  ``{low, moderate, high, severe}``.
* **Explainable** — every record carries a ``components`` mapping
  with the contribution of each signal.
* **Tolerant** — any subset of inputs may be missing; the model
  still produces a valid result with ``confidence`` adjusted.
* **Conservative** — missing signals do NOT create fake congestion.
  When data is poor, ``confidence`` drops and the
  ``missing_inputs`` list grows.

Components:

* ``traffic``        — vessel density (cargo / tanker / passenger)
* ``traffic_change`` — recent change ratio (positive increases score)
* ``port_pressure``  — call intensity + dwell proxy + queue proxy
* ``weather_risk``   — optional risk modifier (NEVER a hard gate)
* ``quality``        — input quality, used to reduce confidence only

The score is a clamped weighted sum of the available component
signals. Weights are configurable via environment variables; the
defaults are documented in :class:`CongestionModelConfig`.

Quality / freshness NEVER inflate the score. They can only
decrease it or decrease ``confidence``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from ..schemas.congestion import (
    CongestionLevel,
    CongestionRecord,
    EntityType,
    level_for_score,
)


# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------


def _env_float(name: str, default: float,
               *, min_value: float = 0.0, max_value: float = 1.0) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return default
    if v < min_value:
        return min_value
    if v > max_value:
        return max_value
    return v


@dataclass(frozen=True)
class CongestionModelConfig:
    """Configurable weights and thresholds.

    Defaults are documented in :mod:`maritime.congestion.model`.
    All weights are in ``[0, 1]`` and are normalized at the point
    of use, so it is safe to leave one weight at 0 to disable a
    component entirely.
    """

    traffic_weight: float = 0.40
    traffic_change_weight: float = 0.10
    port_weight: float = 0.35
    weather_weight: float = 0.15

    # Confidence floor: any score below this is considered
    # under-evidenced and confidence is reduced further.
    confidence_floor: float = 0.30
    # Port-call reference intensity (calls per day) used to normalize
    # ``port_pressure``. Realistic busy hubs sit at 10-30/day.
    port_call_reference_per_day: float = 12.0
    # Dwell-time reference (hours) — a typical commercial port is
    # 24-72 h; higher dwell implies pressure.
    dwell_reference_hours: float = 48.0
    # Traffic-change reference: a +50% change is "strong" signal.
    traffic_change_reference: float = 0.5

    @classmethod
    def from_env(cls) -> "CongestionModelConfig":
        return cls(
            traffic_weight=_env_float("MARITIME_CONGESTION_TRAFFIC_WEIGHT", 0.40),
            traffic_change_weight=_env_float(
                "MARITIME_CONGESTION_TRAFFIC_CHANGE_WEIGHT", 0.10
            ),
            port_weight=_env_float("MARITIME_CONGESTION_PORT_WEIGHT", 0.35),
            weather_weight=_env_float("MARITIME_CONGESTION_WEATHER_WEIGHT", 0.15),
            confidence_floor=_env_float(
                "MARITIME_CONGESTION_CONFIDENCE_FLOOR", 0.30
            ),
            port_call_reference_per_day=_env_float(
                "MARITIME_CONGESTION_PORT_CALL_REF_PER_DAY", 12.0,
                min_value=0.001, max_value=1e6,
            ),
            dwell_reference_hours=_env_float(
                "MARITIME_CONGESTION_DWELL_REF_HOURS", 48.0,
                min_value=0.001, max_value=1e6,
            ),
            traffic_change_reference=_env_float(
                "MARITIME_CONGESTION_TRAFFIC_CHANGE_REF", 0.5,
                min_value=0.001, max_value=1e6,
            ),
        )


# --------------------------------------------------------------------
# Signal inputs
# --------------------------------------------------------------------


@dataclass(frozen=True)
class CongestionSignals:
    """The raw signals a model evaluation consumes.

    All fields are optional. The model treats ``None`` as
    "missing" and routes it into ``missing_inputs``. The
    ``source_quality`` is a value in ``[0, 1]`` representing the
    quality of the upstream input; it is used to gate confidence,
    never to inflate the score.
    """

    entity_type: str  # EntityType.value
    latitude: float
    longitude: float
    observed_at: str  # ISO-8601 UTC

    # Traffic
    traffic_density: Optional[float] = None
    cargo_density: Optional[float] = None
    tanker_density: Optional[float] = None
    passenger_density: Optional[float] = None
    traffic_change_ratio: Optional[float] = None
    vessel_count: Optional[float] = None

    # Port
    port_call_count: Optional[int] = None
    utilization_proxy: Optional[float] = None
    average_dwell_hours: Optional[float] = None
    queue_proxy: Optional[float] = None
    arrival_rate_per_day: Optional[float] = None

    # Weather
    weather_available: bool = False
    weather_quality: Optional[float] = None
    weather_risk_factor: Optional[float] = None

    # Source metadata
    source_quality: float = 0.5
    freshness_state: str = "unknown"
    source: str = "derived"
    dataset_version: str = "1.0.0"
    license: str = "unresolved"
    attribution: str = ""
    commercial_safe: bool = True
    provenance: Mapping[str, Any] = field(default_factory=dict)

    synthetic: bool = True


# --------------------------------------------------------------------
# Model result
# --------------------------------------------------------------------


@dataclass(frozen=True)
class CongestionEvaluation:
    """Outcome of evaluating one :class:`CongestionSignals` object.

    The evaluation is fully self-describing. ``components`` maps
    every signal to its bounded ``[0, 1]`` contribution. ``missing``
    lists the names of inputs that were ``None``. ``score`` is the
    final clamped score, and ``level`` is the banded classification.
    """

    score: float
    level: str  # CongestionLevel.value
    confidence: float
    components: Dict[str, float]
    missing: List[str]
    weather_active: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "level": self.level,
            "confidence": round(self.confidence, 4),
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "missing": list(self.missing),
            "weather_active": self.weather_active,
        }


# --------------------------------------------------------------------
# Normalization helpers
# --------------------------------------------------------------------


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return float(v)


def _normalize_traffic(signals: CongestionSignals) -> Tuple[float, List[str]]:
    """Reduce vessel densities to a single bounded traffic component.

    Returns ``(component, missing)``. ``component`` is in ``[0, 1]``.
    """
    parts: List[float] = []
    missing: List[str] = []
    for name, v in (
        ("traffic_density", signals.traffic_density),
        ("cargo_density", signals.cargo_density),
        ("tanker_density", signals.tanker_density),
        ("passenger_density", signals.passenger_density),
    ):
        if v is None:
            missing.append(name)
        else:
            parts.append(_clamp01(float(v)))
    if not parts:
        return 0.0, missing
    return _clamp01(sum(parts) / len(parts)), missing


def _normalize_traffic_change(
    signals: CongestionSignals, ref: float
) -> Tuple[float, List[str]]:
    if signals.traffic_change_ratio is None:
        return 0.0, ["traffic_change_ratio"]
    ratio = float(signals.traffic_change_ratio)
    if ratio < 0.0:
        # Decreasing traffic does not contribute positively; clamp to 0
        # (the change direction is informational; congestion focuses on
        # the absolute current pressure).
        return 0.0, []
    return _clamp01(ratio / ref), []


def _normalize_port_pressure(
    signals: CongestionSignals,
    *,
    call_ref: float, dwell_ref: float,
) -> Tuple[float, List[str]]:
    parts: List[float] = []
    missing: List[str] = []
    if signals.arrival_rate_per_day is None and signals.port_call_count is None:
        missing.append("port_calls")
    else:
        rate = signals.arrival_rate_per_day
        if rate is None and signals.port_call_count is not None:
            # Heuristic: convert an absolute count into a rate by
            # assuming a weekly observation window. The result is
            # imperfect but it is a documented fallback that does
            # NOT introduce fake congestion — it only produces a
            # softer pressure value.
            rate = float(signals.port_call_count) / 7.0
        if rate is not None:
            parts.append(_clamp01(float(rate) / call_ref))
    if signals.utilization_proxy is None:
        missing.append("utilization_proxy")
    else:
        parts.append(_clamp01(float(signals.utilization_proxy)))
    if signals.average_dwell_hours is None:
        missing.append("average_dwell_hours")
    else:
        # Normalize to [0, 1] using the reference dwell time.
        parts.append(_clamp01(float(signals.average_dwell_hours) / dwell_ref))
    if signals.queue_proxy is None:
        missing.append("queue_proxy")
    else:
        # queue_proxy is a non-negative scalar; clamp directly.
        # We do not invent a unit; we treat its raw value as
        # already-bounded (caller's responsibility).
        parts.append(_clamp01(float(signals.queue_proxy)))
    if not parts:
        return 0.0, missing
    return _clamp01(sum(parts) / len(parts)), missing


def _normalize_weather(signals: CongestionSignals) -> Tuple[float, bool, List[str]]:
    if not signals.weather_available:
        return 0.0, False, ["weather"]
    if signals.weather_risk_factor is None:
        # Weather reported as available but no risk value — treat as
        # missing for explainability, do not invent a value.
        return 0.0, False, ["weather_risk_factor"]
    if signals.weather_quality is not None and signals.weather_quality < 0.3:
        # Weather is too poor to trust; treat as inactive.
        return 0.0, False, ["weather_low_quality"]
    return _clamp01(float(signals.weather_risk_factor)), True, []


# --------------------------------------------------------------------
# Model
# --------------------------------------------------------------------


def _normalize_weights(config: CongestionModelConfig) -> Dict[str, float]:
    raw = {
        "traffic": max(0.0, config.traffic_weight),
        "traffic_change": max(0.0, config.traffic_change_weight),
        "port_pressure": max(0.0, config.port_weight),
        "weather_risk": max(0.0, config.weather_weight),
    }
    total = sum(raw.values())
    if total <= 0.0:
        # Pathological: caller disabled every weight. Return zeros.
        return {k: 0.0 for k in raw}
    return {k: v / total for k, v in raw.items()}


def evaluate_congestion(
    signals: CongestionSignals,
    *,
    config: Optional[CongestionModelConfig] = None,
) -> CongestionEvaluation:
    """Evaluate the deterministic congestion model.

    Returns a :class:`CongestionEvaluation`. Never raises.
    """
    cfg = config or CongestionModelConfig()
    weights = _normalize_weights(cfg)

    missing: List[str] = []

    # Traffic
    traffic_value, traffic_missing = _normalize_traffic(signals)
    missing.extend(traffic_missing)

    # Traffic change
    change_value, change_missing = _normalize_traffic_change(
        signals, cfg.traffic_change_reference
    )
    missing.extend(change_missing)

    # Port pressure
    port_value, port_missing = _normalize_port_pressure(
        signals,
        call_ref=cfg.port_call_reference_per_day,
        dwell_ref=cfg.dwell_reference_hours,
    )
    missing.extend(port_missing)

    # Weather
    weather_value, weather_active, weather_missing = _normalize_weather(signals)
    missing.extend(weather_missing)

    # Score: weighted sum of available components. When a component
    # is entirely missing (its "missing" flag was returned) we
    # redistribute its weight across the other available components
    # so the score never silently becomes 0.0 just because one
    # upstream source was absent. The redistribution is bounded by
    # the active weights only.
    components = {
        "traffic": traffic_value,
        "traffic_change": change_value,
        "port_pressure": port_value,
        "weather_risk": weather_value,
    }
    active_weights = dict(weights)
    if not weather_active:
        # Drop the weather weight — it has no signal.
        active_weights["weather_risk"] = 0.0
    if traffic_missing and not any(
        x not in traffic_missing for x in ("traffic_density",)
    ) and len(traffic_missing) >= 4:
        # All traffic channels missing → redistribute its weight.
        active_weights["traffic"] = 0.0
    if port_missing and len(port_missing) >= 4:
        active_weights["port_pressure"] = 0.0

    total_active = sum(active_weights.values())
    if total_active <= 0.0:
        score = 0.0
    else:
        raw = 0.0
        for k, v in components.items():
            raw += active_weights[k] * v
        score = _clamp01(raw / total_active)

    # Confidence: starts at 1.0 and drops as inputs go missing or
    # as the source quality / freshness degrades.
    base_components = 4
    active_components = base_components - sum(
        1 for k in (
            "traffic", "traffic_change", "port_pressure", "weather_risk"
        )
        if active_weights[k] == 0.0
    )
    coverage_ratio = active_components / float(base_components)
    quality = _clamp01(float(signals.source_quality))
    # Freshness penalty: stale / offline / invalid pull confidence down.
    freshness_penalty = 0.0
    if signals.freshness_state == "stale":
        freshness_penalty = 0.20
    elif signals.freshness_state == "degraded":
        freshness_penalty = 0.10
    elif signals.freshness_state in ("offline", "invalid"):
        freshness_penalty = 0.40
    confidence = _clamp01(
        coverage_ratio * quality - freshness_penalty
    )
    # Apply the floor — never below the configured floor unless
    # everything is missing.
    if confidence < cfg.confidence_floor and active_components > 0:
        confidence = cfg.confidence_floor

    # Deduplicate missing list while preserving order.
    seen = set()
    deduped_missing: List[str] = []
    for m in missing:
        if m in seen:
            continue
        seen.add(m)
        deduped_missing.append(m)

    level = level_for_score(score).value
    return CongestionEvaluation(
        score=score,
        level=level,
        confidence=confidence,
        components=components,
        missing=deduped_missing,
        weather_active=weather_active,
    )


def build_record(
    signals: CongestionSignals,
    *,
    config: Optional[CongestionModelConfig] = None,
    record_id: Optional[str] = None,
    computed_at: Optional[str] = None,
    entity_id: Optional[str] = None,
) -> CongestionRecord:
    """Build a :class:`CongestionRecord` from raw signals.

    Convenience wrapper around :func:`evaluate_congestion` that
    also serializes the result into the canonical record shape.
    """
    from datetime import datetime, timezone
    eval_result = evaluate_congestion(signals, config=config)
    if computed_at is None:
        computed_at = datetime.now(tz=timezone.utc).isoformat()
    if record_id is None:
        rid_src = entity_id or f"{signals.entity_type}@{signals.latitude:.3f},{signals.longitude:.3f}"
        record_id = f"cong-{rid_src}-{computed_at}"
    if entity_id is None:
        entity_id = f"{signals.entity_type}:{signals.latitude:.4f},{signals.longitude:.4f}"
    components_out: Dict[str, float] = dict(eval_result.components)
    # Weights are stored separately on the record (not inside the
    # `components` mapping, which is reserved for signal→value
    # numbers) so the schema can stay strict. The record's
    # `provenance` mapping already accepts arbitrary keys, so we
    # tuck the weights there under a documented sub-key.
    prov = dict(signals.provenance)
    if config is not None:
        weights_norm = _normalize_weights(config)
        prov["weights"] = {k: round(v, 4) for k, v in weights_norm.items()}
    if signals.synthetic:
        prov.setdefault("synthetic_label", "synthetic")
    return CongestionRecord(
        record_id=record_id,
        entity_id=entity_id,
        entity_type=signals.entity_type,
        latitude=signals.latitude,
        longitude=signals.longitude,
        observed_at=signals.observed_at,
        computed_at=computed_at,
        vessel_count=signals.vessel_count,
        traffic_density=signals.traffic_density,
        cargo_density=signals.cargo_density,
        tanker_density=signals.tanker_density,
        passenger_density=signals.passenger_density,
        traffic_change_ratio=signals.traffic_change_ratio,
        port_call_count=signals.port_call_count,
        utilization_proxy=signals.utilization_proxy,
        average_dwell_hours=signals.average_dwell_hours,
        queue_proxy=signals.queue_proxy,
        arrival_rate_per_day=signals.arrival_rate_per_day,
        weather_available=signals.weather_available,
        weather_quality=signals.weather_quality,
        weather_risk_factor=signals.weather_risk_factor,
        congestion_score=eval_result.score,
        congestion_level=eval_result.level,
        confidence=eval_result.confidence,
        freshness_state=signals.freshness_state,
        source=signals.source,
        dataset="maritime_congestion",
        dataset_version=signals.dataset_version,
        license=signals.license,
        attribution=signals.attribution,
        commercial_safe=signals.commercial_safe,
        provenance=prov,
        components=components_out,
        missing_inputs=tuple(eval_result.missing),
        synthetic=signals.synthetic,
        computation_version="1.0.0",
    )


__all__ = [
    "CongestionModelConfig",
    "CongestionSignals",
    "CongestionEvaluation",
    "evaluate_congestion",
    "build_record",
]
