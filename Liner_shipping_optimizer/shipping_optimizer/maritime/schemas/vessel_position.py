"""Canonical vessel-position record schema.

A single canonical AIS-style position report. NOAA MarineCadastre publishes
historical AIS-derived vessel positions in CSV/zstd archives; the NOAA
adapter normalizes those records into this representation, and every
downstream consumer (port-call extraction, dashboards, feature adapter)
reads only this type.

The schema is intentionally strict and frozen; the same validation idiom
as :class:`TrafficDensityRecord` is reused. Invalid input is rejected at
the boundary, never silently dropped inside the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Mapping, Optional

from .traffic_density import (
    _coerce_float,
    _coerce_str,
    _coerce_timestamp,
    _require,
)


# --------------------------------------------------------------------
# Vessel navigation status (AIS ITU-R M.1371)
# --------------------------------------------------------------------


class NavStatus(str, Enum):
    """Canonical AIS navigation-status taxonomy.

    Maps the ITU-R M.1371 navigation-status codes (0-15) into a small
    set of human-readable values. NOAA records typically carry a numeric
    code; the normalization step maps it to one of these.
    """

    UNDERWAY_ENGINE = "underway_engine"
    UNDERWAY_SAILING = "underway_sailing"
    AT_ANCHOR = "at_anchor"
    MOORED = "moored"
    AGROUND = "aground"
    FISHING = "fishing"
    NOT_UNDER_COMMAND = "not_under_command"
    RESTRICTED_MANOEUVRABILITY = "restricted_manoeuvrability"
    CONSTRAINED_DRAUGHT = "constrained_draught"
    TOWING = "towing"
    PILOT_VESSEL = "pilot_vessel"
    OTHER = "other"
    UNKNOWN = "unknown"


_NAV_STATUS_CODE_MAP: Dict[int, NavStatus] = {
    0: NavStatus.UNDERWAY_ENGINE,
    1: NavStatus.AT_ANCHOR,
    2: NavStatus.AT_ANCHOR,
    3: NavStatus.RESTRICTED_MANOEUVRABILITY,
    4: NavStatus.CONSTRAINED_DRAUGHT,
    5: NavStatus.MOORED,
    6: NavStatus.AGROUND,
    7: NavStatus.FISHING,
    8: NavStatus.UNDERWAY_SAILING,
    9: NavStatus.TOWING,
    10: NavStatus.TOWING,
    11: NavStatus.TOWING,
    12: NavStatus.PILOT_VESSEL,
    13: NavStatus.NOT_UNDER_COMMAND,
    14: NavStatus.NOT_UNDER_COMMAND,
    15: NavStatus.OTHER,
}


def canonicalize_nav_status(raw: Any) -> NavStatus:
    """Map any source-provided nav-status label/code to the canonical enum.

    Accepts numeric codes (int/float/str-of-int) or human labels
    (case-insensitive). Returns :class:`NavStatus.UNKNOWN` only when
    the input is None/empty.
    """
    if raw is None:
        return NavStatus.UNKNOWN
    if isinstance(raw, NavStatus):
        return raw
    # Numeric code?
    if isinstance(raw, (int, float)):
        code = int(raw)
        return _NAV_STATUS_CODE_MAP.get(code, NavStatus.UNKNOWN)
    s = str(raw).strip()
    if not s:
        return NavStatus.UNKNOWN
    low = s.lower()
    if low.isdigit():
        return _NAV_STATUS_CODE_MAP.get(int(low), NavStatus.UNKNOWN)
    aliases = {
        "underway_engine": NavStatus.UNDERWAY_ENGINE,
        "underway_sailing": NavStatus.UNDERWAY_SAILING,
        "at_anchor": NavStatus.AT_ANCHOR,
        "anchor": NavStatus.AT_ANCHOR,
        "moored": NavStatus.MOORED,
        "aground": NavStatus.AGROUND,
        "fishing": NavStatus.FISHING,
        "not_under_command": NavStatus.NOT_UNDER_COMMAND,
        "restricted_manoeuvrability": NavStatus.RESTRICTED_MANOEUVRABILITY,
        "constrained_draught": NavStatus.CONSTRAINED_DRAUGHT,
        "towing": NavStatus.TOWING,
        "pilot_vessel": NavStatus.PILOT_VESSEL,
        "other": NavStatus.OTHER,
        "unknown": NavStatus.UNKNOWN,
    }
    return aliases.get(low, NavStatus.UNKNOWN)


# --------------------------------------------------------------------
# MMSI validation helpers
# --------------------------------------------------------------------


def _coerce_mmsi(name: str, value: Any) -> str:
    """Validate an MMSI and return it as a 9-digit string.

    MMSIs are 9 digits. We do not enforce the maritime identification
    digits (MID) prefix here; we just enforce shape.
    """
    s = _coerce_str(name, value)
    digits = "".join(ch for ch in s if ch.isdigit())
    _require(len(digits) == 9, f"{name} must be 9 digits, got {digits!r}")
    return digits


# --------------------------------------------------------------------
# Canonical record
# --------------------------------------------------------------------


@dataclass(frozen=True)
class VesselPosition:
    """A single canonical vessel-position observation (AIS-style).

    All fields are required unless explicitly noted. Coordinates are
    validated against WGS-84. Speed (SOG) is in knots over ground, course
    (COG) and heading are in degrees [0, 360). Timestamps are stored
    as ISO-8601 UTC strings.
    """

    mmsi: str
    timestamp: str  # ISO-8601 UTC, observation time
    latitude: float
    longitude: float
    sog_kn: Optional[float]  # speed over ground (knots)
    cog_deg: Optional[float]  # course over ground (degrees)
    heading_deg: Optional[float]  # true heading (degrees)
    vessel_type: str  # canonical vessel-type label (e.g. "cargo")
    nav_status: NavStatus
    source: str
    dataset: str
    dataset_version: str
    ingested_at: str
    snapshot_id: str
    quality: float
    license: str
    attribution: str
    provenance: Mapping[str, Any]
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require(isinstance(self.mmsi, str) and len(self.mmsi) == 9,
                 "mmsi must be a 9-digit string")
        if not (isinstance(self.latitude, (int, float))
                and -90.0 <= self.latitude <= 90.0):
            raise ValueError(f"latitude out of range: {self.latitude!r}")
        if not (isinstance(self.longitude, (int, float))
                and -180.0 <= self.longitude <= 180.0):
            raise ValueError(f"longitude out of range: {self.longitude!r}")
        for fname in ("sog_kn", "cog_deg", "heading_deg"):
            v = getattr(self, fname)
            if v is not None and not isinstance(v, (int, float)):
                raise ValueError(f"{fname} must be a number or None")
        if self.sog_kn is not None and (self.sog_kn < 0 or self.sog_kn != self.sog_kn):
            raise ValueError(f"sog_kn must be a non-negative finite number: {self.sog_kn!r}")
        for fname in ("cog_deg", "heading_deg"):
            v = getattr(self, fname)
            if v is not None and not (0.0 <= v <= 360.0):
                raise ValueError(f"{fname}={v} out of [0, 360]")
        if not isinstance(self.nav_status, NavStatus):
            raise ValueError("nav_status must be a NavStatus enum")
        for fname in ("timestamp", "ingested_at"):
            v = getattr(self, fname)
            _require(isinstance(v, str) and v.strip() != "", f"{fname} is required")
        for fname in ("source", "dataset", "dataset_version",
                      "snapshot_id", "vessel_type", "license", "attribution"):
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
        d["nav_status"] = self.nav_status.value
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "VesselPosition":
        """Build a vessel-position record from a raw mapping.

        Applies strict validation. Raises ``ValueError`` for invalid input;
        callers must catch and route into rejection counters.
        """
        if not isinstance(d, Mapping):
            raise ValueError(f"record must be a mapping, got {type(d).__name__}")
        mmsi = _coerce_mmsi("mmsi", d.get("mmsi"))
        timestamp = _coerce_timestamp("timestamp", d.get("timestamp"))
        lat = _coerce_float("latitude", d.get("latitude"), min_value=-90.0, max_value=90.0)
        lon = _coerce_float("longitude", d.get("longitude"), min_value=-180.0, max_value=180.0)
        sog = d.get("sog_kn")
        sog_v = None if sog is None else _coerce_float(
            "sog_kn", sog, min_value=0.0, max_value=100.0
        )
        cog = d.get("cog_deg")
        cog_v = None if cog is None else _coerce_float(
            "cog_deg", cog, min_value=0.0, max_value=360.0
        )
        head = d.get("heading_deg")
        head_v = None if head is None else _coerce_float(
            "heading_deg", head, min_value=0.0, max_value=360.0
        )
        vessel_type = _coerce_str("vessel_type", d.get("vessel_type"))
        nav_status = canonicalize_nav_status(d.get("nav_status"))
        source = _coerce_str("source", d.get("source"))
        dataset = _coerce_str("dataset", d.get("dataset"))
        dataset_version = _coerce_str("dataset_version", d.get("dataset_version"))
        ingested_at = _coerce_timestamp("ingested_at", d.get("ingested_at"))
        snapshot_id = _coerce_str("snapshot_id", d.get("snapshot_id"))
        quality = _coerce_float(
            "quality", d.get("quality", 0.0), min_value=0.0, max_value=1.0
        )
        license_str = _coerce_str("license", d.get("license"))
        attribution = _coerce_str("attribution", d.get("attribution"))
        prov = d.get("provenance") or {}
        if not isinstance(prov, Mapping):
            raise ValueError("provenance must be a mapping")
        extra = d.get("extra") or {}
        if not isinstance(extra, Mapping):
            raise ValueError("extra must be a mapping")
        return cls(
            mmsi=mmsi,
            timestamp=timestamp,
            latitude=lat,
            longitude=lon,
            sog_kn=sog_v,
            cog_deg=cog_v,
            heading_deg=head_v,
            vessel_type=vessel_type,
            nav_status=nav_status,
            source=source,
            dataset=dataset,
            dataset_version=dataset_version,
            ingested_at=ingested_at,
            snapshot_id=snapshot_id,
            quality=quality,
            license=license_str,
            attribution=attribution,
            provenance=dict(prov),
            extra=dict(extra),
        )