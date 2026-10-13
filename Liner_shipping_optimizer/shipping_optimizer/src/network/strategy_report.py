"""Strategy, utilisation and unserved-demand report of one verified network plan (Task 19).

Everything here is DERIVED from the final routed cargo of a ``PlanResult`` (the MILP solution
and the independent ledger); nothing is a preassigned quota and nothing feeds back into the
optimisation.  Each served OD cargo flow is counted once; each leg's utilisation is counted
once per leg.

Strategy of a flow (descriptive labels, not constraints)
    direct          the cargo rides one service (no transfer)
    feeder          one transfer, the two services sail on DIFFERENT capacity tiers: a smaller
                    vessel consolidates onto / distributes from a larger one
    hub_and_spoke   one transfer between services of the SAME capacity tier (relay at a hub)
    multi_hop       two transfers (three services; the model's hard bound)

Accounting of a strategy (USD / week)
    revenue         flow TEU x the OD's revenue per TEU                          (exact)
    port charges    flow TEU x the path's per-TEU port charges (origin + destination handling
                    and port-call charges, transshipment at every hub)               (exact)
    service cost    the weekly vessel hire + fuel + fixed port calls of a service are shared
                    by the cargo that occupies its capacity: share = TEU x ride days / (capacity
                    x frequency x cycle days).  The remainder is IDLE CAPACITY and is reported
                    on its own, so  sum(strategies) + idle  ==  the ledger's total, exactly.
    profit          revenue - port charges - allocated service cost; ``idle_capacity_cost`` is
                    negative on top of it.  The allocation is an attribution convention (the
                    ledger's totals are the authority).

Utilisation is measured at four levels with the capacity unit of the model (``capacity_teu``
= the fleet file's ``Capacity FFE`` x 2, converted once by the loader; status
``reference_code``):
    leg      load / (capacity x frequency) of every operated leg
    service  carried TEU-legs / offered TEU-legs of one service
    fleet    vessels used / class inventory, per class
    network  carried TEU-legs / offered TEU-legs (and the same weighted by nautical miles)

Unserved demand is classified by the first cause that applies to the OD's remainder:
    limit_below_fastest_sailing_time  no path: the OD's transit limit is shorter than the pure
                                      sailing time at the fastest class (no pool could serve it)
    no_time_feasible_service_in_pool  no path: attainable at some class speed, no pool candidate
    capacity_exhausted                a path of operated services exists and a leg is full
    not_profitable_to_carry           a path of operated services has room; revenue <= its
                                      per-TEU charges
    fleet_inventory_exhausted         every path needs a service that is not operated and whose
                                      class has too few free vessels to start it
    not_economic_to_open_service      some path could be opened with the free fleet; the
                                      optimiser judged it not worth its weekly cost
    unclassified_residual             operated path with room and positive margin (a time-limited
                                      incumbent gap; reported, never hidden)
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Optional

_EPS = 1e-6

STRATEGIES = ("direct", "feeder", "hub_and_spoke", "multi_hop")


def classify_flow(path, models) -> str:
    """Strategy label of a routed path (see the module docstring)."""
    n = len(path.segments) - 1
    if n <= 0:
        return "direct"
    if n >= 2:
        return "multi_hop"
    caps = {round(float(models[s.service].capacity_teu), 6) for s in path.segments}
    return "feeder" if len(caps) > 1 else "hub_and_spoke"


def _pct(sorted_vals: List[float], q: float) -> Optional[float]:
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, max(0, int(math.ceil(q * len(sorted_vals))) - 1))
    return sorted_vals[i]


def _wquantile(pairs, q):
    """TEU-weighted quantile of (value, weight) pairs."""
    pairs = sorted(pairs)
    tot = sum(w for _, w in pairs)
    if tot <= 0:
        return None
    acc, target = 0.0, q * tot
    for v, w in pairs:
        acc += w
        if acc >= target - 1e-12:
            return v
    return pairs[-1][0]


def build_strategy_report(plan, *, fleet=None, distance_matrix=None, speed_factor: float = 1.0) -> Dict:
    """Strategy / utilisation / unserved report of a usable, ledger-checked plan.  Never raises
    for a plan that has a solution; returns ``{"available": False, ...}`` otherwise."""
    sol, led = getattr(plan, "solution", None), getattr(plan, "ledger", None)
    if sol is None or led is None or not getattr(sol, "usable", False):
        return {"available": False, "reason": "no usable plan"}
    models, demands, paths = plan.models, plan.demands, plan.paths
    freq = {si: int(f) for si, f in sol.frequencies.items() if f > 0}
    sid = [m.service_id for m in models]

    # ---- flows -------------------------------------------------------------------
    S = {g: dict(flows=0, teu=0.0, revenue=0.0, port_charges=0.0, transfer_teu=0.0,
                 transit=[], slack=[], violations=0, by_class=defaultdict(float))
         for g in STRATEGIES}
    leg_load: Dict = defaultdict(float)
    slot_days_by_service: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    served_by_od: Dict[int, float] = defaultdict(float)
    n_flows = 0
    for di, k, teu in sol.flows:
        if teu <= _EPS:
            continue
        p = paths[di][k]
        d = demands[di]
        g = classify_flow(p, models)
        s = S[g]
        n_flows += 1
        s["flows"] += 1
        s["teu"] += teu
        s["revenue"] += teu * d.revenue_per_teu
        s["port_charges"] += teu * p.port_cost_per_teu
        s["transfer_teu"] += teu * (len(p.segments) - 1)
        for seg in p.segments:
            for leg in seg.legs:
                leg_load[(seg.service, leg)] += teu
            slot_days_by_service[seg.service][g] += teu * seg.ride_days
            s["by_class"][models[seg.service].vessel_class] += teu
        s["transit"].append((p.transit_days, teu))
        lim = getattr(d, "max_transit_days", None)
        if lim is not None:
            s["slack"].append(lim - p.transit_days)
            if p.transit_days > lim + 1e-9:
                s["violations"] += 1
        served_by_od[di] += teu

    # ---- service cost allocation ------------------------------------------------------
    svc_cost_total = 0.0
    alloc: Dict[str, float] = defaultdict(float)
    idle_cost = 0.0
    service_rows = []
    for si, f in freq.items():
        m = models[si]
        n_ves = m.vessels(f)                       # the ledger's (minimum) vessel count
        cost = n_ves * m.vessel_week_cost + f * m.fuel_cost_per_rotation + f * m.port_fixed_per_rotation
        svc_cost_total += cost
        cap_slot_days = m.capacity_teu * f * m.cycle_days
        used = sum(slot_days_by_service[si].values())
        share = min(1.0, used / cap_slot_days) if cap_slot_days > 0 else 0.0
        for g, sd in slot_days_by_service[si].items():
            alloc[g] += cost * (sd / cap_slot_days if cap_slot_days > 0 else 0.0)
        idle_cost += cost * (1.0 - share)
        offered = [m.capacity_teu * f] * len(m.legs)
        loads = [leg_load.get((si, l), 0.0) for l in range(len(m.legs))]
        service_rows.append({
            "service": m.service_id, "class": m.vessel_class, "frequency": f, "vessels": n_ves,
            "legs": len(m.legs), "capacity_per_leg": m.capacity_teu * f,
            "offered_teu_legs": sum(offered), "carried_teu_legs": sum(loads),
            "load_factor": (sum(loads) / sum(offered)) if sum(offered) > 0 else None,
            "min_leg_load_factor": min((l / o for l, o in zip(loads, offered) if o > 0), default=None),
            "max_leg_load_factor": max((l / o for l, o in zip(loads, offered) if o > 0), default=None),
            "idle_capacity_teu_legs": sum(offered) - sum(loads),
            "slot_time_utilisation": share, "weekly_cost": cost,
            "n_ports": len(m.ports), "ports": list(m.ports),
        })

    total_demand = float(led.total_demand_teu)
    served_total = sum(s["teu"] for s in S.values())
    by_strategy = {}
    for g in STRATEGIES:
        s = S[g]
        rev, pc, ac = s["revenue"], s["port_charges"], alloc.get(g, 0.0)
        tr = s["transit"]
        by_strategy[g] = {
            "flows": s["flows"],
            "served_teu": s["teu"],
            "share_of_served_teu": (s["teu"] / served_total) if served_total > 0 else 0.0,
            "coverage_contribution_pct": (100.0 * s["teu"] / total_demand) if total_demand > 0 else 0.0,
            "revenue": rev,
            "port_charges": pc,
            "allocated_service_cost": ac,
            "profit_contribution": rev - pc - ac,
            "transfers_per_teu": (s["transfer_teu"] / s["teu"]) if s["teu"] > 0 else 0.0,
            "transit_days_mean": (sum(v * w for v, w in tr) / s["teu"]) if s["teu"] > 0 else None,
            "transit_days_p50": _wquantile(tr, 0.5),
            "transit_days_p90": _wquantile(tr, 0.9),
            "transit_days_max": max((v for v, _ in tr), default=None),
            "min_slack_to_limit_days": min(s["slack"]) if s["slack"] else None,
            "transit_violations": s["violations"],
            "teu_by_vessel_class": dict(s["by_class"]),
        }

    # ---- reconciliation with the independent ledger ------------------------------------
    rev_all = sum(s["revenue"] for s in S.values())
    pc_all = sum(s["port_charges"] for s in S.values())
    ledger_port = led.handling_cost + led.transshipment_cost + led.port_variable_cost
    ledger_service = led.vessel_cost + led.fuel_cost + led.port_call_fixed_cost
    profit_sum = sum(b["profit_contribution"] for b in by_strategy.values()) - idle_cost

    def close(a, b, tol=1e-6):
        return abs(a - b) <= tol * max(1.0, abs(a), abs(b)) + 1e-3
    reconciliation = {
        "revenue_matches_ledger": close(rev_all, led.revenue),
        "port_charges_match_ledger": close(pc_all, ledger_port),
        "service_cost_matches_ledger": close(svc_cost_total, ledger_service),
        "profit_matches_ledger": close(profit_sum, led.operating_profit),
        "served_teu_matches_ledger": close(served_total, led.served_teu, 1e-6),
        "revenue": rev_all, "ledger_revenue": led.revenue,
        "port_charges": pc_all, "ledger_port_charges": ledger_port,
        "service_cost": svc_cost_total, "ledger_service_cost": ledger_service,
        "profit": profit_sum, "ledger_profit": led.operating_profit,
        "each_flow_counted_once": True,
    }
    reconciliation["all"] = all(reconciliation[k] for k in (
        "revenue_matches_ledger", "port_charges_match_ledger", "service_cost_matches_ledger",
        "profit_matches_ledger", "served_teu_matches_ledger"))

    # ---- utilisation ----------------------------------------------------------------------
    leg_lf = []
    offered_total = carried_total = 0.0
    offered_nm = carried_nm = 0.0
    for si, f in freq.items():
        m = models[si]
        cap = m.capacity_teu * f
        for l, (_a, _b, nm_) in enumerate(m.legs):
            load = leg_load.get((si, l), 0.0)
            leg_lf.append(load / cap if cap > 0 else 0.0)
            offered_total += cap
            carried_total += load
            offered_nm += cap * nm_
            carried_nm += load * nm_
    leg_sorted = sorted(leg_lf)
    fleet_rows = {}
    # EVERY class of the fleet counts in the denominator, also a class for which the candidate pool contains no
    # model (e.g. excluded by draft limits): the inventory is what the company owns, not what was modelled
    # (decision phase: the former per-model class list overstated the utilisation, 0.87 reported vs 0.68 of 263).
    owned = {c.vessel_class: int(c.quantity) for c in getattr(fleet, "classes", [])} if fleet is not None else {}
    for cname in sorted(set(owned) | {m.vessel_class for m in models}):
        inv = owned.get(cname)
        if inv is None:
            inv = next((m.class_inventory for m in models if m.vessel_class == cname), 0)
        used = int(led.vessels_by_class.get(cname, 0))
        fleet_rows[cname] = {"vessels_used": used, "inventory": int(inv),
                             "inventory_utilisation": (used / inv) if inv else None,
                             "services_operated": sum(1 for si in freq if models[si].vessel_class == cname)}
    used_total = sum(r["vessels_used"] for r in fleet_rows.values())
    inv_total = sum(r["inventory"] for r in fleet_rows.values())
    utilisation = {
        "capacity_unit": "TEU (fleet file 'Capacity FFE' is FFE, converted x2 once by the loader; status reference_code)",
        "leg": {"legs": len(leg_lf),
                "load_factor_mean": (sum(leg_lf) / len(leg_lf)) if leg_lf else None,
                "p10": _pct(leg_sorted, 0.10), "p50": _pct(leg_sorted, 0.50), "p90": _pct(leg_sorted, 0.90),
                "legs_at_or_above_95pct": sum(1 for x in leg_lf if x >= 0.95 - 1e-9),
                "legs_below_30pct": sum(1 for x in leg_lf if x < 0.30),
                "legs_empty": sum(1 for x in leg_lf if x <= _EPS)},
        "service": {"services": len(service_rows),
                    "load_factor_mean": (sum(r["load_factor"] for r in service_rows if r["load_factor"] is not None)
                                         / max(1, sum(1 for r in service_rows if r["load_factor"] is not None))),
                    "load_factor_min": min((r["load_factor"] for r in service_rows if r["load_factor"] is not None),
                                           default=None),
                    "load_factor_max": max((r["load_factor"] for r in service_rows if r["load_factor"] is not None),
                                           default=None)},
        "fleet": {"by_class": fleet_rows, "vessels_used": used_total, "inventory": inv_total,
                  "inventory_utilisation": (used_total / inv_total) if inv_total else None},
        "network": {"offered_teu_legs": offered_total, "carried_teu_legs": carried_total,
                    "idle_capacity_teu_legs": offered_total - carried_total,
                    "load_factor": (carried_total / offered_total) if offered_total > 0 else None,
                    "load_factor_nm_weighted": (carried_nm / offered_nm) if offered_nm > 0 else None,
                    "served_teu_per_vessel": (served_total / used_total) if used_total else None,
                    "profit_per_vessel": (led.operating_profit / used_total) if used_total else None},
    }

    # ---- coverage by OD ----------------------------------------------------------------------
    ods_full = ods_part = ods_none = 0
    unserved_by_reason: Dict[str, Dict[str, float]] = defaultdict(lambda: {"ods": 0, "teu": 0.0})
    vmax = None
    if fleet is not None:
        speeds = [float(c.design_speed) for c in getattr(fleet, "classes", ()) if c.design_speed]
        vmax = max(speeds) * speed_factor if speeds else None
    # spare vessels per class (free inventory) after the plan
    free = {c: fleet_rows[c]["inventory"] - fleet_rows[c]["vessels_used"] for c in fleet_rows}
    for di, d in enumerate(demands):
        if not d.weekly_teu > 0:
            continue
        got = served_by_od.get(di, 0.0)
        rem = d.weekly_teu - got
        if rem <= 1e-6 * max(1.0, d.weekly_teu):
            ods_full += 1
            continue
        if got > _EPS:
            ods_part += 1
        else:
            ods_none += 1
        reason = _unserved_reason(di, d, rem, paths, models, freq, leg_load, free, distance_matrix, vmax)
        unserved_by_reason[reason]["ods"] += 1
        unserved_by_reason[reason]["teu"] += rem
    for r in unserved_by_reason.values():
        r["share_of_total_demand_pct"] = (100.0 * r["teu"] / total_demand) if total_demand > 0 else 0.0

    n_trans = sum(S[g]["transfer_teu"] for g in STRATEGIES)
    return {
        "available": True,
        "definition": "strategies are the realised structure of the routed cargo, not quotas; "
                      "see src/network/strategy_report.py",
        "totals": {"flows": n_flows, "served_teu": served_total, "total_demand_teu": total_demand,
                   "coverage_pct": (100.0 * served_total / total_demand) if total_demand > 0 else 0.0,
                   "transfers_per_teu": (n_trans / served_total) if served_total > 0 else 0.0,
                   "service_cost": svc_cost_total, "idle_capacity_cost": idle_cost,
                   "operating_profit": led.operating_profit},
        "by_strategy": by_strategy,
        "reconciliation": reconciliation,
        "utilisation": utilisation,
        "coverage_by_od": {"fully_served": ods_full, "partially_served": ods_part, "unserved": ods_none,
                           "total": ods_full + ods_part + ods_none},
        "unserved_by_reason": {k: dict(v) for k, v in sorted(unserved_by_reason.items())},
        "services": sorted(service_rows, key=lambda r: r["service"]),
    }


def _unserved_reason(di, d, remainder, paths, models, freq, leg_load, free_vessels,
                     distance_matrix, vmax) -> str:
    plist = paths.get(di)
    if not plist:
        lim = getattr(d, "max_transit_days", None)
        if lim is not None and vmax and distance_matrix is not None:
            nm_ = (distance_matrix.get(d.origin) or {}).get(d.destination)
            if isinstance(nm_, (int, float)) and nm_ > 0 and nm_ / (vmax * 24.0) > lim + 1e-9:
                return "limit_below_fastest_sailing_time"
        return "no_time_feasible_service_in_pool"
    best = None                       # (kind, detail) of the most hopeful path
    openable = False
    for p in plist:
        ops = [s.service for s in p.segments]
        if all(s in freq for s in ops):
            # operated path: residual capacity on its legs
            resid = min((models[s.service].capacity_teu * freq[s.service]
                         - leg_load.get((s.service, leg), 0.0))
                        for s in p.segments for leg in s.legs)
            if resid > 1e-6 * max(1.0, remainder):
                if d.revenue_per_teu <= p.port_cost_per_teu + 1e-9:
                    best = best or "not_profitable_to_carry"
                else:
                    best = "unclassified_residual"
                    break
            else:
                best = best or "capacity_exhausted"
            continue
        need: Dict[str, int] = defaultdict(int)
        for s in ops:
            if s not in freq:
                need[models[s].vessel_class] += models[s].vessels(1)
        if all(free_vessels.get(c, 0) >= n for c, n in need.items()):
            openable = True
    if best == "unclassified_residual":
        return best
    if best is not None:
        return best
    return "not_economic_to_open_service" if openable else "fleet_inventory_exhausted"
