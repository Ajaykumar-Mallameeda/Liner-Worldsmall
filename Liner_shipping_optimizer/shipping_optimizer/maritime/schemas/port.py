"""Canonical port schema.

A port is a deterministic geofenced location where vessel-port-calls are
detected. The port model intentionally carries only what the
port-call extractor needs (an id, a name, a center coordinate, and a
radius). Optional fields (country, region, type) are kept as
unconstrained strings so the schema does not impose a taxonomy we do
not have a verified source for.

Ports are read-only canonical objects. The list of ports is curated
locally (no network at read-time); Phase 2 ships a small fixture under
``data/maritime/synthetic/ports_sample.json``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, Mapping, Optional

from .traffic_density import _coerce_float, _coerce_str, _require


# --------------------------------------------------------------------
# Port type
# --------------------------------------------------------------------


class PortType(str, Enum):
    """Coarse port-type taxonomy.

    Intentionally minimal: cargo, tanker, fishing, passenger, mixed, unknown.
    The schema does not pretend to have authoritative port metadata; this
    is used only for UI/sorting.
    """

    CARGO = "cargo"
    TANKER = "tanker"
    FISHING = "fishing"
    PASSENGER = "passenger"
    MIXED = "mixed"
    OTHER = "other"
    UNKNOWN = "unknown"


_PORT_TYPE_ALIASES: Dict[str, PortType] = {
    "cargo": PortType.CARGO,
    "container": PortType.CARGO,
    "tanker": PortType.TANKER,
    "oil": PortType.TANKER,
    "lng": PortType.TANKER,
    "fishing": PortType.FISHING,
    "passenger": PortType.PASSENGER,
    "cruise": PortType.PASSENGER,
    "ferry": PortType.PASSENGER,
    "mixed": PortType.MIXED,
    "other": PortType.OTHER,
    "unknown": PortType.UNKNOWN,
}


def canonicalize_port_type(raw: Any) -> PortType:
    """Map any source-provided port-type label to the canonical enum."""
    if raw is None:
        return PortType.UNKNOWN
    if isinstance(raw, PortType):
        return raw
    s = str(raw).strip().lower()
    if not s:
        return PortType.UNKNOWN
    return _PORT_TYPE_ALIASES.get(s, PortType.OTHER)


# --------------------------------------------------------------------
# Canonical port
# --------------------------------------------------------------------


@dataclass(frozen=True)
class Port:
    """A canonical port record.

    The geofence is a circular region defined by ``latitude``,
    ``longitude`` (WGS-84) and ``radius_nm`` (nautical miles). Port-call
    detection treats any position within this radius as inside the port.
    """

    port_id: str
    name: str
    country: str
    region: str
    latitude: float
    longitude: float
    radius_nm: float
    port_type: PortType
    source: str
    dataset: str
    dataset_version: str
    license: str
    attribution: str
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require(isinstance(self.port_id, str) and self.port_id.strip() != "",
                 "port_id is required")
        for fname in ("name", "country", "region", "source", "dataset",
                      "dataset_version", "license", "attribution"):
            v = getattr(self, fname)
            _require(isinstance(v, str), f"{fname} must be a string")
        if not (isinstance(self.latitude, (int, float))
                and -90.0 <= self.latitude <= 90.0):
            raise ValueError(f"latitude out of range: {self.latitude!r}")
        if not (isinstance(self.longitude, (int, float))
                and -180.0 <= self.longitude <= 180.0):
            raise ValueError(f"longitude out of range: {self.longitude!r}")
        if not (isinstance(self.radius_nm, (int, float))
                and self.radius_nm > 0):
            raise ValueError(f"radius_nm must be positive: {self.radius_nm!r}")
        if not isinstance(self.port_type, PortType):
            raise ValueError("port_type must be a PortType enum")
        if not isinstance(self.extra, Mapping):
            raise ValueError("extra must be a mapping")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["port_type"] = self.port_type.value
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Port":
        """Build a port from a raw mapping. Raises on invalid input."""
        if not isinstance(d, Mapping):
            raise ValueError(f"port must be a mapping, got {type(d).__name__}")
        port_id = _coerce_str("port_id", d.get("port_id"))
        name = _coerce_str("name", d.get("name"))
        country = d.get("country") or ""
        region = d.get("region") or ""
        lat = _coerce_float("latitude", d.get("latitude"), min_value=-90.0, max_value=90.0)
        lon = _coerce_float("longitude", d.get("longitude"), min_value=-180.0, max_value=180.0)
        radius = _coerce_float("radius_nm", d.get("radius_nm"), min_value=0.01, max_value=200.0)
        port_type = canonicalize_port_type(d.get("port_type"))
        source = _coerce_str("source", d.get("source"))
        dataset = _coerce_str("dataset", d.get("dataset"))
        dataset_version = _coerce_str("dataset_version", d.get("dataset_version"))
        license_str = _coerce_str("license", d.get("license"))
        attribution = _coerce_str("attribution", d.get("attribution"))
        extra = d.get("extra") or {}
        if not isinstance(extra, Mapping):
            raise ValueError("extra must be a mapping")
        return cls(
            port_id=port_id,
            name=name,
            country=str(country),
            region=str(region),
            latitude=lat,
            longitude=lon,
            radius_nm=radius,
            port_type=port_type,
            source=source,
            dataset=dataset,
            dataset_version=dataset_version,
            license=license_str,
            attribution=attribution,
            extra=dict(extra),
        )


# --------------------------------------------------------------------
# Port-call record (state machine output)
# --------------------------------------------------------------------


class PortCallStatus(str, Enum):
    """Lifecycle states of a detected port-call.

    The state machine progresses:

        outside -> enters -> arrival -> dwell -> confirmed -> departure -> closed

    A "closed" port-call has been observed ending (vessel left the
    geofence). An "open" port-call is still active (vessel last seen
    inside the geofence). "rejected" means the dwell was below the
    confirmation threshold and the candidate was discarded.
    """

    ENTERS = "enters"
    ARRIVAL = "arrival"
    DWELL = "dwell"
    CONFIRMED = "confirmed"
    DEPARTURE = "departure"
    CLOSED = "closed"
    REJECTED = "rejected"


@dataclass(frozen=True)
class PortCall:
    """A detected port-call: vessel visited a port for a measurable dwell.

    The record carries all information needed to reason about port
    activity without re-running the state machine: arrival + departure
    timestamps, dwell in minutes, vessel type, and quality score.
    """

    port_call_id: str
    mmsi: str
    port_id: str
    arrival_ts: str
    departure_ts: Optional[str]  # None while still inside
    dwell_minutes: float  # 0 while still inside
    status: PortCallStatus
    vessel_type: str
    nav_status_at_arrival: str
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
        for fname in ("port_call_id", "mmsi", "port_id", "arrival_ts",
                      "vessel_type", "nav_status_at_arrival",
                      "source", "dataset", "dataset_version",
                      "ingested_at", "snapshot_id", "license", "attribution"):
            v = getattr(self, fname)
            _require(isinstance(v, str) and v.strip() != "", f"{fname} is required")
        if self.departure_ts is not None and not isinstance(self.departure_ts, str):
            raise ValueError("departure_ts must be a string or None")
        if not (isinstance(self.dwell_minutes, (int, float))
                and self.dwell_minutes >= 0):
            raise ValueError(f"dwell_minutes must be non-negative: {self.dwell_minutes!r}")
        if not isinstance(self.status, PortCallStatus):
            raise ValueError("status must be a PortCallStatus enum")
        if not (isinstance(self.quality, (int, float)) and 0.0 <= self.quality <= 1.0):
            raise ValueError(f"quality must be in [0, 1]: {self.quality!r}")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        if not isinstance(self.extra, Mapping):
            raise ValueError("extra must be a mapping")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "PortCall":
        """Build a port-call from a raw mapping. Raises on invalid input."""
        if not isinstance(d, Mapping):
            raise ValueError(f"port_call must be a mapping, got {type(d).__name__}")
        from .vessel_position import _coerce_timestamp  # local import to avoid cycle
        from .traffic_density import _coerce_float
        required_str = ("port_call_id", "mmsi", "port_id", "arrival_ts",
                        "vessel_type", "nav_status_at_arrival",
                        "source", "dataset", "dataset_version",
                        "snapshot_id", "license", "attribution")
        out_d: Dict[str, Any] = {}
        for k in required_str:
            out_d[k] = _coerce_str(k, d.get(k))
        out_d["ingested_at"] = _coerce_timestamp("ingested_at", d.get("ingested_at"))
        out_d["departure_ts"] = (
            None if d.get("departure_ts") is None
            else _coerce_timestamp("departure_ts", d.get("departure_ts"))
        )
        out_d["dwell_minutes"] = _coerce_float(
            "dwell_minutes", d.get("dwell_minutes", 0.0),
            min_value=0.0, max_value=1e9,
        )
        out_d["quality"] = _coerce_float(
            "quality", d.get("quality", 0.0),
            min_value=0.0, max_value=1.0,
        )
        out_d["status"] = PortCallStatus(str(d.get("status", "arrival")))
        prov = d.get("provenance") or {}
        if not isinstance(prov, Mapping):
            raise ValueError("provenance must be a mapping")
        extra = d.get("extra") or {}
        if not isinstance(extra, Mapping):
            raise ValueError("extra must be a mapping")
        out_d["provenance"] = dict(prov)
        out_d["extra"] = dict(extra)
        return cls(**out_d)