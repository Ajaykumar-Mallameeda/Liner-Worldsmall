"""Independent itemised ledger for the paper-comparison cost equations (FFE-native; NOT the operational model).

Equations (Dutta, Lin, Jin, arXiv:2411.09068, Appendix A, Eq. 28-35), weekly horizon:

  profit = R_total - C_reject - C_handle - C_NDP,                 C_NDP = C_service + C_unused + C_voyage
  R_total  = sum_d R_d  x FFE delivered                            (Eq. 29)
  C_reject = Y x FFE rejected, Y = 1000 USD per FFE                (Eq. 30, App. A.1)
  C_handle = sum_flows q x (p_l[origin] + p_l[destination] + sum p_t[transfer port])   (Eq. 31)
  C_service = sum_s n_s x TC_daily x 7                             (Eq. 33; x7: weekly horizon, see below)
  C_unused  = -sum_class (N_class - sum_s n_s) x TC_daily x 7      (Eq. 34; a credit when vessels are spare,
                                                                    a charge when more are used than owned)
  C_voyage  = port calls (p_f + p_v x vessel capacity per call) + fuel (sailing + one idle day per port call)
              + canal fees                                          (Eq. 35)

What is verified and what is not is recorded in ``reports/continuation_20261015/ws3_paper_parity``; in short:
  * the structure above, the 1000 USD penalty, 1 FFE units, p_l at both ends and p_t per transfer, weekly
    TC x 7, the unused-vessel credit at the TC rate, one idle day per call, canal fee once per rotation: reconciled
    against the LINERLIB authors' own WorldSmall solution log (primary source) and against the paper's Table 1;
  * the basis of the voyage terms (once per weekly rotation = ``per_rotation``, or multiplied by the fractional vessel
    count n_s as Eq. 35 is printed = ``per_vessel``) is a switch: the authors' log supports ``per_rotation``; the
    printed equation is dimensionally ambiguous (no 24 h/day factor in the sailing time, n_s on a per-rotation cost);
  * the fuel price is NOT in the paper (it only says "converted to $"): it is an explicit argument; ``None`` leaves the
    fuel cost unavailable instead of inventing one.  The authors' log prints "600 USD" for the benchmark.

Nothing here imports the operational model.  The functions take plain data (``FfeData``) so that a result can be
recomputed by hand.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from src.benchmark.paper_evaluator import FfeData, PORT_DAYS

DAYS_PER_WEEK = 7.0
FFE_PER_FFE = 1.0
TEU_PER_FFE = 2.0


# ------------------------------------------------------------------------------------------ Target 3.1: units
def to_teu_native(data: FfeData) -> FfeData:
    """The same physical instance with every quantity expressed in TEU (1 FFE = 2 TEU) and every per-FFE rate per TEU.

    Quantities (demand, vessel capacity) x2; per-unit rates (revenue, p_l, p_t, p_v and the 1,000 USD per FFE rejection
    penalty) / 2; per-call, per-day and per-tonne amounts unchanged.  Total monetary amounts are invariant by construction; this is the representation change the
    invariance tests exercise."""
    d = copy.deepcopy(data)
    for p in d.ports.values():
        p["pl"] /= TEU_PER_FFE
        p["pt"] /= TEU_PER_FFE
        p["pv"] /= TEU_PER_FFE
    for dm in d.demands:
        dm["ffe"] *= TEU_PER_FFE
        dm["rev"] /= TEU_PER_FFE
    for c in d.classes.values():
        c["cap"] *= TEU_PER_FFE
    d.unit = "TEU"
    d.penalty_per_unit = data.penalty_per_unit / TEU_PER_FFE
    return d


# ------------------------------------------------------------------------------------------ Targets 3.2 / 3.4 / 3.5
def rotation_costs(data: FfeData, ports: Sequence[str], cls: str, *, fuel_price_usd_per_t: Optional[float] = None,
                   speed_knots: Optional[float] = None) -> Dict:
    """Itemised cost of ONE closed rotation (the return leg to the first port is included once), weekly rotation basis.

    Units: nm, knots, days, tonnes, USD.  ``speed_knots`` defaults to the class design speed (the paper's setting);
    the consumption is the design-point consumption (the source gives it at design speed only).  A different speed
    scales sailing fuel with the cubic law the LINERLIB log follows (used only to reconcile that log)."""
    c = data.classes[cls]
    legs = list(zip(ports, list(ports[1:]) + [ports[0]]))
    nm = sum(data.dist[l][0] for l in legs)
    v = float(c["speed"] if speed_knots is None else speed_knots)
    sea_days = nm / (v * 24.0)
    cons = float(c["fuel_sea"]) * ((v / float(c["speed"])) ** 3 if speed_knots is not None else 1.0)
    sea_t = sea_days * cons
    port_days = PORT_DAYS * len(ports)
    idle_t = port_days * float(c["fuel_idle"])
    fixed = sum(data.ports[p]["pf"] for p in ports)
    per_ffe = sum(data.ports[p]["pv"] * float(c["cap"]) for p in ports)
    pan = sum(data.dist[l][1] for l in legs)
    sue = sum(data.dist[l][2] for l in legs)
    pan_fee, sue_fee = c["panama"], c["suez"]
    canal = 0.0
    unpassable = []
    if pan:
        if pan_fee is None:
            unpassable.append(("panama", pan))
        else:
            canal += pan * float(pan_fee)
    if sue:
        if sue_fee is None:
            unpassable.append(("suez", sue))
        else:
            canal += sue * float(sue_fee)
    cycle_days = sea_days + port_days
    out = {
        "distance_nm": nm, "speed_knots": v, "sea_days": sea_days, "port_days": port_days, "cycle_days": cycle_days,
        "vessels_for_weekly_service": cycle_days / DAYS_PER_WEEK,
        "sailing_fuel_t": sea_t, "idle_fuel_t": idle_t, "fuel_t": sea_t + idle_t,
        "port_call_fixed_usd": fixed, "port_call_per_ffe_capacity_usd": per_ffe,
        "canal_traversals": {"panama": pan, "suez": sue}, "canal_usd": canal, "canal_unpassable": unpassable,
        "fuel_price_usd_per_t": fuel_price_usd_per_t,
        "fuel_usd": None if fuel_price_usd_per_t is None else (sea_t + idle_t) * fuel_price_usd_per_t,
        "sailing_fuel_usd": None if fuel_price_usd_per_t is None else sea_t * fuel_price_usd_per_t,
        "idle_fuel_usd": None if fuel_price_usd_per_t is None else idle_t * fuel_price_usd_per_t,
    }
    return out


# ------------------------------------------------------------------------------------------ Target 3.3
def fleet_accounting(data: FfeData, vessels_used: Dict[str, float]) -> Dict:
    """Vessel-service cost and the soft fleet term, per class and in total (USD per week).

    ``service``  = used x TC x 7                              (a cost)
    ``unused``   = (owned - used) x TC x 7                    (a CREDIT when positive; a CHARGE when negative: more
                                                               vessels are used than owned, they are acquired at the TC rate)
    The net fleet cost is service - unused_credit.  Operational C3 does not use this soft rule: it rejects a plan that uses
    more vessels than owned (``ledger`` violation ``fleet_exceeded``)."""
    rows = {}
    tot_service = tot_credit = 0.0
    for name, c in data.classes.items():
        used = float(vessels_used.get(name, 0.0))
        weekly = float(c["tc"]) * DAYS_PER_WEEK
        service = used * weekly
        credit = (float(c["n_avail"]) - used) * weekly
        rows[name] = {"owned": float(c["n_avail"]), "used": used, "tc_usd_per_day": float(c["tc"]), "service_cost_usd": service,
                      "unused_credit_usd": credit, "case": ("fewer_than_owned" if used < c["n_avail"] - 1e-12 else
                                                            "exactly_owned" if abs(used - c["n_avail"]) <= 1e-12 else "more_than_owned")}
        tot_service += service
        tot_credit += credit
    return {"by_class": rows, "service_cost_usd": tot_service, "unused_credit_usd": tot_credit,
            "net_fleet_cost_usd": tot_service - tot_credit}


# ------------------------------------------------------------------------------------------ Target 3.6: full ledger
@dataclass
class Hop:
    service: int
    board: str
    alight: str


def hops_from_edges(services: List[Dict], edges: List[Tuple[int, int]]) -> List[Hop]:
    """Hops of a flow from ``_greedy_mcf`` edges (destination to origin): consecutive legs of one service form one hop."""
    fwd = list(reversed(edges))
    out: List[Hop] = []
    for si, k in fwd:
        ps = services[si]["ports"]
        a, b = ps[k], ps[(k + 1) % len(ps)]
        if out and out[-1].service == si and out[-1].alight == a:
            out[-1] = Hop(si, out[-1].board, b)
        else:
            out.append(Hop(si, a, b))
    return out


def objective_ledger(data: FfeData, services: List[Dict], flows: List[Dict], rejected: Dict[Tuple[str, str], float], *,
                     fuel_price_usd_per_t: Optional[float], voyage_basis: str = "per_rotation",
                     canal_basis: str = "per_rotation", include_unused: bool = True) -> Dict:
    """Recompute the objective from selected services and explicit cargo flows.

    ``services``: [{"ports": closed rotation without the repeated start, "class": name, "n": fractional vessels, "f": departures/week}]
    ``flows``   : [{"od": (o, d), "ffe": q, "hops": [Hop, ...]}]   ``rejected``: {(o, d): FFE not carried}
    Each term is returned with its sign convention: costs positive, the unused-vessel term as ``unused_credit_usd``."""
    if voyage_basis not in ("per_rotation", "per_vessel") or canal_basis not in ("per_rotation", "per_vessel"):
        raise ValueError("voyage_basis / canal_basis must be 'per_rotation' or 'per_vessel'")
    rev_of = {(d["o"], d["d"]): d["rev"] for d in data.demands}
    revenue = handling = transship = 0.0
    served: Dict[Tuple[str, str], float] = {}
    for fl in flows:
        o, d = fl["od"]
        q = float(fl["ffe"])
        hops = fl["hops"]
        if not hops or hops[0].board != o or hops[-1].alight != d:
            raise ValueError(f"flow {o}->{d}: hops do not run from origin to destination")
        for h1, h2 in zip(hops, hops[1:]):
            if h1.alight != h2.board:
                raise ValueError(f"flow {o}->{d}: hop {h1} does not connect to {h2}")
        revenue += q * rev_of[(o, d)]
        handling += q * (data.ports[o]["pl"] + data.ports[d]["pl"])
        for h in hops[:-1]:
            transship += q * data.ports[h.alight]["pt"]
        served[(o, d)] = served.get((o, d), 0.0) + q
    rej_total = sum(float(v) for v in rejected.values())
    penalty = data.penalty_per_unit * rej_total
    service = unused_credit = 0.0
    used: Dict[str, float] = {}
    port_usd = fuel_t = canal = 0.0
    unresolved = []
    for s in services:
        used[s["class"]] = used.get(s["class"], 0.0) + float(s["n"])
        rc = rotation_costs(data, s["ports"], s["class"], fuel_price_usd_per_t=fuel_price_usd_per_t)
        mult = float(s["n"]) if voyage_basis == "per_vessel" else float(s["f"])
        cmult = float(s["n"]) if canal_basis == "per_vessel" else float(s["f"])
        port_usd += (rc["port_call_fixed_usd"] + rc["port_call_per_ffe_capacity_usd"]) * mult
        fuel_t += rc["fuel_t"] * mult
        canal += rc["canal_usd"] * cmult
        unresolved += [(s["ports"], u) for u in rc["canal_unpassable"]]
    fl = fleet_accounting(data, used)
    service = fl["service_cost_usd"]
    unused_credit = fl["unused_credit_usd"] if include_unused else 0.0
    fuel_usd = None if fuel_price_usd_per_t is None else fuel_t * fuel_price_usd_per_t
    handling_total = handling + transship
    profit = None
    if fuel_usd is not None:
        profit = revenue - penalty - handling_total - service - (port_usd + fuel_usd + canal) + unused_credit
    demand_total = sum(float(d["ffe"]) for d in data.demands)
    served_total = sum(served.values())
    return {"revenue_usd": revenue, "rejected_penalty_usd": penalty, "handling_loading_unloading_usd": handling,
            "transshipment_usd": transship, "handling_total_usd": handling_total, "vessel_service_usd": service,
            "unused_vessel_credit_usd": unused_credit, "port_calls_usd": port_usd, "canal_usd": canal,
            "fuel_t": fuel_t, "fuel_usd": fuel_usd, "voyage_total_usd": None if fuel_usd is None else port_usd + fuel_usd + canal,
            "net_profit_usd": profit, "served_ffe": served_total, "rejected_ffe": rej_total, "demand_ffe": demand_total,
            "coverage": served_total / demand_total if demand_total else None,
            "canal_unpassable_transits": unresolved, "fleet": fl,
            "basis": {"voyage": voyage_basis, "canal": canal_basis, "fuel_price_usd_per_t": fuel_price_usd_per_t,
                      "horizon": "weekly (TC x 7)"}}
