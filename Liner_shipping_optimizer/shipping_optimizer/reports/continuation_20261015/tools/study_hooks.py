"""Post-solve study hooks for the continuation experiments (diagnostics only; they never change a plan).

``T_STUDY=coverage``  multi-cause unserved-demand diagnosis and the targeted-path candidate overlay (Workstreams 5 and 7)
``T_STUDY=dual``      dual-priced network value of the rejected trunk / lane rotations vs the actual LP increment (Workstream 6)

The hooks run in the same process after the production global stage has returned, on the pool, the plan and the planner of
that run (captured by wrapping ``NetworkPlanner.plan`` and the trunk / lane generators; no source file is edited).
"""
from __future__ import annotations

import random
import time
from collections import Counter, defaultdict
from typing import Dict, List

CAP: Dict = {"planner": None, "cands": None, "rejected": []}


def install(rec) -> None:
    import src.network.plan as planmod

    orig_plan = planmod.NetworkPlanner.plan

    def plan_wrapper(self, candidates, *a, **k):
        CAP["planner"], CAP["cands"] = self, list(candidates)
        return orig_plan(self, candidates, *a, **k)
    planmod.NetworkPlanner.plan = plan_wrapper
    for attr in ("_augment_trunk", "_augment_lanes"):
        orig = getattr(rec, attr, None)
        if orig is None:
            continue

        def make(orig_):
            def wrapper(*a, **k):
                k.setdefault("collect_rejected", CAP["rejected"])
                return orig_(*a, **k)
            return wrapper
        setattr(rec, attr, make(orig))


def reset() -> None:
    CAP["planner"], CAP["cands"] = None, None
    CAP["rejected"] = []


# ---------------------------------------------------------------------------------------------------- coverage
def coverage_multicause(stage, problem) -> Dict:
    import dataclasses
    from src.network.paths import SELECT_FASTEST, BUDGET_FIXED, build_paths
    planner, plan = CAP["planner"], stage.plan
    if planner is None or plan is None or plan.solution is None or not plan.solution.usable:
        return {"available": False}
    t0 = time.perf_counter()
    models, demands, retained = plan.models, plan.demands, plan.paths
    sol, led = plan.solution, plan.ledger
    freq = {si: int(f) for si, f in sol.frequencies.items() if f > 0}
    leg_load: Dict = defaultdict(float)
    served: Dict[int, float] = defaultdict(float)
    for di, k, teu in sol.flows:
        if teu <= 1e-9:
            continue
        for seg in retained[di][k].segments:
            for leg in seg.legs:
                leg_load[(seg.service, leg)] += teu
        served[di] += teu
    inv = {c.vessel_class: int(c.quantity) for c in problem.fleet.classes}
    free = {c: inv[c] - int(led.vessels_by_class.get(c, 0)) for c in inv}
    cfg = dataclasses.replace(planner.path_config, selection=SELECT_FASTEST, budget=BUDGET_FIXED)
    full, _ = build_paths(demands, models, planner.port_lookup, planner.assumptions, max_paths_per_od=10 ** 9, config=cfg)
    total = sum(d.weekly_teu for d in demands if d.weekly_teu > 0)
    fleet_speeds = [float(c.design_speed) for c in problem.fleet.classes if c.design_speed]
    vmax = max(fleet_speeds) if fleet_speeds else None
    dm = planner.problem.distance_matrix
    combos: Dict[str, Dict] = defaultdict(lambda: {"ods": 0, "teu": 0.0})
    flag_totals = {k: {"ods": 0, "teu": 0.0} for k in ("operated_room_profitable", "operated_room_unprofitable", "operated_full",
                                                     "openable_with_free_fleet", "blocked_by_inventory", "no_valid_path_limit",
                                                     "no_valid_path_pool", "any_path_excluded_by_cap")}
    overlay = []
    contradictions = 0
    for di, d in enumerate(demands):
        if not d.weekly_teu > 0:
            continue
        rem = d.weekly_teu - served.get(di, 0.0)
        if rem <= 1e-6 * max(1.0, d.weekly_teu):
            continue
        valid = full.get(di, [])
        fl = set()
        if not valid:
            lim = getattr(d, "max_transit_days", None)
            nm_ = (dm.get(d.origin) or {}).get(d.destination)
            if lim is not None and vmax and isinstance(nm_, (int, float)) and nm_ > 0 and nm_ / (vmax * 24.0) > lim + 1e-9:
                fl.add("no_valid_path_limit")
            else:
                fl.add("no_valid_path_pool")
        keys_ret = {(p.services, p.transfer_ports) for p in retained.get(di, ())}
        excluded = [p for p in valid if (p.services, p.transfer_ports) not in keys_ret]
        if excluded:
            fl.add("any_path_excluded_by_cap")
        best_excl = None                       # (potential per TEU, kind) among excluded paths with a chance
        for p in valid:
            ops = [s.service for s in p.segments]
            in_ret = (p.services, p.transfer_ports) in keys_ret
            margin = float(d.revenue_per_teu) - float(p.port_cost_per_teu)
            if all(s in freq for s in ops):
                resid = min((models[s.service].capacity_teu * freq[s.service] - leg_load.get((s.service, leg), 0.0))
                            for s in p.segments for leg in s.legs)
                if resid > 1e-6 * max(1.0, rem):
                    kind = "operated_room_profitable" if margin > 1e-9 else "operated_room_unprofitable"
                    if kind == "operated_room_profitable" and not in_ret:
                        contradictions += 1       # flow re-optimisation should have used it
                else:
                    kind = "operated_full"
            else:
                need = defaultdict(int)
                for s in ops:
                    if s not in freq:
                        need[models[s].vessel_class] += models[s].vessels(1)
                kind = "openable_with_free_fleet" if all(free.get(c, 0) >= n for c, n in need.items()) else "blocked_by_inventory"
            fl.add(kind)
            if not in_ret and kind in ("openable_with_free_fleet", "operated_room_profitable", "operated_full") and margin > 0:
                if best_excl is None or margin > best_excl[0]:
                    best_excl = (margin, kind)
        combo = "+".join(sorted(fl - {"any_path_excluded_by_cap"})) or "none"
        if "any_path_excluded_by_cap" in fl:
            combo += " | excluded-by-cap"
        combos[combo]["ods"] += 1
        combos[combo]["teu"] += rem
        for f_ in fl:
            flag_totals[f_]["ods"] += 1
            flag_totals[f_]["teu"] += rem
        if best_excl is not None:
            overlay.append({"od": di, "origin": d.origin, "destination": d.destination, "unserved_teu": rem,
                            "best_excluded_margin_usd_per_teu": best_excl[0], "kind": best_excl[1],
                            "plausible_value_usd_per_week": best_excl[0] * rem, "n_excluded": len(excluded)})
    overlay.sort(key=lambda r: -r["plausible_value_usd_per_week"])
    unserved_total = sum(v["teu"] for v in combos.values())
    for v in list(combos.values()) + list(flag_totals.values()):
        v["share_of_total_demand_pct"] = 100.0 * v["teu"] / total if total else 0.0
    return {"available": True, "sec": round(time.perf_counter() - t0, 1), "total_demand_teu": total, "unserved_teu": unserved_total,
            "unserved_pct": 100.0 * unserved_total / total if total else 0.0,
            "flags_not_exclusive": flag_totals, "exclusive_combinations": dict(sorted(combos.items(), key=lambda kv: -kv[1]["teu"])),
            "contradictions_reopt_should_have_used_path": contradictions,
            "targeted_overlay": {"ods": len(overlay), "plausible_value_usd_per_week_sum": sum(r["plausible_value_usd_per_week"] for r in overlay),
                                 "top": overlay[:40]},
            "free_vessels": free}


# ---------------------------------------------------------------------------------------------------- dual study
def dual_study(stage, problem, n_dual=5, n_standalone=5, n_random=5, seed=0) -> Dict:
    from src.network.dual_screen import BaseLp, actual_incremental_bound, price_candidate
    from src.network.plan import Candidate
    from src.services.demand_coherent import _canonical
    planner, cands = CAP["planner"], CAP["cands"]
    if planner is None or not cands:
        return {"available": False}
    t0 = time.perf_counter()
    existing = {(_canonical(c.ports), c.vessel_class) for c in cands}
    seen, rej = set(), []
    for r in CAP["rejected"]:
        key = (_canonical(r["ports"]), r["vessel_class"])
        if key in existing or key in seen:
            continue
        seen.add(key)
        rej.append(r)
    base = BaseLp(planner, cands)
    out: Dict = {"available": base.ok, "pool": len(cands), "rejected_distinct": len(rej), "base_lp_sec": round(base.lp_sec, 1),
                 "base_bound_usd_per_week": base.bound, "operated_in_lp": len(base.operated),
                 "dual_demand_positive": sum(1 for v in base.duals["dem"].values() if v > 1e-9),
                 "fleet_duals_usd_per_vessel": {c: round(v, 2) for c, v in sorted(base.fleet.items())}}
    if not base.ok or not rej:
        return out
    priced = []
    for i, r in enumerate(rej):
        c = Candidate(f"rj{i:04d}", tuple(r["ports"]), r["vessel_class"])
        p = price_candidate(base, c)
        p["standalone_usd_per_week"] = r["standalone"]
        p["source"] = r.get("source")
        priced.append((c, p))
    out["priced"] = len(priced)
    out["priced_positive"] = sum(1 for _c, p in priced if (p["value_usd_per_week"] or 0.0) > 0.0)
    by_dual = sorted(priced, key=lambda cp: -(cp[1]["value_usd_per_week"] or -1e18))
    by_sa = sorted(priced, key=lambda cp: -cp[1]["standalone_usd_per_week"])
    rng = random.Random(seed)
    pool = list(priced)
    rng.shuffle(pool)
    chosen: Dict[str, tuple] = {}
    for tag, lst, n in (("dual_top", by_dual, n_dual), ("standalone_top", by_sa, n_standalone), ("random", pool, n_random)):
        for c, p in lst[:n]:
            chosen.setdefault(c.service_id, (c, p, []))[2].append(tag)
    rows = []
    for sid, (c, p, tags) in chosen.items():
        act = actual_incremental_bound(base, cands, c)
        rows.append({**p, "selected_by": tags, "actual_delta_bound_usd_per_week": act.get("delta_bound_usd_per_week"),
                     "actual_f_lp": act.get("candidate_f_lp")})
    out["evaluated"] = rows
    out["all_priced"] = [{"id": c.service_id, "class": c.vessel_class, "ports": list(c.ports), "standalone": p["standalone_usd_per_week"],
                          "dual_value": p["value_usd_per_week"], "transfer_paths_used": p.get("transfer_paths_used")} for c, p in priced]
    out["sec"] = round(time.perf_counter() - t0, 1)
    return out


def run(kind: str, stage, problem) -> Dict:
    if kind == "coverage":
        return coverage_multicause(stage, problem)
    if kind == "dual":
        return dual_study(stage, problem)
    raise ValueError(f"unknown T_STUDY {kind!r}")
