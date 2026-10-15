"""Network marginal-value pricing of candidate services from LP duals (study tool; no pipeline default, no flag).

Question (Workstream 6): the existing screen keeps a rotation only if its STAND-ALONE profit (its own direct cargo at full
revenue) is positive.  A rotation that fails it can still add network value - it takes cargo the network serves at a lower
margin, relieves congested legs and feeds hubs through ONE transfer to the services already operated.  Direct-cargo pricing
alone cannot show that (net revenue = revenue - dual(demand) <= revenue, so the net stand-alone value is never above the
stand-alone value); the paths that combine the new service with operated ones have to be priced.

Method (one LP relaxation of the current pool, then one small restricted LP per candidate):
  * duals of the LP relaxation (validated by finite differences in ``tests/test_targeted_paths.py``):
        dem_od     USD per TEU      marginal profit of one more TEU of that OD in the current network
        cap_s,leg  USD per TEU      marginal profit of one more TEU of capacity on that leg of an operated service
        fleet_c    USD per vessel   marginal profit of one more vessel of class c
  * candidate c, frequency f >= 0 (continuous), paths p through c (direct, or c + one operated service; time-feasible):
        max  sum_p q_p (revenue_od - port_p - dual(dem_od) - sum dual(cap) on the operated legs of p)
             - (fuel + port fixed) f - (vessel week cost + dual(fleet_c)) x cycle_days/7 x f
        s.t. cargo on every leg of c <= capacity(c) f ;  sum_p q_p <= weekly TEU of the OD
  * the optimum is the dual-priced network value of c per week (USD).  It is an LP estimate on the capped path model with
    operated-service capacity priced rather than limited and one candidate at a time; it is not the integer-plan profit and
    prices are not additive.  A candidate is only ever evaluated further by the real model and the independent ledger.
"""
from __future__ import annotations

import dataclasses
import time
from typing import Dict, List, Optional, Sequence, Tuple

import pulp

from src.network import network_milp as nm
from src.network.paths import PathConfig, SELECT_FASTEST, BUDGET_FIXED, build_paths
from src.network.targeted_paths import lp_duals


def fleet_duals(lp: Dict) -> Dict[str, float]:
    out = {}
    for name, con in lp["prob"].constraints.items():
        if name.startswith("fleet_") and name != "fleet_total" and getattr(con, "pi", None) is not None:
            out[name[len("fleet_"):]] = float(con.pi)
    return out


class BaseLp:
    """LP relaxation of the pool (models, paths, solution, duals) that candidates are priced against."""

    def __init__(self, planner, candidates: Sequence, time_limit_sec: float = 60.0):
        self.planner = planner
        problem = planner.problem
        self.models, _ = planner.build_models(candidates)
        self.demands = problem.demands
        self.paths, _ = build_paths(self.demands, self.models, planner.port_lookup, planner.assumptions,
                                    max_paths_per_od=planner.max_paths_per_od, config=planner.path_config)
        self.limits = {c.vessel_class: c.quantity for c in problem.fleet.classes}
        services = sorted({s for pl in self.paths.values() for p in pl for s in p.services})
        t0 = time.perf_counter()
        self.lp = nm._build_and_solve(self.models, self.demands, self.paths, self.limits, services, integer=False, penalty=0.0,
                                      fixed=None, initial=None, max_departures_cap=None, time_limit_sec=time_limit_sec,
                                      threads=None, vub=nm.vub_enabled())
        self.lp_sec = time.perf_counter() - t0
        self.ok = (not self.lp["error"]) and self.lp["prob"].status == pulp.LpStatusOptimal
        self.bound = float(pulp.value(self.lp["prob"].objective) or 0.0) if self.ok else None
        self.duals = lp_duals(self.lp) if self.ok else {"dem": {}, "cap": {}}
        self.fleet = fleet_duals(self.lp) if self.ok else {}
        self.operated = ([si for si in self.lp["active"] if (self.lp["f"][si].varValue or 0.0) > 1e-6] if self.ok else [])


def price_candidate(base: BaseLp, candidate, *, max_f: int = 14) -> Dict:
    """Dual-priced network value of ``candidate`` (see module docstring).  Returns a dict; never raises for a solver outcome."""
    planner = base.planner
    new_models, rej = planner.build_models([candidate])
    out = {"service_id": candidate.service_id, "ports": list(candidate.ports), "vessel_class": candidate.vessel_class,
           "value_usd_per_week": None, "f": None, "paths": 0, "reason": None}
    if not new_models:
        out["reason"] = "not modelled: " + "; ".join(r for x in rej for r in x.get("reasons", []))
        return out
    ms = new_models[0]
    sub_ids = list(base.operated)
    sub_models = [base.models[i] for i in sub_ids] + [ms]
    s_idx = len(sub_models) - 1
    pset = set(ms.ports)
    pick = [di for di, d in enumerate(base.demands) if d.weekly_teu > 0 and (d.origin in pset or d.destination in pset)]
    demands_sub = [base.demands[di] for di in pick]
    cfg = dataclasses.replace(planner.path_config, selection=SELECT_FASTEST, budget=BUDGET_FIXED)
    paths_sub, _ = build_paths(demands_sub, sub_models, planner.port_lookup, planner.assumptions, max_paths_per_od=10 ** 9, config=cfg)
    prob = pulp.LpProblem("price", pulp.LpMaximize)
    limit = int(base.limits.get(ms.vessel_class, ms.class_inventory))
    f = pulp.LpVariable("f", lowBound=0, upBound=max(1, min(max_f, ms.max_departures(limit))))
    q: Dict[Tuple[int, int], pulp.LpVariable] = {}
    margin: Dict[Tuple[int, int], float] = {}
    by_od: Dict[int, List] = {}
    leg_vars: Dict[int, List] = {}
    for sdi, plist in paths_sub.items():
        d = demands_sub[sdi]
        di = pick[sdi]
        for k, p in enumerate(plist):
            if s_idx not in p.services:
                continue
            m_ = float(d.revenue_per_teu) - float(p.port_cost_per_teu) - base.duals["dem"].get(di, 0.0)
            for seg in p.segments:
                if seg.service != s_idx:
                    base_si = sub_ids[seg.service]
                    for leg in seg.legs:
                        m_ -= base.duals["cap"].get((base_si, leg), 0.0)
            v = pulp.LpVariable(f"q_{sdi}_{k}", lowBound=0)
            q[(sdi, k)] = v
            margin[(sdi, k)] = m_
            by_od.setdefault(sdi, []).append(v)
            for seg in p.segments:
                if seg.service == s_idx:
                    for leg in seg.legs:
                        leg_vars.setdefault(leg, []).append(v)
    out["paths"] = len(q)
    if not q:
        out["reason"] = "no time-feasible path through the candidate"
        out["value_usd_per_week"] = 0.0
        out["f"] = 0.0
        return out
    fixed = ms.fuel_cost_per_rotation + ms.port_fixed_per_rotation
    vessel = (ms.vessel_week_cost + base.fleet.get(ms.vessel_class, 0.0)) * (ms.cycle_time_days / 7.0)
    prob += pulp.lpSum(margin[key] * v for key, v in q.items()) - (fixed + vessel) * f
    for sdi, vs in by_od.items():
        prob += pulp.lpSum(vs) <= float(demands_sub[sdi].weekly_teu)
    for leg, vs in leg_vars.items():
        prob += pulp.lpSum(vs) <= ms.capacity_teu * f
    try:
        prob.solve(pulp.PULP_CBC_CMD(msg=False))
    except Exception as exc:                                        # noqa: BLE001
        out["reason"] = f"{type(exc).__name__}: {exc}"
        return out
    if prob.status != pulp.LpStatusOptimal:
        out["reason"] = f"LP status {pulp.LpStatus.get(prob.status)}"
        return out
    out["value_usd_per_week"] = float(pulp.value(prob.objective) or 0.0)
    out["f"] = float(f.varValue or 0.0)
    out["served_teu"] = float(sum((v.varValue or 0.0) for v in q.values()))
    out["transfer_paths_used"] = sum(1 for (sdi, k), v in q.items()
                                     if (v.varValue or 0.0) > 1e-6 and len(paths_sub[sdi][k].services) > 1)
    return out


def actual_incremental_bound(base: BaseLp, base_candidates: Sequence, candidate, time_limit_sec: float = 60.0) -> Dict:
    """The ACTUAL model: LP bound of the pool plus ``candidate`` minus the pool's bound (what the price estimates)."""
    planner = base.planner
    models, _ = planner.build_models(list(base_candidates) + [candidate])
    paths, _ = build_paths(base.demands, models, planner.port_lookup, planner.assumptions, max_paths_per_od=planner.max_paths_per_od,
                           config=planner.path_config)
    services = sorted({s for pl in paths.values() for p in pl for s in p.services})
    lp = nm._build_and_solve(models, base.demands, paths, base.limits, services, integer=False, penalty=0.0, fixed=None, initial=None,
                             max_departures_cap=None, time_limit_sec=time_limit_sec, threads=None, vub=nm.vub_enabled())
    if lp["error"] or lp["prob"].status != pulp.LpStatusOptimal:
        return {"delta_bound_usd_per_week": None, "reason": "LP not solved"}
    b = float(pulp.value(lp["prob"].objective) or 0.0)
    cid = len(models) - 1
    return {"delta_bound_usd_per_week": b - base.bound, "candidate_f_lp": float(lp["f"][cid].varValue or 0.0) if cid in lp["f"] else 0.0}
