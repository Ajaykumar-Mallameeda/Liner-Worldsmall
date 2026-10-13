"""Independent accounting ledger and network validator.

Given only (a) which services operate at which weekly frequency and (b) how many
TEU of each OD were carried on which sequence of service segments, this module
recomputes - from the raw distance matrix, fleet records and port records, WITHOUT
using the service model or the MILP that produced the plan - the full economics and
checks every constraint. It is the authority that decides whether a result may be
reported as verified.

Accounting identity (USD per week)

    operating_profit = cargo_revenue
                     - vessel_cost            N_s * TC_daily * 7
                     - fuel_cost              f_s * (sea_days*bunker_t + port_days*idle_t) * price_s
                           (price_s = applicable price of service s: the uniform price
                            or the per-service price passed in ``fuel_prices``; the
                            tonnes are always recomputed here)
                     - port_call_fixed_cost   f_s * sum(PortCallCostFixed over calls)
                     - handling_cost          origin load + destination unload, per TEU
                     - transshipment_cost     per TEU at the hub
                     - port_variable_cost     per TEU per load/unload event
    cargo_revenue    = sum_allocations teu * revenue_per_teu(od)        (once per OD TEU)

Penalties or rewards used by an optimiser never appear here.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

TOL = 1e-6


@dataclass(frozen=True)
class LedgerService:
    service_id: str
    ports: Tuple[str, ...]
    vessel_class: str
    frequency: int                   # departures per week


@dataclass(frozen=True)
class LedgerFlow:
    od: int                          # index into the demand list
    segments: Tuple[Tuple[str, str, str], ...]   # (service_id, from_port, to_port)
    teu: float


@dataclass
class Ledger:
    revenue: float = 0.0
    vessel_cost: float = 0.0
    fuel_cost: float = 0.0
    port_call_fixed_cost: float = 0.0       # includes the canal fees (memo item ``canal_fee_cost``)
    canal_fee_cost: float = 0.0
    handling_cost: float = 0.0
    transshipment_cost: float = 0.0
    port_variable_cost: float = 0.0
    served_teu: float = 0.0
    unserved_teu: float = 0.0
    total_demand_teu: float = 0.0
    vessels_by_class: Dict[str, int] = field(default_factory=dict)
    vessels_by_service: Dict[str, int] = field(default_factory=dict)
    cycle_time_days: Dict[str, int] = field(default_factory=dict)
    service_rows: Dict[str, Dict] = field(default_factory=dict)
    od_served: Dict[int, float] = field(default_factory=dict)
    violations: List[Dict] = field(default_factory=list)

    @property
    def operating_cost(self) -> float:
        return (self.vessel_cost + self.fuel_cost + self.port_call_fixed_cost
                + self.handling_cost + self.transshipment_cost + self.port_variable_cost)

    @property
    def operating_profit(self) -> float:
        return self.revenue - self.operating_cost

    @property
    def coverage(self) -> float:
        return self.served_teu / self.total_demand_teu if self.total_demand_teu > 0 else 0.0

    @property
    def valid(self) -> bool:
        return not self.violations

    def to_dict(self) -> Dict:
        return {
            "revenue": self.revenue, "vessel_cost": self.vessel_cost, "fuel_cost": self.fuel_cost,
            "port_call_fixed_cost": self.port_call_fixed_cost, "handling_cost": self.handling_cost,
            "transshipment_cost": self.transshipment_cost, "port_variable_cost": self.port_variable_cost,
            "operating_cost": self.operating_cost, "operating_profit": self.operating_profit,
            "served_teu": self.served_teu, "unserved_teu": self.unserved_teu,
            "total_demand_teu": self.total_demand_teu, "coverage": self.coverage,
            "vessels_by_class": dict(self.vessels_by_class),
            "valid": self.valid, "violations": list(self.violations),
        }


def _num(x, default=0.0) -> float:
    return float(x) if isinstance(x, (int, float)) and math.isfinite(x) else default


def compute_ledger(
    services: Sequence[LedgerService],
    flows: Sequence[LedgerFlow],
    demands: Sequence,
    fleet,
    distance_matrix: Dict,
    port_lookup: Dict,
    *,
    port_stay_hours: float,
    transshipment_min_hours: float,
    transfer_wait_days: float,
    bunker_price_usd_per_t: float,
    unserved_reported: Optional[Dict[int, float]] = None,
    speed_factor: float = 1.0,
    fuel_prices: Optional[Mapping[str, Mapping[str, Any]]] = None,
    max_transfers: int = 1,
) -> Ledger:
    """Recompute the economics of a plan and validate it. Never raises for a bad
    plan: every problem is a structured violation.

    ``bunker_price_usd_per_t`` is the uniform price. When ``fuel_prices`` is given
    (``service_id -> {"price": USD/t, ...}``) every service is priced at ITS entry and
    a service without a valid entry is a ``missing_fuel_price`` violation - a missing
    price is never replaced by the uniform one.

    ``max_transfers`` is the number of transfers a journey may have (a flow has at most
    ``max_transfers + 1`` segments); 1 reproduces the original two-segment rule.  Every
    transfer adds the hub dwell to the transit time and the hub charges to the cost."""
    L = Ledger()
    bad = L.violations.append
    stay_days = port_stay_hours / 24.0
    dwell_days = transshipment_min_hours / 24.0 + transfer_wait_days

    # ---- services: rotation, time, vessels, fixed costs ----------------------------
    svc: Dict[str, Dict] = {}
    for s in services:
        if s.service_id in svc:
            bad({"type": "duplicate_service", "service": s.service_id})
            continue
        f = s.frequency
        if not isinstance(f, int) or isinstance(f, bool) or f < 0:
            bad({"type": "invalid_frequency", "service": s.service_id, "value": f})
            continue
        cls = fleet.get_class(s.vessel_class) if fleet is not None else None
        if cls is None:
            bad({"type": "unknown_vessel_class", "service": s.service_id, "class": s.vessel_class})
            continue
        ports = list(s.ports)
        if len(ports) >= 2 and ports[0] == ports[-1]:
            ports = ports[:-1]
        if len(ports) < 2 or len(set(ports)) != len(ports):
            bad({"type": "invalid_route", "service": s.service_id, "ports": list(s.ports)})
            continue
        legs, missing = [], False
        for i, a in enumerate(ports):
            b = ports[(i + 1) % len(ports)]
            d = (distance_matrix.get(a) or {}).get(b)
            if not (isinstance(d, (int, float)) and math.isfinite(d) and d > 0):
                bad({"type": "missing_distance", "service": s.service_id, "leg": (a, b)})
                missing = True
                break
            legs.append(float(d))
        if missing:
            continue
        absent = [p for p in ports if p not in port_lookup]
        if absent:
            bad({"type": "missing_port_record", "service": s.service_id, "ports": absent})
            continue
        # physical rules (recomputed here from the raw records, not from the service model):
        # draft feasibility and canal traversals of the closed rotation
        canal_fee = 0.0
        vd = _num(getattr(cls, "draft", 0.0))
        flags = getattr(distance_matrix, "canal_flags", None) or {}
        edraft = getattr(distance_matrix, "edge_draft", None) or {}
        if vd > 0:
            low = [p for p in ports if 0 < _num(getattr(port_lookup.get(p), "draft", 0.0)) < vd - 1e-9]
            if low:
                bad({"type": "draft_infeasible", "service": s.service_id, "class": cls.vessel_class,
                     "class_draft": vd, "ports": low})
                continue
        n_pan = n_sue = 0
        blocked = None
        for i, a in enumerate(ports):
            b = ports[(i + 1) % len(ports)]
            if vd > 0 and (a, b) in edraft and vd > edraft[(a, b)] + 1e-9:
                blocked = {"type": "draft_infeasible", "service": s.service_id, "class": cls.vessel_class,
                           "class_draft": vd, "leg": (a, b), "leg_limit": edraft[(a, b)]}
                break
            pan, sue = flags.get((a, b), (0, 0))
            n_pan += int(pan)
            n_sue += int(sue)
        if blocked is not None:
            bad(blocked)
            continue
        for n_t, fee, nm in ((n_pan, getattr(cls, "panama_fee", None), "Panama"),
                             (n_sue, getattr(cls, "suez_fee", None), "Suez")):
            if n_t <= 0:
                continue
            if fee is None:
                bad({"type": "canal_not_passable", "service": s.service_id, "class": cls.vessel_class,
                     "canal": nm, "traversals": n_t})
                canal_fee = None
                break
            canal_fee += n_t * float(fee)
        if canal_fee is None:
            continue
        price = bunker_price_usd_per_t
        if fuel_prices is not None:
            entry = fuel_prices.get(s.service_id)
            p = entry.get("price") if isinstance(entry, Mapping) else None
            if not (isinstance(p, (int, float)) and not isinstance(p, bool)
                    and math.isfinite(p) and p >= 0):
                bad({"type": "missing_fuel_price", "service": s.service_id, "value": p})
                continue
            price = float(p)
        speed = cls.design_speed * speed_factor
        leg_days = [d / (speed * 24.0) for d in legs]
        sea_days = sum(leg_days)
        port_days = len(ports) * stay_days
        fuel_t = sea_days * cls.bunker_consumption_tons_per_day \
            + port_days * cls.idle_consumption_tons_per_day
        cycle = math.ceil(round(sea_days + port_days, 9))
        vessels = 0 if f == 0 else math.ceil(round(cycle * f / 7.0, 9))
        svc[s.service_id] = {
            "ports": ports, "class": cls, "f": f, "leg_days": leg_days, "cycle": cycle,
            "vessels": vessels, "cap": float(cls.capacity_teu),
            "vessel_cost": vessels * cls.tc_rate_daily * 7.0,
            "fuel": f * fuel_t * price,
            "fuel_tonnes": f * fuel_t, "fuel_price": price,
            "port_fixed": f * (sum(_num(getattr(port_lookup.get(p), "port_call_cost", 0.0)) for p in ports)
                               + canal_fee),
            "canal_fee": f * canal_fee,
            "revenue": 0.0, "load": 0.0, "var_cost": 0.0,
        }
        L.cycle_time_days[s.service_id] = cycle
        L.vessels_by_service[s.service_id] = vessels
        L.vessels_by_class[cls.vessel_class] = L.vessels_by_class.get(cls.vessel_class, 0) + vessels
        L.vessel_cost += svc[s.service_id]["vessel_cost"]
        L.fuel_cost += svc[s.service_id]["fuel"]
        L.port_call_fixed_cost += svc[s.service_id]["port_fixed"]
        L.canal_fee_cost += svc[s.service_id]["canal_fee"]

    # fleet inventory per class
    for cname, used in L.vessels_by_class.items():
        avail = fleet.quantity_of(cname)
        if used > avail:
            bad({"type": "fleet_exceeded", "class": cname, "used": used, "available": avail,
                 "excess": used - avail})

    # ---- flows: revenue, per-TEU charges, leg loads, transit --------------------
    leg_load: Dict[Tuple[str, int], float] = defaultdict(float)
    served: Dict[int, float] = defaultdict(float)
    for fl in flows:
        if not (isinstance(fl.teu, (int, float)) and math.isfinite(fl.teu) and fl.teu >= 0):
            bad({"type": "invalid_flow", "od": fl.od, "teu": fl.teu})
            continue
        if fl.teu <= TOL:
            continue
        if not 0 <= fl.od < len(demands):
            bad({"type": "unknown_od", "od": fl.od})
            continue
        d = demands[fl.od]
        segs = fl.segments
        if not segs or len(segs) > max_transfers + 1:
            bad({"type": "invalid_path", "od": fl.od,
                 "detail": f"needs 1..{max_transfers + 1} segments"})
            continue
        if segs[0][1] != d.origin or segs[-1][2] != d.destination:
            bad({"type": "invalid_path", "od": fl.od,
                 "detail": f"path {segs[0][1]}->{segs[-1][2]} does not connect {d.origin}->{d.destination}"})
            continue
        broken = next((k for k in range(len(segs) - 1) if segs[k][2] != segs[k + 1][1]), None)
        if broken is not None:
            bad({"type": "invalid_transfer", "od": fl.od,
                 "detail": f"arrives {segs[broken][2]}, next departs {segs[broken + 1][1]}"})
            continue
        if len(segs) > 2:
            # a journey never revisits a port: origin, every transfer port, destination
            stops = [segs[0][1]] + [s[2] for s in segs]
            if len(set(stops)) != len(stops):
                bad({"type": "invalid_path", "od": fl.od,
                     "detail": f"journey revisits a port: {stops}"})
                continue
            sids = [s[0] for s in segs]
            if len(set(sids)) != len(sids):
                bad({"type": "invalid_path", "od": fl.od,
                     "detail": f"journey rides a service twice: {sids}"})
                continue

        transit, ride_days, path_ok = 0.0, [], True
        for k, (sid, a, b) in enumerate(segs):
            s = svc.get(sid)
            if s is None or s["f"] <= 0:
                bad({"type": "flow_on_inactive_service", "od": fl.od, "service": sid})
                path_ok = False
                break
            ports = s["ports"]
            if a not in ports or b not in ports or a == b:
                bad({"type": "invalid_route", "od": fl.od, "service": sid,
                     "detail": f"{a}->{b} not on rotation {ports}"})
                path_ok = False
                break
            i, j, n = ports.index(a), ports.index(b), len(ports)
            days, idx = 0.0, i
            while idx != j:
                leg_load[(sid, idx)] += fl.teu
                days += s["leg_days"][idx]
                idx = (idx + 1) % n
                if idx != j:
                    days += stay_days
            ride_days.append(days)
            transit += days
        if not path_ok:
            continue
        if len(segs) > 1:
            transit += dwell_days * (len(segs) - 1)
        limit = getattr(d, "max_transit_days", None)
        if limit is not None and transit > limit + 1e-9:
            bad({"type": "transit_time_exceeded", "od": fl.od, "transit_days": transit, "limit_days": limit})

        o, t = port_lookup.get(d.origin), port_lookup.get(d.destination)
        if o is None or t is None or any(port_lookup.get(segs[k][2]) is None
                                         for k in range(len(segs) - 1)):
            bad({"type": "missing_port_record", "od": fl.od})
            continue
        L.revenue += fl.teu * d.revenue_per_teu
        L.handling_cost += fl.teu * (_num(getattr(o, "handling_cost", 0.0)) + _num(getattr(t, "handling_cost", 0.0)))
        L.port_variable_cost += fl.teu * (_num(getattr(o, "variable_port_call_cost", 0.0))
                                          + _num(getattr(t, "variable_port_call_cost", 0.0)))
        path_var = (_num(getattr(o, "handling_cost", 0.0)) + _num(getattr(t, "handling_cost", 0.0))
                    + _num(getattr(o, "variable_port_call_cost", 0.0))
                    + _num(getattr(t, "variable_port_call_cost", 0.0)))
        for k in range(len(segs) - 1):
            h = port_lookup.get(segs[k][2])
            L.transshipment_cost += fl.teu * _num(getattr(h, "transshipment_cost", 0.0))
            L.port_variable_cost += fl.teu * 2.0 * _num(getattr(h, "variable_port_call_cost", 0.0))
            path_var += (_num(getattr(h, "transshipment_cost", 0.0))
                         + 2.0 * _num(getattr(h, "variable_port_call_cost", 0.0)))
        served[fl.od] += fl.teu
        # attribution only (totals above are what count): split by ride days
        tot = sum(ride_days) or 1.0
        for (sid, _a, _b), rd in zip(segs, ride_days):
            share = rd / tot
            row = svc[sid]
            row["revenue"] += fl.teu * d.revenue_per_teu * share
            row["load"] += fl.teu * share if len(segs) == 1 else fl.teu
            row["var_cost"] += fl.teu * path_var * share

    # ---- leg capacity ---------------------------------------------------------------
    for (sid, leg), load in leg_load.items():
        cap = svc[sid]["cap"] * svc[sid]["f"]
        if load > cap + 1e-6 * max(1.0, cap):
            a = svc[sid]["ports"][leg]
            b = svc[sid]["ports"][(leg + 1) % len(svc[sid]["ports"])]
            bad({"type": "leg_capacity_exceeded", "service": sid, "leg": (a, b),
                 "load": load, "capacity": cap, "excess": load - cap})

    # ---- demand conservation --------------------------------------------------------
    for di, d in enumerate(demands):
        if not d.weekly_teu > 0:
            continue
        L.total_demand_teu += d.weekly_teu
        s_teu = served.get(di, 0.0)
        L.od_served[di] = s_teu
        if s_teu > d.weekly_teu + 1e-6 * max(1.0, d.weekly_teu):
            bad({"type": "demand_overserved", "od": di, "served": s_teu, "demand": d.weekly_teu})
        if unserved_reported is not None and di in unserved_reported:
            if abs(s_teu + unserved_reported[di] - d.weekly_teu) > 1e-5 * max(1.0, d.weekly_teu):
                bad({"type": "demand_not_conserved", "od": di, "served": s_teu,
                     "unserved": unserved_reported[di], "demand": d.weekly_teu})
    L.served_teu = sum(min(L.od_served.get(di, 0.0), d.weekly_teu)
                       for di, d in enumerate(demands) if d.weekly_teu > 0)
    L.unserved_teu = max(0.0, L.total_demand_teu - L.served_teu)

    legs_carried: Dict[str, float] = defaultdict(float)
    for (sid, _leg), load in leg_load.items():
        legs_carried[sid] += load
    for sid, r in svc.items():
        offered_legs = r["cap"] * r["f"] * len(r["ports"])         # closed rotation: one leg per port
        L.service_rows[sid] = {
            # utilisation of the offered slot capacity: carried TEU-legs / (capacity x f x legs); the
            # ``load`` below is the weekly cargo through the service and is NOT comparable with the
            # per-departure ``capacity_per_departure``
            "weekly_capacity_per_leg": r["cap"] * r["f"], "carried_teu_legs": legs_carried.get(sid, 0.0),
            "offered_teu_legs": offered_legs,
            "leg_load_factor": (legs_carried.get(sid, 0.0) / offered_legs) if offered_legs > 0 else None,
            "ports": list(r["ports"]), "vessel_class": r["class"].vessel_class,
            "frequency": r["f"], "vessels": r["vessels"], "cycle_time_days": r["cycle"],
            "capacity_per_departure": r["cap"], "load": r["load"], "revenue": r["revenue"],
            "vessel_cost": r["vessel_cost"], "fuel_cost": r["fuel"],
            "fuel_tonnes": r["fuel_tonnes"], "fuel_price_usd_per_t": r["fuel_price"],
            "port_cost": r["port_fixed"] + r["var_cost"],
        }
    return L
