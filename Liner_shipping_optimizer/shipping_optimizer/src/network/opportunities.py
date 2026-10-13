"""Executive opportunity register (Issue 5): why each service is operated and which alternatives merit review.

Read-only analysis of a finished plan; it changes no decision of the optimiser and is not part of the
production pipeline.  Two dimensions are kept apart and never conflated:

  operational status   FEASIBLE | CONDITIONALLY_FEASIBLE | INFEASIBLE | UNKNOWN
  commercial status    POSITIVE_MARGIN | NEGATIVE_MARGIN | UNCERTAIN

Method (global marginal economics, not stand-alone profit)
  * ``network_profit(F)``: with the set ``F`` of operated services and their weekly frequencies fixed,
    cargo is routed by an LP over ALL valid time-feasible paths whose services are all in ``F``
    (each OD at most once, every leg capacity ``capacity x f``); profit = routed margin - fixed costs
    (vessels = ceil(T f / 7), fuel, port calls).  This is the model's own accounting.
  * operated service s:   marginal profit = P(F) - P(F without s)      (what the network loses without it)
  * alternative c not in F: marginal profit = max over f in {1, 2} of P(F + c at f) - P(F).
  * operational status of an alternative: its vessels fit the idle inventory of its class -> FEASIBLE;
    otherwise CONDITIONALLY_FEASIBLE with the exact condition (vessels of which class to add or charter);
    a candidate the service model rejected -> INFEASIBLE with the stated reasons; a missing price -> UNKNOWN.
  * commercial status: the sign of the marginal profit under the stated accounting; UNCERTAIN when the sign
    changes under any sensitivity scenario (fuel price +-25 %, capacity unit read at half).  The hire cost of
    vessels that would have to be added is already inside the marginal profit (charter at the class TC rate).

A conditional or negative item is never presented as an executable feasible schedule.
"""
from __future__ import annotations

import dataclasses
import math
import time
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

import pulp

SCENARIOS = {
    "fuel_plus_25pct": {"fuel_mult": 1.25, "cap_mult": 1.0},
    "fuel_minus_25pct": {"fuel_mult": 0.75, "cap_mult": 1.0},
    "capacity_half": {"fuel_mult": 1.0, "cap_mult": 0.5},
}
EPS_USD = 1.0


class PathIndex:
    """All valid paths grouped by the set of services they use."""

    def __init__(self, paths_by_od: Dict[int, List]):
        self.by_services: Dict[frozenset, List[Tuple[int, object]]] = defaultdict(list)
        for di, plist in paths_by_od.items():
            for p in plist:
                self.by_services[frozenset(p.services)].append((di, p))

    def columns(self, operated: Sequence[int]) -> List[Tuple[int, object]]:
        ops = set(operated)
        out: List[Tuple[int, object]] = []
        for key, rows in self.by_services.items():
            if key <= ops:
                out.extend(rows)
        return out


def _scaled(models, fuel_mult: float, cap_mult: float):
    if fuel_mult == 1.0 and cap_mult == 1.0:
        return models
    return [dataclasses.replace(m, fuel_cost_per_rotation=m.fuel_cost_per_rotation * fuel_mult,
                                capacity_teu=m.capacity_teu * cap_mult) for m in models]


def network_profit(models, demands, index: PathIndex, freq: Dict[int, int], *, want_flows: bool = False,
                   time_limit_sec: float = 30.0) -> Dict:
    """Profit of the network ``freq`` (service index -> weekly frequency, > 0 only)."""
    fixed = sum(models[s].weekly_fixed_cost(f) for s, f in freq.items() if f > 0)
    cols = index.columns([s for s, f in freq.items() if f > 0])
    if not cols:
        return {"profit": -fixed, "margin": 0.0, "fixed": fixed, "served_teu": 0.0, "flows": []}
    prob = pulp.LpProblem("Marginal", pulp.LpMaximize)
    q = [pulp.LpVariable(f"q{j}", lowBound=0) for j in range(len(cols))]
    prob += pulp.lpSum((demands[di].revenue_per_teu - p.port_cost_per_teu) * q[j] for j, (di, p) in enumerate(cols))
    by_od: Dict[int, List[int]] = defaultdict(list)
    by_leg: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for j, (di, p) in enumerate(cols):
        by_od[di].append(j)
        for seg in p.segments:
            for leg in seg.legs:
                by_leg[(seg.service, leg)].append(j)
    for di, js in by_od.items():
        prob += pulp.lpSum(q[j] for j in js) <= float(demands[di].weekly_teu)
    for (si, leg), js in by_leg.items():
        prob += pulp.lpSum(q[j] for j in js) <= models[si].capacity_teu * freq[si]
    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=max(1, int(time_limit_sec))))
    if prob.status != pulp.LpStatusOptimal:
        raise RuntimeError(f"marginal LP status {pulp.LpStatus.get(prob.status)}")
    margin = float(pulp.value(prob.objective) or 0.0)
    flows = []
    served = 0.0
    for j, (di, p) in enumerate(cols):
        v = float(q[j].varValue or 0.0)
        if v > 1e-6:
            served += v
            if want_flows:
                flows.append((di, p, v))
    return {"profit": margin - fixed, "margin": margin, "fixed": fixed, "served_teu": served, "flows": flows}


def _vessels_by_class(models, freq) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    for s, f in freq.items():
        if f > 0:
            out[models[s].vessel_class] += models[s].vessels(f)
    return dict(out)


def _commercial(base: float, scen: Dict[str, float]) -> str:
    vals = [base] + list(scen.values())
    if all(v > EPS_USD for v in vals):
        return "POSITIVE_MARGIN"
    if all(v < -EPS_USD for v in vals):
        return "NEGATIVE_MARGIN"
    if (base > EPS_USD) != any(v > EPS_USD for v in scen.values()) or (base < -EPS_USD) != any(v < -EPS_USD for v in scen.values()):
        return "UNCERTAIN"
    return "POSITIVE_MARGIN" if base > EPS_USD else ("NEGATIVE_MARGIN" if base < -EPS_USD else "UNCERTAIN")


def build_register(models, demands, paths_by_od, freq: Dict[int, int], class_inventory: Dict[str, int],
                   *, rejected: Optional[Sequence[Dict]] = None, top_k: int = 120, report_k: int = 40,
                   frequencies_tried: Sequence[int] = (1, 2), log=None) -> Dict:
    """Register for the plan ``freq``.  ``paths_by_od`` must be the FULL valid path set (not capped)."""
    t0 = time.perf_counter()
    index = PathIndex(paths_by_od)
    F = {s: f for s, f in freq.items() if f > 0}
    base = network_profit(models, demands, index, F, want_flows=True)
    used = _vessels_by_class(models, F)
    out: Dict = {"network": {"profit_usd_wk": base["profit"], "served_teu": base["served_teu"],
                             "fixed_cost_usd_wk": base["fixed"], "services": len(F),
                             "vessels_used": used, "vessels_idle": {c: class_inventory.get(c, 0) - used.get(c, 0)
                                                                     for c in class_inventory}},
                 "operated": [], "opportunities": [], "infeasible": [], "method_seconds": None}

    # ---- operated services: why they are operated ---------------------------------------------
    carried: Dict[int, float] = defaultdict(float)
    transfer_share: Dict[int, float] = defaultdict(float)
    transit_w: Dict[int, float] = defaultdict(float)
    teu_legs: Dict[int, float] = defaultdict(float)
    for di, p, v in base["flows"]:
        for seg in p.segments:
            teu_legs[seg.service] += v * len(seg.legs)
        for s in set(p.services):
            carried[s] += v
            transit_w[s] += v * p.transit_days
            if len(set(p.services)) > 1:
                transfer_share[s] += v
    for s, f in sorted(F.items()):
        m = models[s]
        without = {k: v for k, v in F.items() if k != s}
        marg = base["profit"] - network_profit(models, demands, index, without)["profit"]
        alone = network_profit(models, demands, index, {s: f})["profit"]
        sens = {}
        for name, sc in SCENARIOS.items():
            ms = _scaled(models, sc["fuel_mult"], sc["cap_mult"])
            sens[name] = network_profit(ms, demands, index, F)["profit"] - network_profit(ms, demands, index, without)["profit"]
        offered = m.capacity_teu * f * len(m.legs)
        out["operated"].append({
            "service_id": m.service_id, "ports": list(m.ports), "vessel_class": m.vessel_class,
            "capacity_per_departure_teu": m.capacity_teu, "frequency_per_week": f, "vessels": m.vessels(f),
            "cycle_days": m.cycle_time_days, "standalone_profit_usd_wk": alone,
            "network_marginal_profit_usd_wk": marg, "carried_teu": carried.get(s, 0.0),
            "load_factor_mean": (teu_legs[s] / offered) if offered > 0 else None,
            "share_of_flow_that_connects_to_other_services": (transfer_share[s] / carried[s]) if carried.get(s) else 0.0,
            "mean_transit_days_of_flows": (transit_w[s] / carried[s]) if carried.get(s) else None,
            "operational_status": "FEASIBLE", "commercial_status": _commercial(marg, sens),
            "sensitivity_marginal_profit_usd_wk": sens,
            "role": ("connecting (feeder/hub)" if carried.get(s) and transfer_share[s] / carried[s] > 0.3 else "direct"),
        })

    # ---- alternatives -----------------------------------------------------------------------------
    unserved_rev = _unserved_revenue(demands, base["flows"])
    cands = []
    for s in range(len(models)):
        if s in F:
            continue
        ops = set(F) | {s}
        pot = 0.0
        best_od: Dict[int, float] = {}
        for key, rows in index.by_services.items():
            if s in key and key <= ops:
                for di, p in rows:
                    gain = min(float(demands[di].weekly_teu), models[s].capacity_teu) * max(0.0, demands[di].revenue_per_teu - p.port_cost_per_teu)
                    if gain > best_od.get(di, 0.0):
                        best_od[di] = gain
        pot = sum(best_od.values()) - models[s].weekly_fixed_cost(1)
        cands.append((pot, s))
    cands.sort(reverse=True)
    evaluated = []
    for pot, s in cands[:top_k]:
        best = None
        for f in frequencies_tried:
            trial = dict(F)
            trial[s] = f
            r = network_profit(models, demands, index, trial)
            marg = r["profit"] - base["profit"]
            if best is None or marg > best[0]:
                best = (marg, f, r)
        if best is None:
            continue
        marg, f, r = best
        m = models[s]
        need = m.vessels(f)
        avail = class_inventory.get(m.vessel_class, 0) - used.get(m.vessel_class, 0)
        evaluated.append((marg, s, f, need, avail, r))
    evaluated.sort(reverse=True, key=lambda t: t[0])
    for marg, s, f, need, avail, r in evaluated[:report_k]:
        m = models[s]
        trial = dict(F)
        trial[s] = f
        sens = {}
        for name, sc in SCENARIOS.items():
            ms = _scaled(models, sc["fuel_mult"], sc["cap_mult"])
            sens[name] = network_profit(ms, demands, index, trial)["profit"] - network_profit(ms, demands, index, F)["profit"]
        if need <= avail:
            op, cond = "FEASIBLE", []
        else:
            op, cond = "CONDITIONALLY_FEASIBLE", [{"vessel_class": m.vessel_class, "additional_vessels_required": need - max(avail, 0),
                                                    "idle_in_inventory": max(avail, 0), "needed": need}]
        out["opportunities"].append({
            "service_id": m.service_id, "ports": list(m.ports), "vessel_class": m.vessel_class,
            "capacity_per_departure_teu": m.capacity_teu, "frequency_per_week": f, "vessels_required": need,
            "network_marginal_profit_usd_wk": marg,
            "incremental_served_teu": r["served_teu"] - base["served_teu"],
            "incremental_fixed_cost_usd_wk": r["fixed"] - base["fixed"],
            "cycle_days": m.cycle_time_days,
            "operational_status": op, "unmet_conditions": cond,
            "commercial_status": _commercial(marg, sens),
            "sensitivity_marginal_profit_usd_wk": sens,
            "evaluated_alternatives_in_pool": len(evaluated),
        })
    for r in (rejected or []):
        out["infeasible"].append({"service_id": r.get("service"), "operational_status": "INFEASIBLE",
                                  "reasons": r.get("reasons", [])})
    out["method_seconds"] = round(time.perf_counter() - t0, 1)
    out["alternatives_evaluated"] = len(evaluated)
    out["alternatives_with_positive_marginal"] = sum(1 for e in evaluated if e[0] > EPS_USD)
    return out


def _unserved_revenue(demands, flows) -> float:
    served: Dict[int, float] = defaultdict(float)
    for di, _p, v in flows:
        served[di] += v
    return sum(max(0.0, d.weekly_teu - served.get(di, 0.0)) * d.revenue_per_teu for di, d in enumerate(demands))
