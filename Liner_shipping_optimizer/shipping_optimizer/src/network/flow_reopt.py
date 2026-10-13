"""Flow re-optimisation of a fixed network over the FULL valid path set (Task 20).

Why
    The global MILP chooses services, frequencies, vessels and cargo flows jointly, but only
    over the ``max_paths_per_od`` paths per OD that ``paths.py`` keeps (10 of ~53,000 valid
    paths on WorldSmall).  Measured on recorded plans (reports/tasks_19_20_21): holding the
    plan's services, frequencies and vessels fixed, re-routing the cargo over ALL valid paths
    adds 1.4 - 2.3 M USD/week and about one point of coverage, because capacity that is
    already paid for is out of reach of cargo whose usable paths were cut.

What it does
    With every frequency and vessel count fixed (so every fixed cost is unchanged) it solves
    the pure LP

        max  sum_p (revenue_od - per-TEU port charges_p) q_p
        s.t. sum_{p of od} q_p <= weekly demand_od                (each OD at most once)
             sum_{p rides (s, leg)} q_p <= capacity_s * f_s       (EVERY leg of every service)
             q_p >= 0, only paths whose services are ALL operated

    over all valid, time-feasible paths of the pool.  The incumbent's own flows are feasible
    in it, so the optimum is never below the incumbent's profit; the plan is replaced only if
    the new flows are better by more than a tolerance and the ledger still verifies it (the
    caller runs the independent ledger on whatever is returned).

What it does NOT do
    It changes no frequency, vessel count, service, price or constraint; it never serves less
    cargo than the incumbent (a coverage floor of the solved model included); it adds no cargo
    beyond demand; it cannot create a path the transit-time rule would have rejected (the
    full set is built by the same ``build_paths``).  It is not a proof of optimality: a plan
    it improves is reported ``feasible`` even if the MILP over the capped paths had closed.

Solver: PuLP + CBC (the production solver); no other engine is used.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import replace
from typing import Dict, List, Optional, Sequence, Tuple

import pulp

#: a plan is replaced only if the profit rises by more than this (USD / week)
MIN_GAIN_USD = 1.0
#: a routed quantity at or below this is solver noise, not a flow (same as the MILP)
FLOW_NOISE_TEU = 1e-6


def reoptimize_flows(models, demands, paths: Dict[int, List], sol, build_all_paths,
                     *, time_limit_sec: float = 60.0, min_served_teu: float = 0.0) -> Dict:
    """Re-route ``sol`` over the full valid path set; mutates ``paths`` (new paths are
    appended, existing indices are untouched) and ``sol`` (flows, unserved, objective) only
    when the profit improves.  Returns a report dict (always)."""
    t0 = time.perf_counter()
    rep: Dict = {"applied": False, "reason": "", "gain_usd": 0.0, "paths_considered": 0,
                 "paths_added": 0, "served_teu_before": 0.0, "served_teu_after": 0.0}
    f = {si: int(fr) for si, fr in sol.frequencies.items() if fr > 0}
    if not f or not sol.flows:
        rep["reason"] = "no operated service"
        return rep
    try:
        full, _stats = build_all_paths()
    except Exception as exc:                                       # noqa: BLE001
        rep["reason"] = f"full path set unavailable: {type(exc).__name__}: {exc}"
        return rep

    # candidate columns: every valid path whose services are all operated
    known = {(di, tuple(p.services), tuple(p.transfer_ports), tuple(s.legs for s in p.segments)): k
             for di, plist in paths.items() for k, p in enumerate(plist)}
    columns: List[Tuple[int, object, Optional[int]]] = []          # (od, path, index in paths or None)
    for di, plist in full.items():
        if not demands[di].weekly_teu > 0:
            continue
        for p in plist:
            if all(s in f for s in p.services):
                key = (di, tuple(p.services), tuple(p.transfer_ports), tuple(s.legs for s in p.segments))
                columns.append((di, p, known.get(key)))
    rep["paths_considered"] = len(columns)
    if not columns:
        rep["reason"] = "no valid path through the operated services"
        return rep

    prob = pulp.LpProblem("FlowReoptimisation", pulp.LpMaximize)
    q = [pulp.LpVariable(f"r_{j}", lowBound=0) for j in range(len(columns))]
    prob += pulp.lpSum((demands[di].revenue_per_teu - p.port_cost_per_teu) * q[j]
                       for j, (di, p, _k) in enumerate(columns))
    by_od: Dict[int, List[int]] = defaultdict(list)
    by_leg: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for j, (di, p, _k) in enumerate(columns):
        by_od[di].append(j)
        for seg in p.segments:
            for leg in seg.legs:
                by_leg[(seg.service, leg)].append(j)
    for di, js in by_od.items():
        prob += pulp.lpSum(q[j] for j in js) <= float(demands[di].weekly_teu), f"od_{di}"
    for (si, leg), js in by_leg.items():
        prob += pulp.lpSum(q[j] for j in js) <= models[si].capacity_teu * f[si], f"cap_{si}_{leg}"
    # Never serve less than the incumbent: the re-routing may only add cargo or trade it for
    # better cargo on the same capacity, so a coverage floor of the solved model (and the
    # incumbent's own coverage) can never be undercut.  The incumbent satisfies this, so the LP
    # is feasible.
    incumbent_served = float(sum(t for _, _, t in sol.flows))
    floor = max(float(min_served_teu), incumbent_served) - 1e-6
    if floor > 0.0:
        prob += pulp.lpSum(q) >= floor, "no_coverage_regression"
    try:
        prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=max(1, int(math.ceil(time_limit_sec)))))
    except Exception as exc:                                       # noqa: BLE001
        rep["reason"] = f"LP solver error: {type(exc).__name__}: {exc}"
        return rep
    if prob.status != pulp.LpStatusOptimal:
        rep["reason"] = f"LP status {pulp.LpStatus.get(prob.status, prob.status)}"
        return rep

    # carrying columns only; (od, path, index in the capped list or None, TEU)
    carrying: List[Tuple[int, object, Optional[int], float]] = []
    for j, (di, p, k) in enumerate(columns):
        val = float(q[j].varValue or 0.0)
        if val > FLOW_NOISE_TEU:
            carrying.append((di, p, k, val))

    def spec_margin(rows) -> float:
        return sum((demands[di].revenue_per_teu - p.port_cost_per_teu) * t for di, p, _k, t in rows)

    old_rows = [(di, paths[di][k], k, t) for di, k, t in sol.flows]
    old_margin, new_margin = spec_margin(old_rows), spec_margin(carrying)
    rep["served_teu_before"] = float(sum(t for _, _, _, t in old_rows))
    rep["served_teu_after"] = float(sum(t for _, _, _, t in carrying))
    rep["lp_sec"] = round(time.perf_counter() - t0, 2)
    if new_margin <= old_margin + MIN_GAIN_USD:
        # not applied: the plan keeps its flows, so no gain is claimed.  (The LP's margin can be BELOW the
        # incumbent's when the incumbent already uses paths outside this re-routing's enumeration, e.g.
        # after the exact-LP local search; the difference is recorded separately, never as a "gain".)
        rep["gain_usd"] = 0.0
        rep["lp_margin_minus_incumbent_usd"] = new_margin - old_margin
        rep["reason"] = "no improvement over the incumbent's flows"
        return rep
    rep["gain_usd"] = new_margin - old_margin

    # ---- accepted: extend the capped lists (existing indices untouched) and replace the flows
    new_flows: List[Tuple[int, int, float]] = []
    served_by_od: Dict[int, float] = defaultdict(float)
    appended = 0
    for di, p, k, val in carrying:
        if k is None:
            paths.setdefault(di, [])
            paths[di].append(p)
            k = len(paths[di]) - 1
            appended += 1
        new_flows.append((di, k, val))
        served_by_od[di] += val
    revenue = sum(demands[di].revenue_per_teu * t for di, _k, t in new_flows)
    port = sum(paths[di][k].port_cost_per_teu * t for di, k, t in new_flows)
    comp = dict(sol.objective_components)
    comp["revenue"], comp["per_teu_port_cost"] = revenue, port
    pen = comp.get("unserved_penalty", 0.0)
    sol.objective_value = (revenue - port - comp.get("vessel_cost", 0.0) - comp.get("fuel_cost", 0.0)
                           - comp.get("port_fixed_cost", 0.0) - pen)
    sol.objective_components = comp
    sol.flows = sorted(new_flows)
    sol.unserved = {di: max(0.0, float(demands[di].weekly_teu) - served_by_od.get(di, 0.0))
                    for di in sol.unserved}
    rep["applied"] = True
    rep["paths_added"] = appended
    rep["reason"] = "flows re-optimised over the full valid path set"
    return rep


# =====================================================================================
# Repair of a plan that violates the approved profit floor (Task 20)
# =====================================================================================
def repair_profit_floor(models, demands, paths: Dict[int, List], sol, build_all_paths,
                        *, floor_usd: float = 0.0, max_rounds: int = 6, trials_per_round: int = 6,
                        time_limit_sec: float = 90.0) -> Dict:
    """Switch off services that lose money until the plan's profit reaches the approved floor.

    A time-limited incumbent can carry loss-making services (measured: profits of -2 to -6 M
    USD/week on 3 of 10 paired pools for the production CBC solve).  The approved floor of the
    pipeline is a weekly profit of 0 (the coordinator re-runs an iteration below it).  When
    the plan's profit - cargo margin minus the fixed cost of every operated service - is below
    ``floor_usd``, this repair tries, round by round, to switch off the services whose
    attributed result is worst, re-routes the cargo over the remaining operated services (the
    LP of :func:`reoptimize_flows`) and keeps the move that raises the profit most.  It stops
    at the floor, when no move helps, or at the limits.  It never touches a plan that already
    meets the floor, never raises a frequency and changes no constraint; a dropped service
    simply is not operated.  The caller's independent ledger verifies the result; coverage
    may fall (the cargo of a dropped service that no other operated service can carry) and
    is reported."""
    t0 = time.perf_counter()
    rep: Dict = {"applied": False, "reason": "", "dropped": [], "profit_before": None,
                 "profit_after": None, "trials": 0, "rounds": 0,
                 "served_teu_before": float(sum(t for _, _, t in sol.flows)), "served_teu_after": None}
    f = {si: int(fr) for si, fr in sol.frequencies.items() if fr > 0}
    if not f or not sol.flows:
        rep["reason"] = "no operated service"
        return rep

    def fixed_cost(active: Dict[int, int]) -> float:
        return sum(models[si].weekly_fixed_cost(fr) for si, fr in active.items())

    cur_rows = [(di, paths[di][k], k, t) for di, k, t in sol.flows]
    cur_margin = sum((demands[di].revenue_per_teu - p.port_cost_per_teu) * t for di, p, _k, t in cur_rows)
    cur_profit = cur_margin - fixed_cost(f)
    rep["profit_before"] = cur_profit
    if cur_profit >= floor_usd:
        rep["reason"] = "profit floor met"
        return rep
    try:
        full, _stats = build_all_paths()
    except Exception as exc:                                       # noqa: BLE001
        rep["reason"] = f"full path set unavailable: {type(exc).__name__}: {exc}"
        return rep
    known = {(di, tuple(p.services), tuple(p.transfer_ports), tuple(s.legs for s in p.segments)): k
             for di, plist in paths.items() for k, p in enumerate(plist)}
    all_cols: List[Tuple[int, object, Optional[int]]] = []
    for di, plist in full.items():
        if not demands[di].weekly_teu > 0:
            continue
        for p in plist:
            if all(s in f for s in p.services):
                all_cols.append((di, p, known.get((di, tuple(p.services), tuple(p.transfer_ports),
                                                   tuple(s.legs for s in p.segments)))))

    def route(active: Dict[int, int]):
        """LP over the columns whose services are all in ``active``; (margin, carrying) or None."""
        cols = [c for c in all_cols if all(s in active for s in c[1].services)]
        if not cols:
            return 0.0, []
        prob = pulp.LpProblem("ProfitFloorRepair", pulp.LpMaximize)
        q = [pulp.LpVariable(f"r_{j}", lowBound=0) for j in range(len(cols))]
        prob += pulp.lpSum((demands[di].revenue_per_teu - p.port_cost_per_teu) * q[j]
                           for j, (di, p, _k) in enumerate(cols))
        by_od: Dict[int, List[int]] = defaultdict(list)
        by_leg: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        for j, (di, p, _k) in enumerate(cols):
            by_od[di].append(j)
            for seg in p.segments:
                for leg in seg.legs:
                    by_leg[(seg.service, leg)].append(j)
        for di, js in by_od.items():
            prob += pulp.lpSum(q[j] for j in js) <= float(demands[di].weekly_teu), f"od_{di}"
        for (si, leg), js in by_leg.items():
            prob += pulp.lpSum(q[j] for j in js) <= models[si].capacity_teu * active[si], f"cap_{si}_{leg}"
        prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=30))
        if prob.status != pulp.LpStatusOptimal:
            return None
        carrying = [(di, p, k, float(q[j].varValue or 0.0)) for j, (di, p, k) in enumerate(cols)
                    if float(q[j].varValue or 0.0) > FLOW_NOISE_TEU]
        margin = sum((demands[di].revenue_per_teu - p.port_cost_per_teu) * t for di, p, _k, t in carrying)
        return margin, carrying

    def attributed_profit(active: Dict[int, int], rows) -> Dict[int, float]:
        """Per-service result of the current cargo: revenue less per-TEU charges split over the
        services of a path by ride days (the ledger's attribution), minus the service's cost."""
        res: Dict[int, float] = {si: -models[si].weekly_fixed_cost(fr) for si, fr in active.items()}
        for di, p, _k, t in rows:
            tot = sum(s.ride_days for s in p.segments) or 1.0
            net = (demands[di].revenue_per_teu - p.port_cost_per_teu) * t
            for s in p.segments:
                res[s.service] = res.get(s.service, 0.0) + net * (s.ride_days / tot)
        return res

    cur_rows_spec = cur_rows
    dropped: List[int] = []
    for _round in range(max_rounds):
        if cur_profit >= floor_usd or time.perf_counter() - t0 > time_limit_sec:
            break
        rep["rounds"] += 1
        attr = attributed_profit(f, cur_rows_spec)
        order = [si for si in sorted(f, key=lambda s: (attr.get(s, 0.0), s)) if attr.get(si, 0.0) < 0.0]
        best = None
        for si in order[:trials_per_round]:
            if time.perf_counter() - t0 > time_limit_sec:
                break
            f2 = {s: v for s, v in f.items() if s != si}
            try:
                got = route(f2)
            except Exception:                                      # noqa: BLE001
                got = None
            rep["trials"] += 1
            if got is None:
                continue
            margin2, carrying2 = got
            profit2 = margin2 - fixed_cost(f2)
            if best is None or profit2 > best[0]:
                best = (profit2, si, f2, carrying2)
        if best is None or best[0] <= cur_profit + MIN_GAIN_USD:
            break
        cur_profit, si, f, cur_rows_spec = best[0], best[1], best[2], best[3]
        dropped.append(si)
    if not dropped:
        rep["reason"] = "no service switch-off raises the profit"
        rep["profit_after"] = rep["profit_before"]
        return rep

    # ---- apply: frequencies / vessels of the dropped services, the re-routed flows ----------
    comp = dict(sol.objective_components)
    for si in dropped:
        fr0 = int(sol.frequencies.get(si, 0))
        n0 = int(sol.vessels.get(si, models[si].vessels(fr0)))
        comp["vessel_cost"] = comp.get("vessel_cost", 0.0) - n0 * models[si].vessel_week_cost
        comp["fuel_cost"] = comp.get("fuel_cost", 0.0) - fr0 * models[si].fuel_cost_per_rotation
        comp["port_fixed_cost"] = comp.get("port_fixed_cost", 0.0) - fr0 * models[si].port_fixed_per_rotation
        sol.frequencies[si] = 0
        sol.vessels[si] = 0
    new_flows: List[Tuple[int, int, float]] = []
    served_by_od: Dict[int, float] = defaultdict(float)
    for di, p, k, val in cur_rows_spec:
        if k is None:
            paths.setdefault(di, [])
            paths[di].append(p)
            k = len(paths[di]) - 1
        new_flows.append((di, k, val))
        served_by_od[di] += val
    revenue = sum(demands[di].revenue_per_teu * t for di, _k, t in new_flows)
    port = sum(paths[di][k].port_cost_per_teu * t for di, k, t in new_flows)
    comp["revenue"], comp["per_teu_port_cost"] = revenue, port
    sol.objective_value = (revenue - port - comp.get("vessel_cost", 0.0) - comp.get("fuel_cost", 0.0)
                           - comp.get("port_fixed_cost", 0.0) - comp.get("unserved_penalty", 0.0))
    sol.objective_components = comp
    sol.flows = sorted(new_flows)
    sol.unserved = {di: max(0.0, float(demands[di].weekly_teu) - served_by_od.get(di, 0.0))
                    for di in sol.unserved}
    rep.update(applied=True, dropped=[models[si].service_id for si in dropped], profit_after=cur_profit,
               served_teu_after=float(sum(t for _, _, t in new_flows)),
               reason=("services switched off until the approved profit floor was met"
                       if cur_profit >= floor_usd
                       else "services switched off; profit improved but is still below the floor"))
    return rep
