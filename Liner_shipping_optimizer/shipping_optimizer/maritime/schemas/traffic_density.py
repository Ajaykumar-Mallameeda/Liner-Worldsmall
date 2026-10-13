"""Canonical traffic-density record schema.

The single immutable record type for a single EMODnet-style vessel-density
observation. Future sources (NOAA, PortWatch, etc.) normalize into this
representation; the rest of the system consumes only this type.

Validation rules are strict and raise :class:`ValueError` for invalid input.
The contract is: invalid input is rejected at the boundary, never silently
dropped inside the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Mapping, Optional


# --------------------------------------------------------------------
# Validators
# --------------------------------------------------------------------


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _coerce_str(name: str, value: Any) -> str:
    _require(value is not None, f"{name} is required")
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    _require(value != "", f"{name} must be non-empty")
    return value


def _coerce_float(name: str, value: Any, *, min_value: float, max_value: float) -> float:
    _require(value is not None, f"{name} is required")
    try:
        f = float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{name} must be numeric, got {value!r}") from e
    if f != f:  # NaN
        raise ValueError(f"{name} must not be NaN")
    _require(f >= min_value and f <= max_value, f"{name}={f} out of range [{min_value}, {max_value}]")
    return f


def _coerce_timestamp(name: str, value: Any) -> str:
    """Accepts an ISO-8601 string, datetime, or epoch seconds; returns ISO-8601 UTC."""
    _require(value is not None, f"{name} is required")
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    if isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        return dt.isoformat()
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"{name}={value!r} is not a valid ISO-8601 timestamp") from e
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    raise ValueError(f"{name} must be ISO-8601 string, datetime, or epoch number")


# --------------------------------------------------------------------
# Vessel classification
# --------------------------------------------------------------------


class VesselClass(str, Enum):
    """Canonical vessel-class taxonomy.

    EMODnet publishes vessel density by ship type using a multi-digit code;
    we map the most common codes into a small canonical set so downstream
    consumers do not need to know the source taxonomy.
    """

    UNKNOWN = "unknown"
    CARGO = "cargo"
    TANKER = "tanker"
    PASSENGER = "passenger"
    FISHING = "fishing"
    PLEASURE = "pleasure"
    OTHER = "other"


# Mapping from EMODnet ship-type codes (commonly used in EMODnet density
# products) to the canonical taxonomy.  Unknown codes are mapped to OTHER.
_EMODNET_VESSEL_CODE_MAP: Dict[str, VesselClass] = {
    # Cargo family (70-79, 80-89)
    "70": VesselClass.CARGO, "71": VesselClass.CARGO, "72": VesselClass.CARGO,
    "73": VesselClass.CARGO, "74": VesselClass.CARGO, "75": VesselClass.CARGO,
    "76": VesselClass.CARGO, "77": VesselClass.CARGO, "78": VesselClass.CARGO,
    "79": VesselClass.CARGO, "80": VesselClass.CARGO, "81": VesselClass.CARGO,
    "82": VesselClass.CARGO, "83": VesselClass.CARGO, "84": VesselClass.CARGO,
    "85": VesselClass.CARGO, "86": VesselClass.CARGO, "87": VesselClass.CARGO,
    "88": VesselClass.CARGO, "89": VesselClass.CARGO,
    # Tanker family (80-89 in some taxonomies; 90-99 elsewhere)
    "90": VesselClass.TANKER, "91": VesselClass.TANKER, "92": VesselClass.TANKER,
    "93": VesselClass.TANKER, "94": VesselClass.TANKER, "95": VesselClass.TANKER,
    "96": VesselClass.TANKER, "97": VesselClass.TANKER, "98": VesselClass.TANKER,
    "99": VesselClass.TANKER,
    # Passenger
    "60": VesselClass.PASSENGER, "61": VesselClass.PASSENGER, "62": VesselClass.PASSENGER,
    "63": VesselClass.PASSENGER, "64": VesselClass.PASSENGER, "65": VesselClass.PASSENGER,
    "66": VesselClass.PASSENGER, "67": VesselClass.PASSENGER, "68": VesselClass.PASSENGER,
    "69": VesselClass.PASSENGER,
    # Fishing
    "30": VesselClass.FISHING, "31": VesselClass.FISHING, "32": VesselClass.FISHING,
    "33": VesselClass.FISHING, "34": VesselClass.FISHING, "35": VesselClass.FISHING,
    "36": VesselClass.FISHING, "37": VesselClass.FISHING, "38": VesselClass.FISHING,
    "39": VesselClass.FISHING,
    # Pleasure
    "40": VesselClass.PLEASURE, "41": VesselClass.PLEASURE, "42": VesselClass.PLEASURE,
    "43": VesselClass.PLEASURE, "44": VesselClass.PLEASURE, "45": VesselClass.PLEASURE,
    "46": VesselClass.PLEASURE, "47": VesselClass.PLEASURE, "48": VesselClass.PLEASURE,
    "49": VesselClass.PLEASURE,
}


def canonicalize_vessel_class(raw: Any) -> VesselClass:
    """Map any source-provided vessel class label to the canonical taxonomy.

    Accepts strings (case-insensitive), integers, or floats. Returns
    :class:`VesselClass.UNKNOWN` only for None/empty; otherwise maps to the
    closest canonical bucket.
    """
    if raw is None:
        return VesselClass.UNKNOWN
    s = str(raw).strip()
    if not s:
        return VesselClass.UNKNOWN
    low = s.lower()
    # Direct alias match
    direct = {
        "cargo": VesselClass.CARGO, "tanker": VesselClass.TANKER,
        "passenger": VesselClass.PASSENGER, "fishing": VesselClass.FISHING,
        "pleasure": VesselClass.PLEASURE, "other": VesselClass.OTHER,
        "unknown": VesselClass.UNKNOWN, "all": VesselClass.OTHER,
    }
    if low in direct:
        return direct[low]
    # Try EMODnet numeric code (e.g. "70" or 70.0)
    try:
        key = str(int(float(low)))
    except (ValueError, TypeError):
        return VesselClass.OTHER
    return _EMODNET_VESSEL_CODE_MAP.get(key, VesselClass.OTHER)


# --------------------------------------------------------------------
# Canonical record
# --------------------------------------------------------------------


@dataclass(frozen=True)
class TrafficDensityRecord:
    """A single EMODnet-style traffic-density observation.

    All fields are required unless explicitly noted. Coordinates are validated
    against the WGS-84 range. Intensities must be non-negative finite floats.
    Timestamps are stored as ISO-8601 UTC strings.
    """

    spatial_id: str
    latitude: float
    longitude: float
    vessel_class: VesselClass
    intensity: float
    observation_start: str
    observation_end: str
    source: str
    dataset: str
    dataset_version: str
    observed_at: str
    ingested_at: str
    snapshot_id: str
    quality: float
    provenance: Mapping[str, Any]
    license: str
    attribution: str
    # Optional enrichment — the cell is identified by a stable id (e.g. EMODnet
    # cell hash). Latitude/longitude may be the cell centroid.
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Re-validate in __post_init__ because frozen dataclass __init__ runs before.
        # We must use object.__setattr__ to mutate; but we only need to raise.
        # Re-check fields explicitly (coercion already happened in from_dict, but
        # if the user constructed directly we still validate).
        _require(isinstance(self.spatial_id, str) and self.spatial_id.strip() != "",
                 "spatial_id is required")
        if not (isinstance(self.latitude, (int, float)) and -90.0 <= self.latitude <= 90.0):
            raise ValueError(f"latitude out of range: {self.latitude!r}")
        if not (isinstance(self.longitude, (int, float)) and -180.0 <= self.longitude <= 180.0):
            raise ValueError(f"longitude out of range: {self.longitude!r}")
        if not (isinstance(self.intensity, (int, float)) and self.intensity >= 0
                and self.intensity == self.intensity):  # not NaN
            raise ValueError(f"intensity must be a non-negative finite number: {self.intensity!r}")
        if not isinstance(self.vessel_class, VesselClass):
            raise ValueError(f"vessel_class must be a VesselClass, got {type(self.vessel_class).__name__}")
        # string fields
        for fname in ("source", "dataset", "dataset_version", "observed_at",
                      "ingested_at", "snapshot_id", "observation_start",
                      "observation_end", "license", "attribution"):
            v = getattr(self, fname)
            _require(isinstance(v, str) and v.strip() != "", f"{fname} is required")
        if not (isinstance(self.quality, (int, float)) and 0.0 <= self.quality <= 1.0):
            raise ValueError(f"quality must be in [0, 1]: {self.quality!r}")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        if not isinstance(self.extra, Mapping):
            raise ValueError("extra must be a mapping")

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # VesselClass -> value string
        d["vessel_class"] = self.vessel_class.value
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "TrafficDensityRecord":
        """Construct a record from a raw dict (e.g. one JSONL line).

        Applies strict validation and normalization. Raises ``ValueError`` for
        invalid input; callers must catch and route into rejection counters.
        """
        if not isinstance(d, Mapping):
            raise ValueError(f"record must be a mapping, got {type(d).__name__}")
        # Required fields
        spatial_id = _coerce_str("spatial_id", d.get("spatial_id"))
        lat = _coerce_float("latitude", d.get("latitude"), min_value=-90.0, max_value=90.0)
        lon = _coerce_float("longitude", d.get("longitude"), min_value=-180.0, max_value=180.0)
        vc = canonicalize_vessel_class(d.get("vessel_class"))
        intensity = _coerce_float("intensity", d.get("intensity"), min_value=0.0, max_value=1e9)
        # Timestamps
        obs_start = _coerce_timestamp("observation_start", d.get("observation_start"))
        obs_end = _coerce_timestamp("observation_end", d.get("observation_end"))
        observed_at = _coerce_timestamp("observed_at", d.get("observed_at"))
        ingested_at = _coerce_timestamp("ingested_at", d.get("ingested_at"))
        # Metadata strings
        source = _coerce_str("source", d.get("source"))
        dataset = _coerce_str("dataset", d.get("dataset"))
        dataset_version = _coerce_str("dataset_version", d.get("dataset_version"))
        snapshot_id = _coerce_str("snapshot_id", d.get("snapshot_id"))
        license_str = _coerce_str("license", d.get("license"))
        attribution = _coerce_str("attribution", d.get("attribution"))
        # Quality
        quality = _coerce_float("quality", d.get("quality", 0.0), min_value=0.0, max_value=1.0)
        # Provenance: must be mapping; allow missing
        prov = d.get("provenance") or {}
        if not isinstance(prov, Mapping):
            raise ValueError("provenance must be a mapping")
        extra = d.get("extra") or {}
        if not isinstance(extra, Mapping):
            raise ValueError("extra must be a mapping")
        return cls(
            spatial_id=spatial_id,
            latitude=lat,
            longitude=lon,
            vessel_class=vc,
            intensity=intensity,
            observation_start=obs_start,
            observation_end=obs_end,
            source=source,
            dataset=dataset,
            dataset_version=dataset_version,
            observed_at=observed_at,
            ingested_at=ingested_at,
            snapshot_id=snapshot_id,
            quality=quality,
            provenance=dict(prov),
            license=license_str,
            attribution=attribution,
            extra=dict(extra),
        )
