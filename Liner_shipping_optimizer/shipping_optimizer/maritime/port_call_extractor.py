"""Port-call state machine.

Inputs: a time-ordered list of canonical :class:`VesselPosition` records
(per MMSI) and a list of canonical :class:`Port` geofences.

Output: a list of canonical :class:`PortCall` records, each representing
a confirmed (or rejected) vessel visit to a port.

State machine (per MMSI, per port):

    outside -> enters -> arrival -> dwell -> confirmed -> departure -> closed

The extractor is intentionally streaming and deterministic: it sorts
each MMSI's positions by timestamp, then walks through them while
maintaining a per-port "current candidate". A candidate enters on the
first position inside the geofence, accumulates dwell time, and is
either promoted to ``CONFIRMED`` once the dwell exceeds
``min_dwell_minutes`` (default 30 minutes), or ``REJECTED`` if the
vessel leaves before then. Once confirmed, leaving the geofence
transitions the candidate to ``DEPARTURE`` then ``CLOSED``.

A vessel that is *still inside* at the end of its observation window
produces a port-call with ``departure_ts = None`` and status
``CONFIRMED``. Such "open" port-calls are still useful for the
dashboard (they reflect real activity) but are excluded from
historical aggregates that require closed calls.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .geofencing import is_within_port, ports_containing
from .schemas.port import Port, PortCall, PortCallStatus
from .schemas.vessel_position import NavStatus, VesselPosition


_DEFAULT_MIN_DWELL_MINUTES = 30.0


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _minutes_between(start_iso: str, end_iso: str) -> float:
    s = _parse_iso(start_iso)
    e = _parse_iso(end_iso)
    return max(0.0, (e - s).total_seconds() / 60.0)


def _stable_call_id(
    *, mmsi: str, port_id: str, arrival_ts: str, snapshot_id: str
) -> str:
    h = hashlib.sha1()
    h.update(f"{mmsi}|{port_id}|{arrival_ts}|{snapshot_id}".encode("utf-8"))
    return "pc:" + h.hexdigest()[:16]


@dataclass
class _Candidate:
    port: Port
    mmsi: str
    vessel_type: str
    arrival_ts: str
    nav_status_at_arrival: NavStatus
    last_inside_ts: str
    positions_inside: int = 0


def _bucket_by_mmsi(
    positions: Iterable[VesselPosition]
) -> Dict[str, List[VesselPosition]]:
    out: Dict[str, List[VesselPosition]] = {}
    for p in positions:
        out.setdefault(p.mmsi, []).append(p)
    for v in out.values():
        v.sort(key=lambda r: _parse_iso(r.timestamp).timestamp())
    return out


def extract_port_calls(
    positions: Sequence[VesselPosition],
    ports: Sequence[Port],
    *,
    snapshot_id: str,
    ingested_at: str,
    min_dwell_minutes: float = _DEFAULT_MIN_DWELL_MINUTES,
    dataset_version: str = "0.0.0",
    license: str = "CC0",
    attribution: str = "NOAA MarineCadastre (synthetic fixture)",
) -> List[PortCall]:
    """Detect port-calls from positions + port geofences.

    See module docstring for the state machine. Positions are processed
    per-MMSI in timestamp order. Ports must be a non-empty list; an
    empty port list always yields an empty result (graceful degradation
    rather than crash).
    """
    if not ports:
        return []
    if not positions:
        return []

    port_by_id: Dict[str, Port] = {p.port_id: p for p in ports}
    calls: List[PortCall] = []
    by_mmsi = _bucket_by_mmsi(positions)

    for mmsi, mmsi_positions in by_mmsi.items():
        # Per-MMSI state: candidates keyed by port_id
        candidates: Dict[str, _Candidate] = {}

        for pos in mmsi_positions:
            inside_ports = ports_containing(ports, pos.latitude, pos.longitude)
            inside_ids = {p.port_id for p in inside_ports}
            # 1) Update existing candidates
            for pid, cand in list(candidates.items()):
                if pid in inside_ids:
                    cand.positions_inside += 1
                    cand.last_inside_ts = pos.timestamp
                else:
                    # Vessel left this port's geofence.
                    dwell = _minutes_between(cand.arrival_ts, cand.last_inside_ts)
                    status = (
                        PortCallStatus.CLOSED
                        if dwell >= min_dwell_minutes
                        else PortCallStatus.REJECTED
                    )
                    if status == PortCallStatus.CLOSED:
                        status = PortCallStatus.DEPARTURE
                    quality = _quality_for(dwell, min_dwell_minutes, pos_count=cand.positions_inside)
                    calls.append(_build_call(
                        cand=cand,
                        snapshot_id=snapshot_id,
                        ingested_at=ingested_at,
                        departure_ts=pos.timestamp,
                        dwell_minutes=dwell,
                        status=status,
                        quality=quality,
                        dataset_version=dataset_version,
                        license=license,
                        attribution=attribution,
                    ))
                    del candidates[pid]
            # 2) For ports that newly contain the vessel, start a candidate.
            for p in inside_ports:
                if p.port_id in candidates:
                    continue
                candidates[p.port_id] = _Candidate(
                    port=p,
                    mmsi=mmsi,
                    vessel_type=pos.vessel_type,
                    arrival_ts=pos.timestamp,
                    nav_status_at_arrival=pos.nav_status,
                    last_inside_ts=pos.timestamp,
                    positions_inside=1,
                )

        # End of stream: any candidate remaining is still inside.
        for pid, cand in candidates.items():
            dwell = _minutes_between(cand.arrival_ts, cand.last_inside_ts)
            if dwell >= min_dwell_minutes:
                status = PortCallStatus.CONFIRMED
            else:
                status = PortCallStatus.ARRIVAL  # open, unconfirmed
            quality = _quality_for(dwell, min_dwell_minutes, pos_count=cand.positions_inside)
            calls.append(_build_call(
                cand=cand,
                snapshot_id=snapshot_id,
                ingested_at=ingested_at,
                departure_ts=None,
                dwell_minutes=dwell,
                status=status,
                quality=quality,
                dataset_version=dataset_version,
                license=license,
                attribution=attribution,
            ))

    # Sort by arrival timestamp ascending; deterministic.
    calls.sort(key=lambda c: (c.arrival_ts, c.port_id, c.mmsi))
    return calls


def _quality_for(dwell_minutes: float, min_dwell_minutes: float, *, pos_count: int) -> float:
    """Deterministic quality in [0, 1].

    Approaches 1.0 when dwell >> min_dwell and we have many inside
    positions; approaches 0.5 when the candidate barely meets the
    dwell threshold.
    """
    if min_dwell_minutes <= 0:
        return 1.0
    dwell_ratio = dwell_minutes / (min_dwell_minutes * 4.0)
    dwell_score = max(0.0, min(1.0, dwell_ratio))
    pos_score = max(0.0, min(1.0, pos_count / 10.0))
    raw = 0.6 * dwell_score + 0.4 * pos_score
    return round(0.5 + 0.5 * raw, 4)


def _build_call(
    *,
    cand: _Candidate,
    snapshot_id: str,
    ingested_at: str,
    departure_ts: Optional[str],
    dwell_minutes: float,
    status: PortCallStatus,
    quality: float,
    dataset_version: str,
    license: str,
    attribution: str,
) -> PortCall:
    call_id = _stable_call_id(
        mmsi=cand.mmsi,
        port_id=cand.port.port_id,
        arrival_ts=cand.arrival_ts,
        snapshot_id=snapshot_id,
    )
    return PortCall(
        port_call_id=call_id,
        mmsi=cand.mmsi,
        port_id=cand.port.port_id,
        arrival_ts=cand.arrival_ts,
        departure_ts=departure_ts,
        dwell_minutes=dwell_minutes,
        status=status,
        vessel_type=cand.vessel_type,
        nav_status_at_arrival=cand.nav_status_at_arrival.value,
        source=cand.port.source,
        dataset=cand.port.dataset,
        dataset_version=dataset_version,
        ingested_at=ingested_at,
        snapshot_id=snapshot_id,
        quality=quality,
        license=license,
        attribution=attribution,
        provenance={
            "source": cand.port.source,
            "dataset": cand.port.dataset,
            "license": license,
            "attribution": attribution,
        },
        extra={"port_name": cand.port.name, "country": cand.port.country},
    )