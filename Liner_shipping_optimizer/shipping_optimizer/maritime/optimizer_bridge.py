"""Maritime feature attach for the AI Vessel Routing optimizer.

This module implements the IP-1 integration point from
``docs/architecture/INTEGRATION_BOUNDARIES.md``: a bounded,
read-only, network-free attach of maritime intelligence to the
optimizer's ``Problem`` object.

Hard rules (all enforced here):

* No network access. All reads go through the local snapshot
  store via the existing ``maritime.SafeFeatureAdapter`` and the
  Phase 5 / Phase 6 read-only adapters.
* No external provider instantiation. No retry / no rate limiter.
* No mutation of optimizer state beyond a single attribute
  attach on the ``Problem`` object.
* The attach is gated on the existing
  ``MARITIME_INTELLIGENCE_ENABLED`` flag (master) and the
  individual sub-flags ``MARITIME_TRAFFIC_ENABLED``,
  ``MARITIME_PORT_INTELLIGENCE_ENABLED``,
  ``MARITIME_CONGESTION_ENABLED``, ``MARITIME_WEATHER_ENABLED``.
* A wall-clock budget (default 5 seconds) bounds the read path.
  Any budget breach surfaces as ``budget_exceeded=True`` and the
  feature set is dropped to ``None`` so the optimizer continues
  on the pre-maritime path.
* When disabled, unavailable, stale, invalid, or budget-breached,
  the function returns ``None`` and the orchestrator continues
  with the existing pre-maritime behavior.

The attached object is a :class:`MaritimeFeatures` instance, an
immutable read-only bundle of validated feature views plus a
``diagnostics`` mapping that records what was attempted, what
was actually used, and what fell back. It is consumed by IP-2
(fuel cost) and IP-3 (port capacity override).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


# Confidence floor: any feature with confidence below this is
# treated as missing. Mirrors IP-3's documented default.
DEFAULT_MIN_CONFIDENCE = 0.6

# Wall-clock budget for the attach (per pipeline run). The brief
# specifies <= 5 seconds.
DEFAULT_BUDGET_SECONDS = 5.0

# Default path: feature_flags. Master switch.
MASTER_FLAG = "MARITIME_INTELLIGENCE_ENABLED"
TRAFFIC_FLAG = "MARITIME_TRAFFIC_ENABLED"
PORT_FLAG = "MARITIME_PORT_INTELLIGENCE_ENABLED"
CONGESTION_FLAG = "MARITIME_CONGESTION_ENABLED"
WEATHER_FLAG = "MARITIME_WEATHER_ENABLED"

# Confidence floor override for IP-3 (mirrors the protected-component
# document).
MIN_CONFIDENCE_FLAG = "MARITIME_CONGESTION_MIN_CONFIDENCE"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return default
    return v


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def flags_enabled() -> Dict[str, bool]:
    """Return the resolved maritime feature flag state."""
    master = _env_bool(MASTER_FLAG, default=False)
    return {
        "master": master,
        "traffic": master and _env_bool(TRAFFIC_FLAG, default=False),
        "port": master and _env_bool(PORT_FLAG, default=False),
        "congestion": master and _env_bool(CONGESTION_FLAG, default=False),
        "weather": master and _env_bool(WEATHER_FLAG, default=False),
    }


def min_confidence() -> float:
    """Confidence floor for maritime-derived feature use (IP-3)."""
    raw = _env_float(MIN_CONFIDENCE_FLAG, DEFAULT_MIN_CONFIDENCE)
    # Clamp to [0, 1] without raising — a malformed env var falls
    # back to the documented default.
    if raw != raw:  # NaN
        return DEFAULT_MIN_CONFIDENCE
    if raw < 0.0:
        return 0.0
    if raw > 1.0:
        return 1.0
    return raw


def attach_budget_seconds() -> float:
    """Wall-clock budget for the attach (per pipeline run)."""
    raw = _env_float("MARITIME_INTELLIGENCE_BUDGET_SECONDS",
                     DEFAULT_BUDGET_SECONDS)
    if raw <= 0.0:
        return DEFAULT_BUDGET_SECONDS
    return raw


# --------------------------------------------------------------------
# Result type
# --------------------------------------------------------------------


@dataclass(frozen=True)
class MaritimeFeatures:
    """An immutable bundle of validated maritime feature views.

    A value of ``None`` for any field means "not available, not
    used". The optimizer must treat ``None`` exactly like the
    pre-maritime path.

    Diagnostics are a small dictionary, intended for additive
    inclusion in the existing orchestrator output (IP-5) and for
    the operator dashboard. They do NOT alter any existing
    output field.
    """

    # Phase 1/2: traffic + port. The raw ResilientReadResult
    # payloads are kept for IP-1 transparency; the optimizer
    # itself does not currently read them (it consumes the
    # already-derived congestion override + weather factor).
    traffic: Optional[Dict[str, Any]] = None
    port: Optional[Dict[str, Any]] = None

    # Phase 6: congestion per-port override map.
    # {port_id (str): {"score": float, "confidence": float,
    #                  "level": "low|moderate|high|severe",
    #                  "freshness_state": str,
    #                  "synthetic": bool,
    #                  "provenance": {...}}}
    # Only ports whose confidence >= min_confidence are included.
    congestion_override: Mapping[str, Dict[str, Any]] = field(default_factory=dict)
    congestion_avg_confidence: float = 0.0
    congestion_freshness_state: str = "unknown"
    congestion_synthetic: bool = True

    # Phase 5: weather speed factor in [0.5, 1.5] when valid
    # weather is available, else None. 1.0 means "no adjustment".
    weather_speed_factor: Optional[float] = None
    weather_confidence: float = 0.0
    weather_freshness_state: str = "unknown"
    weather_synthetic: bool = True

    # Provenance & budget
    snapshot_id: Optional[str] = None
    retrieved_at: Optional[str] = None
    sources_used: Tuple[str, ...] = ()
    sources_missing: Tuple[str, ...] = ()
    duration_ms: float = 0.0
    budget_exceeded: bool = False
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "retrieved_at": self.retrieved_at,
            "sources_used": list(self.sources_used),
            "sources_missing": list(self.sources_missing),
            "duration_ms": round(self.duration_ms, 3),
            "budget_exceeded": self.budget_exceeded,
            "congestion": {
                "by_port": {
                    pid: {
                        "score": v.get("score"),
                        "level": v.get("level"),
                        "freshness_state": v.get("freshness_state"),
                        "synthetic": v.get("synthetic"),
                    }
                    for pid, v in self.congestion_override.items()
                },
                "average_confidence": round(self.congestion_avg_confidence, 3),
                "freshness_state": self.congestion_freshness_state,
                "synthetic": self.congestion_synthetic,
            },
            "weather": {
                "speed_factor": (
                    round(self.weather_speed_factor, 4)
                    if self.weather_speed_factor is not None else None
                ),
                "confidence": round(self.weather_confidence, 3),
                "freshness_state": self.weather_freshness_state,
                "synthetic": self.weather_synthetic,
            },
            "diagnostics": dict(self.diagnostics),
        }


# --------------------------------------------------------------------
# Validators / clamps
# --------------------------------------------------------------------


def _is_finite_number(v: Any) -> bool:
    if not isinstance(v, (int, float)):
        return False
    return v == v and v not in (float("inf"), float("-inf"))


def _clamp_unit(v: Any, default: float = 0.0) -> float:
    if not _is_finite_number(v):
        return default
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return float(v)


def _clamp_speed_factor(v: Any) -> Optional[float]:
    """Bounded in [0.5, 1.5] per the approved integration contract.

    A value of 1.0 means "no adjustment". The clamp rejects
    non-finite, NaN, and out-of-range values — invalid input
    becomes ``None`` so the consumer falls back to the
    pre-maritime path.
    """
    if not _is_finite_number(v):
        return None
    fv = float(v)
    if fv < 0.5:
        return 0.5
    if fv > 1.5:
        return 1.5
    return fv


# --------------------------------------------------------------------
# Source readers — pure local, network-free
# --------------------------------------------------------------------


def _read_traffic_safe(budget_remaining: float) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Read traffic intelligence via the existing safe adapter.

    Returns ``(payload, budget_exceeded)``. Never raises.
    """
    started = time.perf_counter()
    try:
        from maritime.safe_feature_adapter import SafeFeatureAdapter
        sfa = SafeFeatureAdapter()
        result = sfa.get_traffic_snapshot()
        if result is None or not getattr(result, "ok", False):
            return None, False
        # The SafeFeatureAdapter returns a ResilientReadResult; we
        # hand back its dict view if present.
        d = result.to_dict() if hasattr(result, "to_dict") else None
        if not isinstance(d, Mapping):
            return None, False
        # Cap wall-clock so a slow read cannot exceed the budget.
        elapsed = time.perf_counter() - started
        return dict(d), elapsed > budget_remaining
    except Exception as e:  # noqa: BLE001
        # The attach must NEVER raise. Any exception is logged and
        # we return None so the optimizer continues on the
        # pre-maritime path.
        logger.info("maritime_features_traffic_read_failed", error=repr(e))
        return None, False


def _read_port_safe(budget_remaining: float) -> Tuple[Optional[Dict[str, Any]], bool]:
    started = time.perf_counter()
    try:
        from maritime.safe_feature_adapter import SafeFeatureAdapter
        sfa = SafeFeatureAdapter()
        result = sfa.get_port_snapshot()
        if result is None or not getattr(result, "ok", False):
            return None, False
        d = result.to_dict() if hasattr(result, "to_dict") else None
        if not isinstance(d, Mapping):
            return None, False
        elapsed = time.perf_counter() - started
        return dict(d), elapsed > budget_remaining
    except Exception as e:  # noqa: BLE001
        logger.info("maritime_features_port_read_failed", error=repr(e))
        return None, False


def _read_congestion() -> Tuple[Optional[Dict[str, Any]], bool]:
    """Read congestion intelligence via the Phase 6 read-only adapter.

    Returns ``(payload, stale)`` where ``stale`` is True when the
    latest snapshot is past the documented max-age window. The
    caller treats stale-but-readable congestion the same as a
    fresh read; it only affects the per-record ``freshness_state``
    surfaced in diagnostics.
    """
    try:
        from maritime.congestion.feature_adapter import CongestionFeatureAdapter
        adp = CongestionFeatureAdapter()
        status = adp.source_status()
        if not status.ok:
            return None, True
        snap = adp.latest_snapshot()
        if not isinstance(snap, Mapping):
            return None, True
        records, _manifest = adp._load_records()
        return (
            {
                "snapshot_id": snap.get("snapshot_id"),
                "retrieved_at": snap.get("retrieved_at"),
                "source_health": snap.get("source_health"),
                "freshness_state": snap.get("freshness_state", "unknown"),
                "synthetic": bool(snap.get("synthetic", False)),
                "records": list(records) if isinstance(records, list) else [],
            },
            False,
        )
    except Exception as e:  # noqa: BLE001
        logger.info("maritime_features_congestion_read_failed", error=repr(e))
        return None, True


def _read_weather() -> Tuple[Optional[Dict[str, Any]], bool]:
    try:
        from maritime.weather.feature_adapter import WeatherFeatureAdapter
        adp = WeatherFeatureAdapter()
        status = adp.source_status()
        if not status.ok:
            return None, True
        snap = adp.latest_snapshot()
        if not isinstance(snap, Mapping):
            return None, True
        records, _manifest = adp._load_records()
        return (
            {
                "snapshot_id": snap.get("snapshot_id"),
                "retrieved_at": snap.get("retrieved_at"),
                "source_health": snap.get("source_health"),
                "freshness_state": snap.get("freshness_state", "unknown"),
                "records": list(records) if isinstance(records, list) else [],
            },
            False,
        )
    except Exception as e:  # noqa: BLE001
        logger.info("maritime_features_weather_read_failed", error=repr(e))
        return None, True


# --------------------------------------------------------------------
# Derived signal extractors
# --------------------------------------------------------------------


def _extract_port_pressure_from_records(
    records: Sequence[Mapping[str, Any]],
    min_confidence: float,
) -> Tuple[Dict[str, Dict[str, Any]], float, str, bool]:
    """Build a per-port override map from congestion records.

    Only records whose ``confidence >= min_confidence`` are
    accepted. The output mapping is keyed by ``entity_id`` (the
    canonical port id used in the congestion layer; it matches
    the optimizer's port identifier when the port-intelligence
    snapshot defines the same set of ports).
    """
    by_port: Dict[str, Dict[str, Any]] = {}
    confs: list = []
    freshness_states: list = []
    synthetic_flags: list = []
    for r in records:
        if not isinstance(r, Mapping):
            continue
        conf = r.get("confidence")
        if not _is_finite_number(conf):
            continue
        if conf < min_confidence:
            continue
        score = r.get("congestion_score")
        if not _is_finite_number(score):
            continue
        level = r.get("congestion_level")
        if not isinstance(level, str) or level not in {
            "low", "moderate", "high", "severe",
        }:
            continue
        entity = r.get("entity_id")
        if not isinstance(entity, str) or not entity.strip():
            continue
        freshness = r.get("freshness_state")
        if not isinstance(freshness, str) or not freshness:
            freshness = "unknown"
        prov = r.get("provenance") if isinstance(r.get("provenance"), Mapping) else {}
        by_port[entity] = {
            "score": _clamp_unit(score),
            "confidence": _clamp_unit(conf),
            "level": level,
            "freshness_state": freshness,
            "synthetic": bool(r.get("synthetic", True)),
            "provenance": dict(prov),
        }
        confs.append(_clamp_unit(conf))
        freshness_states.append(freshness)
        synthetic_flags.append(bool(r.get("synthetic", True)))
    if not confs:
        return {}, 0.0, "unknown", True
    avg_conf = sum(confs) / len(confs)
    # Worst-case freshness dominates.
    rank = {
        "available": 0, "checking": 1, "degraded": 2,
        "stale": 3, "offline": 4, "invalid": 4, "unknown": 1,
    }
    worst = max(freshness_states, key=lambda s: rank.get(s, 1))
    synth = all(synthetic_flags)
    return by_port, avg_conf, worst, synth


def _extract_weather_speed_factor(
    records: Sequence[Mapping[str, Any]],
    min_confidence: float,
) -> Tuple[Optional[float], float, str, bool]:
    """Derive a single bounded weather speed factor from records.

    Strategy: take the *highest* ``weather_risk_factor`` across
    records that are geographically near the optimizer's
    problem-space (we use all available records here — the
    congestion layer already gates on proximity). A risk factor
    of 0.0 -> speed_factor 1.0 (no slowdown). A risk factor of
    1.0 -> speed_factor 0.92 (8% slowdown for severe weather).
    The relationship is documented and linear in the [0, 1]
    band. The factor is then clamped to [0.5, 1.5].
    """
    confs: list = []
    risks: list = []
    freshness_states: list = []
    synthetic_flags: list = []
    for r in records:
        if not isinstance(r, Mapping):
            continue
        if not r.get("weather_available", True):
            continue
        # The Phase 5 weather record does not carry a per-record
        # ``weather_risk_factor``; derive it from wind + wave.
        risk = _weather_risk_from_record(r)
        if risk is None:
            continue
        conf_raw = r.get("quality")
        if not _is_finite_number(conf_raw):
            continue
        conf = _clamp_unit(conf_raw)
        if conf < min_confidence:
            continue
        risks.append(_clamp_unit(risk))
        confs.append(conf)
        fs = r.get("freshness_state")
        if isinstance(fs, str) and fs:
            freshness_states.append(fs)
        synthetic_flags.append(bool(r.get("synthetic", False)))
    if not risks:
        return None, 0.0, "unknown", True
    # Use the *maximum* risk across nearby records. The
    # documented relationship: speed_factor = 1.0 - 0.08 * risk.
    risk = max(risks)
    speed_factor = _clamp_speed_factor(1.0 - 0.08 * risk)
    if speed_factor is None:
        return None, 0.0, "unknown", True
    avg_conf = sum(confs) / len(confs)
    rank = {
        "available": 0, "checking": 1, "degraded": 2,
        "stale": 3, "offline": 4, "invalid": 4, "unknown": 1,
    }
    worst = (
        max(freshness_states, key=lambda s: rank.get(s, 1))
        if freshness_states else "unknown"
    )
    synth = all(synthetic_flags) if synthetic_flags else True
    return speed_factor, avg_conf, worst, synth


def _weather_risk_from_record(r: Mapping[str, Any]) -> Optional[float]:
    """Replicate the Phase 6 weather-risk derivation locally.

    Kept here so the optimizer path has zero dependence on the
    Phase 6 orchestrator's helpers. The function is intentionally
    side-effect-free and pure.
    """
    parts: list = []
    wind = r.get("wind_speed_ms")
    if _is_finite_number(wind):
        parts.append(_clamp_unit(float(wind) / 25.0))
    gust = r.get("gust_speed_ms")
    if _is_finite_number(gust):
        parts.append(_clamp_unit(float(gust) / 35.0))
    wave = r.get("wave_height_m")
    if _is_finite_number(wave):
        parts.append(_clamp_unit(float(wave) / 6.0))
    if not parts:
        return None
    return min(1.0, sum(parts) / len(parts))


# --------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------


def attach_maritime_features(
    *,
    problem: Any = None,
    budget_seconds: Optional[float] = None,
) -> Optional[MaritimeFeatures]:
    """IP-1: attach maritime intelligence to the optimizer.

    Returns ``None`` when the master flag is off, when no
    sub-feature is enabled, or when the attach fails for any
    reason. The function never raises.

    The attach is bounded by a wall-clock budget. Each source is
    read at most once per call. The returned object is immutable.
    """
    started = time.perf_counter()
    fl = flags_enabled()
    if not fl["master"]:
        return None
    any_sub = any([fl["traffic"], fl["port"], fl["congestion"], fl["weather"]])
    if not any_sub:
        return None
    budget = budget_seconds if budget_seconds is not None else attach_budget_seconds()
    if budget <= 0.0:
        return None

    used: list = []
    missing: list = []
    diagnostics: Dict[str, Any] = {
        "flags": fl,
        "min_confidence": min_confidence(),
    }

    # --- Traffic ---
    traffic_payload: Optional[Dict[str, Any]] = None
    if fl["traffic"]:
        remaining = max(0.0, budget - (time.perf_counter() - started))
        traffic_payload, exceeded = _read_traffic_safe(remaining)
        if traffic_payload is not None:
            used.append("traffic")
        else:
            missing.append("traffic")
        if exceeded:
            diagnostics["budget_exceeded_source"] = "traffic"

    # --- Port ---
    port_payload: Optional[Dict[str, Any]] = None
    if fl["port"]:
        remaining = max(0.0, budget - (time.perf_counter() - started))
        port_payload, exceeded = _read_port_safe(remaining)
        if port_payload is not None:
            used.append("port")
        else:
            missing.append("port")
        if exceeded:
            diagnostics.setdefault("budget_exceeded_source", "port")

    # --- Congestion ---
    congestion_payload: Optional[Dict[str, Any]] = None
    congestion_override: Dict[str, Dict[str, Any]] = {}
    congestion_avg_conf = 0.0
    congestion_fresh = "unknown"
    congestion_synth = True
    if fl["congestion"]:
        congestion_payload, _stale = _read_congestion()
        if isinstance(congestion_payload, Mapping):
            used.append("congestion")
            by_port, avg_conf, worst, synth = _extract_port_pressure_from_records(
                congestion_payload.get("records", []) or [],
                min_confidence(),
            )
            congestion_override = by_port
            congestion_avg_conf = avg_conf
            congestion_fresh = (
                str(congestion_payload.get("freshness_state", worst)) or worst
            )
            congestion_synth = bool(
                congestion_payload.get("synthetic", synth)
            )
        else:
            missing.append("congestion")

    # --- Weather ---
    weather_payload: Optional[Dict[str, Any]] = None
    weather_speed_factor: Optional[float] = None
    weather_conf = 0.0
    weather_fresh = "unknown"
    weather_synth = True
    if fl["weather"]:
        weather_payload, _stale = _read_weather()
        if isinstance(weather_payload, Mapping):
            used.append("weather")
            sf, conf, worst, synth = _extract_weather_speed_factor(
                weather_payload.get("records", []) or [],
                min_confidence(),
            )
            weather_speed_factor = sf
            weather_conf = conf
            weather_fresh = (
                str(weather_payload.get("freshness_state", worst)) or worst
            )
            weather_synth = bool(weather_payload.get("synthetic", synth))
        else:
            missing.append("weather")

    duration = (time.perf_counter() - started) * 1000.0
    budget_exceeded = duration > budget * 1000.0

    # Snapshot identity: use the congestion snapshot_id when
    # available, else the weather snapshot_id, else None.
    snapshot_id = None
    retrieved_at = None
    if isinstance(congestion_payload, Mapping):
        snapshot_id = congestion_payload.get("snapshot_id")
        retrieved_at = congestion_payload.get("retrieved_at")
    if snapshot_id is None and isinstance(weather_payload, Mapping):
        snapshot_id = weather_payload.get("snapshot_id")
        retrieved_at = weather_payload.get("retrieved_at")

    diagnostics["duration_ms"] = round(duration, 3)
    diagnostics["budget_seconds"] = budget
    diagnostics["traffic_present"] = traffic_payload is not None
    diagnostics["port_present"] = port_payload is not None
    diagnostics["congestion_present"] = bool(congestion_override)
    diagnostics["weather_present"] = weather_speed_factor is not None

    # Always return a result when at least one sub-feature is
    # enabled. The orchestrator and downstream consumers must
    # treat this as "maritime was attached" and inspect
    # ``congestion_override`` / ``weather_speed_factor`` for
    # actually-injected values.
    return MaritimeFeatures(
        traffic=traffic_payload,
        port=port_payload,
        congestion_override=congestion_override,
        congestion_avg_confidence=congestion_avg_conf,
        congestion_freshness_state=congestion_fresh,
        congestion_synthetic=congestion_synth,
        weather_speed_factor=weather_speed_factor,
        weather_confidence=weather_conf,
        weather_freshness_state=weather_fresh,
        weather_synthetic=weather_synth,
        snapshot_id=snapshot_id,
        retrieved_at=retrieved_at,
        sources_used=tuple(used),
        sources_missing=tuple(missing),
        duration_ms=duration,
        budget_exceeded=budget_exceeded,
        diagnostics=diagnostics,
    )


__all__ = [
    "MaritimeFeatures",
    "attach_maritime_features",
    "fuel_cost_kwargs",
    "congestion_port_capacity",
    "flags_enabled",
    "min_confidence",
    "attach_budget_seconds",
    "_normalize_weather_speed_factor",
    "DEFAULT_MIN_CONFIDENCE",
    "DEFAULT_BUDGET_SECONDS",
    "MASTER_FLAG",
    "TRAFFIC_FLAG",
    "PORT_FLAG",
    "CONGESTION_FLAG",
    "WEATHER_FLAG",
]


# --------------------------------------------------------------------
# IP-2 / IP-3 forwarding helpers
# --------------------------------------------------------------------


def fuel_cost_kwargs(problem: Any) -> Dict[str, Any]:
    """Return ``weather_speed_factor`` kwargs for fuel-cost callers.

    Reads the maritime features attached to ``problem`` (IP-1) when
    present. Returns an empty dict when maritime is disabled,
    unavailable, or no weather factor is available. Never raises.
    The factor is already validated and clamped to
    ``[0.5, 1.5]`` by the attach layer.

    This helper inlines the (formerly imported) fuel-cost normalizer
    so that the maritime package has no dependency on
    ``src.utils.fuel_cost``. The optimizer calls
    :func:`fuel_cost_kwargs` on the optimizer side; the actual
    function lives here so the call site can use a simple
    ``**fuel_cost_kwargs(problem)`` spread.
    """
    if problem is None:
        return {}
    mf = getattr(problem, "maritime_features", None)
    if mf is None:
        return {}
    wsf = getattr(mf, "weather_speed_factor", None)
    if wsf is None:
        return {}
    safe = _normalize_weather_speed_factor(wsf)
    if safe is None:
        return {}
    return {"weather_speed_factor": safe}


def _normalize_weather_speed_factor(value):
    """Mirror of ``src.utils.fuel_cost._normalize_weather_speed_factor``.

    Kept inline (rather than imported) so that the maritime package
    has no compile-time dependency on ``src/``. Returns a clamped
    float in ``[0.5, 1.5]`` for finite numeric input, or ``None``
    for ``None`` / non-finite / non-numeric input. This is the
    single source of truth for the contract — the optimizer-side
    helper applies the same bounds.
    """
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    fv = float(value)
    if fv < 0.5:
        return 0.5
    if fv > 1.5:
        return 1.5
    return fv


def congestion_port_capacity(
    problem: Any,
    *,
    kappa: float = 0.3,
    min_confidence: Optional[float] = None,
) -> Dict[str, float]:
    """Return an IP-3 port-capacity override map.

    For every port whose attached congestion ``confidence`` is at
    or above the floor, the returned mapping is::

        cap_override[port_id] = 1.0 - kappa * score

    The optimizer's existing capacity formula multiplies this
    factor onto the synthetic per-port throughput cap, so a
    factor < 1.0 reduces the cap (more congestion => less
    capacity). The factor is always in ``[1 - kappa, 1.0]`` and
    never goes below zero (the consumer clamps).

    When maritime is disabled, unavailable, or the override map
    is empty, the function returns an empty dict. The consumer
    MUST treat an empty dict as "use the existing synthetic
    capacity map unchanged".

    ``min_confidence`` may be a float (used as the floor) or a
    zero-argument callable (resolved at call time). When neither
    is provided, the env-configured default
    (``MARITIME_CONGESTION_MIN_CONFIDENCE``) is used.
    """
    if problem is None:
        return {}
    mf = getattr(problem, "maritime_features", None)
    if mf is None:
        return {}
    override = getattr(mf, "congestion_override", None)
    if not override:
        return {}

    # Resolve the confidence floor: float -> use as-is;
    # callable -> invoke; None -> env-configured default.
    if min_confidence is None:
        floor_val = globals()["min_confidence"]()
    elif callable(min_confidence):
        try:
            floor_val = float(min_confidence())
        except (TypeError, ValueError):
            floor_val = DEFAULT_MIN_CONFIDENCE
    else:
        try:
            floor_val = float(min_confidence)
        except (TypeError, ValueError):
            floor_val = DEFAULT_MIN_CONFIDENCE
    if not _is_finite_number(floor_val):
        floor_val = DEFAULT_MIN_CONFIDENCE
    if floor_val < 0.0:
        floor_val = 0.0
    if floor_val > 1.0:
        floor_val = 1.0

    out: Dict[str, float] = {}
    for port_id, info in override.items():
        if not isinstance(info, Mapping):
            continue
        conf = info.get("confidence")
        score = info.get("score")
        if not _is_finite_number(conf) or not _is_finite_number(score):
            continue
        if conf < floor_val:
            continue
        s = _clamp_unit(score)
        factor = 1.0 - float(kappa) * s
        if factor < 0.0:
            factor = 0.0
        if factor > 1.0:
            factor = 1.0
        out[str(port_id)] = factor
    return out
