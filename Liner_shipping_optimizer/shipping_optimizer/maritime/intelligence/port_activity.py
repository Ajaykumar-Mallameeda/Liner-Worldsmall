"""Port intelligence feature derivation.

Phase 2 derives three classes of feature from a list of confirmed
:class:`PortCall` records:

* ``port_activity`` — per-port call count + dwell-time stats.
* ``port_vessel_type_mix`` — distribution of vessel_type per port.
* ``port_call_timeline`` — chronological sequence of port-calls for the
  snapshot (per-port).

All derivations are deterministic given the input list; no network,
no I/O, no time of evaluation dependency.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Mapping, Sequence, Tuple

from ..schemas.port import Port, PortCall, PortCallStatus


# Stable ordering of feature types so the dashboard and tests see the
# same order across runs.
PORT_FEATURE_TYPES = (
    "port_activity",
    "port_vessel_type_mix",
    "port_call_timeline",
)


@dataclass(frozen=True)
class PortActivityFeature:
    """Per-port activity summary derived from a list of port-calls."""

    feature_id: str
    port_id: str
    port_name: str
    feature_type: str  # "port_activity"
    call_count: int
    confirmed_count: int
    open_count: int
    rejected_count: int
    avg_dwell_minutes: float
    median_dwell_minutes: float
    unique_vessels: int
    observed_start: str
    observed_end: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PortVesselTypeMixFeature:
    """Distribution of vessel_type at a port."""

    feature_id: str
    port_id: str
    port_name: str
    feature_type: str  # "port_vessel_type_mix"
    counts_by_type: Mapping[str, int]
    dominant_type: str
    sample_size: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PortCallTimelineFeature:
    """A single point on the per-port port-call timeline.

    Each entry corresponds to one confirmed (or in-progress) port-call.
    Open calls have ``departure_ts=None`` and ``status="confirmed"``.
    """

    feature_id: str
    port_id: str
    port_name: str
    feature_type: str  # "port_call_timeline"
    port_call_id: str
    mmsi: str
    vessel_type: str
    arrival_ts: str
    departure_ts: str  # "" when still inside
    dwell_minutes: float
    status: str  # string form of PortCallStatus
    quality: float

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


# --------------------------------------------------------------------
# Derivation
# --------------------------------------------------------------------


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if q <= 0:
        return sorted_values[0]
    if q >= 1:
        return sorted_values[-1]
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac


def compute_port_activity(
    port_calls: Sequence[PortCall],
    ports_by_id: Mapping[str, Port],
    *,
    feature_id_prefix: str = "port",
) -> List[PortActivityFeature]:
    """Compute per-port activity features from port-calls.

    Closed calls (DEPARTURE) are included; rejected calls are excluded
    from average dwell; open calls (CONFIRMED with no departure_ts)
    contribute their observed dwell to the average but count separately
    in ``open_count``.
    """
    if not port_calls:
        return []

    by_port: Dict[str, List[PortCall]] = defaultdict(list)
    for c in port_calls:
        by_port[c.port_id].append(c)

    out: List[PortActivityFeature] = []
    for port_id, calls in by_port.items():
        port = ports_by_id.get(port_id)
        port_name = port.name if port is not None else port_id
        dwells = sorted(c.dwell_minutes for c in calls if c.dwell_minutes >= 0)
        avg_dwell = (sum(dwells) / len(dwells)) if dwells else 0.0
        med_dwell = _percentile(dwells, 0.5)
        confirmed = sum(1 for c in calls if c.status in (
            PortCallStatus.CONFIRMED, PortCallStatus.DEPARTURE, PortCallStatus.CLOSED,
        ))
        open_count = sum(1 for c in calls if c.departure_ts is None
                         and c.status == PortCallStatus.CONFIRMED)
        rejected = sum(1 for c in calls if c.status == PortCallStatus.REJECTED)
        unique_vessels = len({c.mmsi for c in calls})
        arrivals = sorted(c.arrival_ts for c in calls)
        obs_start = arrivals[0]
        obs_end = arrivals[-1]
        out.append(PortActivityFeature(
            feature_id=f"{feature_id_prefix}:port_activity:{port_id}",
            port_id=port_id,
            port_name=port_name,
            feature_type="port_activity",
            call_count=len(calls),
            confirmed_count=confirmed,
            open_count=open_count,
            rejected_count=rejected,
            avg_dwell_minutes=round(avg_dwell, 2),
            median_dwell_minutes=round(med_dwell, 2),
            unique_vessels=unique_vessels,
            observed_start=obs_start,
            observed_end=obs_end,
        ))
    out.sort(key=lambda f: (f.port_id,))
    return out


def compute_port_vessel_type_mix(
    port_calls: Sequence[PortCall],
    ports_by_id: Mapping[str, Port],
    *,
    feature_id_prefix: str = "port",
) -> List[PortVesselTypeMixFeature]:
    """Compute vessel-type distribution per port.

    Rejected calls are excluded from the count; the dominant type is
    the highest-count bucket, ties broken alphabetically (deterministic).
    """
    if not port_calls:
        return []

    by_port: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in port_calls:
        if c.status == PortCallStatus.REJECTED:
            continue
        by_port[c.port_id][c.vessel_type] += 1

    out: List[PortVesselTypeMixFeature] = []
    for port_id, counts in by_port.items():
        port = ports_by_id.get(port_id)
        port_name = port.name if port is not None else port_id
        sample = sum(counts.values())
        # Deterministic dominant: max count, ties broken by type name.
        dom_type = max(
            sorted(counts.items()),
            key=lambda kv: (kv[1], kv[0]),
        )[0]
        out.append(PortVesselTypeMixFeature(
            feature_id=f"{feature_id_prefix}:vessel_mix:{port_id}",
            port_id=port_id,
            port_name=port_name,
            feature_type="port_vessel_type_mix",
            counts_by_type=dict(counts),
            dominant_type=dom_type,
            sample_size=sample,
        ))
    out.sort(key=lambda f: (f.port_id,))
    return out


def compute_port_call_timeline(
    port_calls: Sequence[PortCall],
    ports_by_id: Mapping[str, Port],
    *,
    feature_id_prefix: str = "port",
) -> List[PortCallTimelineFeature]:
    """Compute a chronological timeline of port-calls."""
    if not port_calls:
        return []
    sorted_calls = sorted(port_calls, key=lambda c: (c.arrival_ts, c.port_id, c.mmsi))
    out: List[PortCallTimelineFeature] = []
    for c in sorted_calls:
        if c.status == PortCallStatus.REJECTED:
            continue
        port = ports_by_id.get(c.port_id)
        port_name = port.name if port is not None else c.port_id
        out.append(PortCallTimelineFeature(
            feature_id=f"{feature_id_prefix}:timeline:{c.port_call_id}",
            port_id=c.port_id,
            port_name=port_name,
            feature_type="port_call_timeline",
            port_call_id=c.port_call_id,
            mmsi=c.mmsi,
            vessel_type=c.vessel_type,
            arrival_ts=c.arrival_ts,
            departure_ts=c.departure_ts or "",
            dwell_minutes=c.dwell_minutes,
            status=c.status.value,
            quality=c.quality,
        ))
    return out