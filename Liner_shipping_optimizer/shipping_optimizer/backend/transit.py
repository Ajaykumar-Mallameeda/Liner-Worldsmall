"""
Point-to-point transit finder (2026-10-28, feature #22): how the plan on screen carries a box from port A to port B.

POST /api/transit {run, origin, destination, max_transfers?}

Itineraries come from the engine's own path enumeration (src/network/paths.build_paths) over the run's operated
services: the same rules the flow LP uses (forward ride on a closed rotation, transit = sailing + port stays at
intermediate calls + the fixed transfer dwell, at most two transfers). Any port pair may be asked, not only pairs with
recorded demand. When the pair has demand, its time limit is checked and the flow LP's routed TEU per itinerary is
shown (backend/whatif._evaluate, the same evaluation as the What-if baseline).

Departures per week of an itinerary = the lowest frequency of its services. Waiting for the next departure is NOT
in the engine's transit time; the worst case (7 / frequency days at each boarding after the first) is reported beside it.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import whatif

router = APIRouter()

MAX_ITINERARIES = 40


class TransitRequest(BaseModel):
    run: Dict = Field(default_factory=lambda: {"kind": "current"})
    origin: str
    destination: str
    max_transfers: Optional[int] = Field(None, ge=0, le=2)


def _segment(models, freq, seg) -> Dict:
    m = models[seg.service]
    calls = [m.ports[i] for i in seg.legs] + [seg.to_port]
    return {"service": m.service_id, "vessel_class": m.vessel_class, "from": seg.from_port, "to": seg.to_port,
            "ride_days": round(seg.ride_days, 2), "calls": calls, "departures_per_week": freq.get(seg.service, 0)}


@router.post("/api/transit")
def transit(req: TransitRequest):
    from src.network.paths import BUDGET_FIXED, SELECT_FASTEST, PathConfig, build_paths

    o, t = req.origin.strip().upper(), req.destination.strip().upper()
    if o == t:
        raise HTTPException(status_code=422, detail="origin and destination are the same port")
    t0 = time.perf_counter()
    with whatif._lock:
        key, out = whatif._run_output(req.run)
        prep = whatif._prepare(key, out, whatif._dataset_of(req.run, out))
        lookup = prep["planner"].port_lookup
        unknown = [p for p in (o, t) if p not in lookup]
        if unknown:
            raise HTTPException(status_code=422, detail=f"unknown port(s) {unknown} in dataset {prep['dataset']}")
        models, freq, a = prep["models"], prep["freq"], prep["assumptions"]
        max_tr = prep["max_transfers"] if req.max_transfers is None else min(req.max_transfers, 2)
        cfg = PathConfig(selection=SELECT_FASTEST, budget=BUDGET_FIXED, max_transfers=max_tr,
                         multi_hop_min_alternatives=10 ** 9 if max_tr >= 2 else 1)
        # one synthetic OD, no time limit: every itinerary the rules allow (the limit is checked below)
        od = SimpleNamespace(origin=o, destination=t, weekly_teu=1.0, revenue_per_teu=0.0, max_transit_days=None)
        found: List = []
        if freq:
            paths, _stats = build_paths([od], models, lookup, a, max_paths_per_od=10 ** 9, config=cfg,
                                        only_services=sorted(freq))
            found = paths.get(0, [])
        di = next((i for i, d in enumerate(prep["problem"].demands) if d.origin == o and d.destination == t), None)
        demand = prep["problem"].demands[di] if di is not None else None
        routed: Dict = {}
        if demand is not None and demand.weekly_teu > 0:
            ev = whatif._evaluate(prep, 1.0, 1.0, od_flows_for=di)
            for p, v in ev["od_flows"]:
                k = (tuple(models[s.service].service_id for s in p.segments), p.transfer_ports)
                routed[k] = routed.get(k, 0.0) + v
    limit = getattr(demand, "max_transit_days", None) if demand is not None else None
    rows = []
    for p in sorted(found, key=lambda p: (p.transit_days, p.n_transfers, p.port_cost_per_teu)):
        segs = [_segment(models, freq, s) for s in p.segments]
        k = (tuple(s["service"] for s in segs), p.transfer_ports)
        rows.append({
            "kind": p.kind, "transfers": p.n_transfers, "hubs": list(p.transfer_ports),
            "transit_days": round(p.transit_days, 2),
            "departures_per_week": min(s["departures_per_week"] for s in segs),
            "max_wait_days": round(sum(7.0 / s["departures_per_week"] for s in segs[1:] if s["departures_per_week"]), 2),
            "port_cost_per_teu": round(p.port_cost_per_teu, 2),
            "within_limit": None if limit is None else bool(p.transit_days <= limit + 1e-9),
            "plan_teu": round(routed.get(k, 0.0), 1),
            "segments": segs,
        })
    return {
        "run": req.run, "dataset": prep["dataset"], "origin": o, "destination": t,
        "max_transfers": max_tr, "transfer_dwell_days": a.transfer_dwell_days,
        "demand": None if demand is None else {
            "weekly_teu": demand.weekly_teu, "revenue_per_teu": demand.revenue_per_teu,
            "max_transit_days": limit, "routed_teu": round(sum(routed.values()), 1)},
        "itineraries_found": len(rows), "itineraries": rows[:MAX_ITINERARIES],
        "runtime_sec": round(time.perf_counter() - t0, 2),
        "method": "src/network/paths.build_paths over the run's operated services (forward ride on each rotation; "
                  "transit = sailing + intermediate port stays + transfer dwell); routed TEU from the flow LP of "
                  "the What-if baseline",
    }
