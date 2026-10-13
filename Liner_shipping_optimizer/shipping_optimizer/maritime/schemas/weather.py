"""Phase 5 — Canonical weather observation schema.

A single canonical weather record suitable for maritime routing.
The schema is frozen, validated at construction, and never silently
coerced. Bad input is rejected at the boundary.

The same conventions as :class:`VesselPosition` are used:
* All coordinates are WGS-84.
* All timestamps are ISO-8601 UTC strings.
* Unknown / missing values are explicit ``None`` (never fabricated).
* Provenance, license, source, and quality are mandatory.
* ``commercial_safe`` is a Boolean — providers whose license is
  restricted (e.g. Open-Meteo free tier) must set it to ``False`` so
  downstream consumers and the dashboard can warn the user.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from .traffic_density import _coerce_float, _coerce_str, _coerce_timestamp, _require


# --------------------------------------------------------------------
# Physical-range helpers
# --------------------------------------------------------------------


def _coerce_optional_float(name: str, value: Any,
                           *, min_value: Optional[float] = None,
                           max_value: Optional[float] = None) -> Optional[float]:
    if value is None:
        return None
    return _coerce_float(name, value, min_value=min_value, max_value=max_value)


# --------------------------------------------------------------------
# Canonical record
# --------------------------------------------------------------------


@dataclass(frozen=True)
class WeatherObservation:
    """A single canonical weather observation (or forecast-valid sample).

    The model separates:

    * ``valid_at`` — when the observation describes (UTC). For a
      forecast, this is the future timestamp the forecast is for.
    * ``retrieved_at`` — when the record was materialized locally.
    * ``source`` / ``dataset`` / ``dataset_version`` — provenance.
    * ``license`` / ``attribution`` — licensing chain.
    * ``commercial_safe`` — ``True`` only when the license permits
      commercial use. Restricted licenses (e.g. Open-Meteo free
      tier) must set this to ``False``.
    * ``quality`` — float in [0, 1].
    * ``freshness_state`` — one of ``"available" | "degraded" |
      "stale" | "offline" | "invalid" | "unknown" | "checking"``.
    """

    # Identification
    record_id: str
    source: str
    dataset: str
    dataset_version: str

    # Geography + time
    latitude: float
    longitude: float
    valid_at: str  # ISO-8601 UTC, the time the observation is FOR
    retrieved_at: str  # ISO-8601 UTC, when we materialized the record

    # Atmospheric
    wind_speed_ms: Optional[float] = None  # metres / second
    wind_direction_deg: Optional[float] = None  # 0..360, meteorological
    gust_speed_ms: Optional[float] = None  # metres / second
    temperature_c: Optional[float] = None  # °C
    pressure_hpa: Optional[float] = None  # hPa
    precipitation_mm: Optional[float] = None  # mm in the period
    visibility_m: Optional[float] = None  # metres

    # Marine
    wave_height_m: Optional[float] = None  # metres
    wave_period_s: Optional[float] = None  # seconds
    wave_direction_deg: Optional[float] = None  # 0..360
    sea_state: Optional[str] = None  # WMO sea-state (0..9) as text

    # Provenance + license
    license: str = "unresolved"
    attribution: str = ""
    commercial_safe: bool = False
    quality: float = 0.0  # 0..1
    freshness_state: str = "unknown"
    provenance: Mapping[str, Any] = field(default_factory=dict)
    extra: Mapping[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        _require(isinstance(self.latitude, (int, float))
                 and -90.0 <= self.latitude <= 90.0,
                 f"latitude out of range: {self.latitude!r}")
        _require(isinstance(self.longitude, (int, float))
                 and -180.0 <= self.longitude <= 180.0,
                 f"longitude out of range: {self.longitude!r}")
        for fname in ("valid_at", "retrieved_at"):
            v = getattr(self, fname)
            _require(isinstance(v, str) and v.strip() != "", f"{fname} is required")
        for fname in ("record_id", "source", "dataset", "dataset_version",
                      "license"):
            v = getattr(self, fname)
            _require(isinstance(v, str) and v.strip() != "", f"{fname} is required")
        _require(isinstance(self.quality, (int, float))
                 and 0.0 <= self.quality <= 1.0,
                 f"quality out of [0, 1]: {self.quality!r}")
        # Wind/wave physical sanity
        for fname, mn, mx in (
            ("wind_speed_ms", 0.0, 120.0),
            ("gust_speed_ms", 0.0, 200.0),
            ("wave_height_m", 0.0, 30.0),
            ("wave_period_s", 0.0, 30.0),
        ):
            v = getattr(self, fname)
            if v is not None and not (mn <= v <= mx):
                raise ValueError(f"{fname}={v} out of physical range [{mn}, {mx}]")
        for fname in ("wind_direction_deg", "wave_direction_deg"):
            v = getattr(self, fname)
            if v is not None and not (0.0 <= v <= 360.0):
                raise ValueError(f"{fname}={v} out of [0, 360]")
        # Pressure / temperature / precip / visibility: physically sane
        for fname, mn, mx in (
            ("pressure_hpa", 850.0, 1100.0),
            ("temperature_c", -90.0, 60.0),
            ("precipitation_mm", 0.0, 500.0),
            ("visibility_m", 0.0, 100000.0),
        ):
            v = getattr(self, fname)
            if v is not None and not (mn <= v <= mx):
                raise ValueError(f"{fname}={v} out of physical range [{mn}, {mx}]")
        # Freshness state enum
        _require(self.freshness_state in {
            "available", "degraded", "stale", "offline",
            "invalid", "unknown", "checking",
        }, f"unknown freshness_state: {self.freshness_state!r}")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        if not isinstance(self.extra, Mapping):
            raise ValueError("extra must be a mapping")

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "WeatherObservation":
        """Build a weather observation from a raw mapping.

        Raises ``ValueError`` for invalid input. Callers must catch
        and route into rejection counters.
        """
        if not isinstance(d, Mapping):
            raise ValueError(f"record must be a mapping, got {type(d).__name__}")
        lat = _coerce_float("latitude", d.get("latitude"),
                            min_value=-90.0, max_value=90.0)
        lon = _coerce_float("longitude", d.get("longitude"),
                            min_value=-180.0, max_value=180.0)
        valid_at = _coerce_timestamp("valid_at", d.get("valid_at"))
        retrieved_at = _coerce_timestamp("retrieved_at", d.get("retrieved_at"))
        record_id = _coerce_str("record_id", d.get("record_id"))
        source = _coerce_str("source", d.get("source"))
        dataset = _coerce_str("dataset", d.get("dataset"))
        dataset_version = _coerce_str("dataset_version", d.get("dataset_version"))
        quality = _coerce_float("quality", d.get("quality", 0.0),
                                min_value=0.0, max_value=1.0)
        license_str = _coerce_str("license", d.get("license", "unresolved"))
        attr_raw = d.get("attribution", "")
        attribution = str(attr_raw).strip() if attr_raw is not None else ""
        prov = d.get("provenance") or {}
        if not isinstance(prov, Mapping):
            raise ValueError("provenance must be a mapping")
        extra = d.get("extra") or {}
        if not isinstance(extra, Mapping):
            raise ValueError("extra must be a mapping")
        commercial_safe = bool(d.get("commercial_safe", False))
        freshness_state = str(d.get("freshness_state", "unknown"))
        return cls(
            record_id=record_id,
            source=source,
            dataset=dataset,
            dataset_version=dataset_version,
            latitude=lat,
            longitude=lon,
            valid_at=valid_at,
            retrieved_at=retrieved_at,
            wind_speed_ms=_coerce_optional_float(
                "wind_speed_ms", d.get("wind_speed_ms"),
                min_value=0.0, max_value=120.0,
            ),
            wind_direction_deg=_coerce_optional_float(
                "wind_direction_deg", d.get("wind_direction_deg"),
                min_value=0.0, max_value=360.0,
            ),
            gust_speed_ms=_coerce_optional_float(
                "gust_speed_ms", d.get("gust_speed_ms"),
                min_value=0.0, max_value=200.0,
            ),
            temperature_c=_coerce_optional_float(
                "temperature_c", d.get("temperature_c"),
                min_value=-90.0, max_value=60.0,
            ),
            pressure_hpa=_coerce_optional_float(
                "pressure_hpa", d.get("pressure_hpa"),
                min_value=850.0, max_value=1100.0,
            ),
            precipitation_mm=_coerce_optional_float(
                "precipitation_mm", d.get("precipitation_mm"),
                min_value=0.0, max_value=500.0,
            ),
            visibility_m=_coerce_optional_float(
                "visibility_m", d.get("visibility_m"),
                min_value=0.0, max_value=100000.0,
            ),
            wave_height_m=_coerce_optional_float(
                "wave_height_m", d.get("wave_height_m"),
                min_value=0.0, max_value=30.0,
            ),
            wave_period_s=_coerce_optional_float(
                "wave_period_s", d.get("wave_period_s"),
                min_value=0.0, max_value=30.0,
            ),
            wave_direction_deg=_coerce_optional_float(
                "wave_direction_deg", d.get("wave_direction_deg"),
                min_value=0.0, max_value=360.0,
            ),
            sea_state=d.get("sea_state"),
            license=license_str,
            attribution=attribution,
            commercial_safe=commercial_safe,
            quality=quality,
            freshness_state=freshness_state,
            provenance=dict(prov),
            extra=dict(extra),
        )
