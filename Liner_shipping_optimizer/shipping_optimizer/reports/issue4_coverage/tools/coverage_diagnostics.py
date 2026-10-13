"""Issue 4 - read-only coverage diagnostics (WorldSmall, production code, no model change).

For one generator seed: rebuild the production candidate pool (regional generation, then the production
regional filter) and measure, with the LP relaxation of the production network model (variable-upper-bound
inequality on, so the relaxation is as tight as the integer problem allows), what each upstream restriction
costs:

  A  production           pool after the regional filter, per-OD cap 10
  B  cap lifted           same pool, every valid path of every OD
  C  filter lifted        pool BEFORE the regional filter, cap 10
  D  both lifted          pool before the filter, every valid path
  E  class screening off  every feasible class of every rotation offered (LINER_CLASS_SCREEN=all), filter on, cap 10
  F  inventory lifted     production pool and cap, class inventories x100
  H  all lifted           pool before filter + all classes + all paths + inventories x100

An LP value is an UPPER bound of operating profit with fractional frequencies and vessels - it measures the
value of the removed restriction to the relaxation, it is not an achievable plan.  Served TEU at the LP optimum
is reported with it.  Nothing is written to the tree; one JSON is produced.

usage: python coverage_diagnostics.py <tree_root> <seed> <out.json> [scenario letters, default ABCDEFH]
"""
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))
SEED = int(sys.argv[2])
OUT = Path(sys.argv[3])
WANT = sys.argv[4] if len(sys.argv) > 4 else "ABCDEFH"

import pulp                                                              # noqa: E402

import src.network.network_milp as nm                                    # noqa: E402
from src.agents.regional_agent import RegionalAgent                      # noqa: E402
from src.agents.service_generator_agent import ServiceGeneratorAgent     # noqa: E402
from src.data.network_loader import NetworkLoader                        # noqa: E402
from src.decomposition.port_clustering import PortClustering             # noqa: E402
from src.decomposition.regional_splitter import RegionalSplitter         # noqa: E402
from src.network.paths import build_paths                                # noqa: E402
from src.network.plan import Candidate, NetworkPlanner                   # noqa: E402
from src.network.reconcile import collect_candidates                     # noqa: E402
from src.optimization.adaptive_budget import AdaptiveBudget, compute_complexity_signals  # noqa: E402
from src.optimization.data import Problem                                # noqa: E402

REGIONS = ["Asia", "Europe", "Americas"]
_ld = NetworkLoader()
_full = _ld.load_problem()
_dist = _full.distance_matrix
for _p in _full.ports:
    _dist.setdefault(_p.id, {})


def fresh() -> Problem:
    return Problem(ports=_full.ports, services=[], demands=_full.demands, distance_matrix=_dist, fleet=_full.fleet)


def pools_for(seed: int, env: dict):
    """(pre-filter pools, post-filter pools) per region, as lists of dicts, under ``env``."""
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        base = fresh()
        clusters = PortClustering(n_clusters=3).cluster_ports(base.ports)
        regional = RegionalSplitter(base).split(clusters)
        pre, post = {}, {}
        for idx, (ci, rp) in enumerate(sorted(regional.items())):
            region = REGIONS[idx]
            random.seed(seed * 100 + idx)
            agent = ServiceGeneratorAgent(name=f"svc_gen_{region}", model="none")
            services = agent.generate_services(rp, archetype_params=None)
            prefix = region.lower().replace(" ", "_")
            for i, s in enumerate(services):
                s.id = f"{prefix}_svc_{i:03d}"
            rp.services = services
            pre[region] = [{"id": str(s.id), "ports": list(s.ports), "vessel_class": s.vessel_class,
                            "section": getattr(s, "origin_section", "unknown")} for s in services]
            sig = compute_complexity_signals(num_ports=len(rp.ports), demands=rp.demands, fleet=rp.fleet)
            budget = AdaptiveBudget.from_signals(sig)
            ra = RegionalAgent(f"regional_{prefix}", region, "none")
            rp = ra._filter_services(rp, budget)
            post[region] = [{"id": str(s.id), "ports": list(s.ports), "vessel_class": s.vessel_class,
                             "section": getattr(s, "origin_section", "unknown")} for s in rp.services]
        return pre, post
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def lp_value(pool, cap, inventory_mult=1, env=None):
    saved = {k: os.environ.get(k) for k in (env or {})}
    os.environ.update(env or {})
    try:
        return _lp_value(pool, cap, inventory_mult)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _lp_value(pool, cap, inventory_mult=1):
    t0 = time.perf_counter()
    cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in pool.items()})
    pr = fresh()
    planner = NetworkPlanner(pr)
    models, rejected = planner.build_models(cands)
    t_models = time.perf_counter() - t0
    paths, stats = build_paths(pr.demands, models, planner.port_lookup, planner.assumptions,
                               max_paths_per_od=cap, config=planner.path_config)
    t_paths = time.perf_counter() - t0 - t_models
    limits = {c.vessel_class: int(c.quantity) * inventory_mult for c in pr.fleet.classes}
    # the LP is solved with HiGHS (scipy.optimize.milp, all-continuous): CBC reports a time-limited,
    # non-optimal LP as "Optimal" (seen on the 53k-path model: served TEU > demand), HiGHS reports its status.
    res = nm._build_and_solve(models, pr.demands, paths, limits, list(range(len(models))), integer=False,
                              penalty=0.0, fixed=None, initial=None, max_departures_cap=None,
                              time_limit_sec=900.0, threads=None, solve=False, vub=True)
    info = nm._solve_highs(res, time.perf_counter() + 3000.0)
    prob = res["prob"]
    proven = getattr(prob, "sol_status", None) == pulp.LpSolutionOptimal
    ok = (not info["error"]) and prob.status == pulp.LpStatusOptimal and proven
    val = float(pulp.value(prob.objective)) if ok else None
    served = sum(float(v.varValue or 0.0) for v in res["q"].values()) if ok else None
    total = sum(d.weekly_teu for d in pr.demands)
    ods_with_path = sum(1 for di in range(len(pr.demands)) if paths.get(di))
    dem_with_path = sum(d.weekly_teu for di, d in enumerate(pr.demands) if paths.get(di))
    classes = Counter(m.vessel_class for m in models)
    ops = {}
    if ok:
        for si in res["active"]:
            fv = res["f"][si].varValue or 0.0
            if fv > 1e-6:
                ops[models[si].vessel_class] = ops.get(models[si].vessel_class, 0.0) + float(fv)
    return {"candidates": len(cands), "models": len(models), "rejected": len(rejected), "paths_in_model": sum(len(v) for v in paths.values()),
            "ods_with_a_path": ods_with_path, "demand_with_a_path_pct": round(100 * dem_with_path / total, 2),
            "lp_status": pulp.LpStatus.get(prob.status), "lp_proven_optimal": bool(proven), "highs_message": info.get("message"), "lp_profit_usd_wk": val,
            "lp_served_teu": served, "lp_coverage_pct": round(100 * served / total, 2) if served is not None else None,
            "models_by_class": dict(classes), "lp_departures_by_class": {k: round(v, 1) for k, v in ops.items()},
            "sec_models": round(t_models, 1), "sec_paths": round(t_paths, 1), "sec_total": round(time.perf_counter() - t0, 1)}


out = {"seed": SEED, "tree": str(ROOT), "scenarios": {}}
t_all = time.perf_counter()
pre, post = pools_for(SEED, {})
out["pool"] = {"pre_filter": {k: len(v) for k, v in pre.items()}, "post_filter": {k: len(v) for k, v in post.items()},
               "post_by_class": dict(Counter(c["vessel_class"] for v in post.values() for c in v)),
               "pre_by_class": dict(Counter(c["vessel_class"] for v in pre.values() for c in v)),
               "post_by_section": dict(Counter(c["section"] for v in post.values() for c in v))}
BIG = 100000
runs = {"A": lambda: lp_value(post, 10), "B": lambda: lp_value(post, BIG), "C": lambda: lp_value(pre, 10),
        "D": lambda: lp_value(pre, BIG), "F": lambda: lp_value(post, 10, 100),
        "P": lambda: lp_value(post, 10, 1, {"LINER_PATH_SELECTION": "cost_aware"}),
        "Q": lambda: lp_value(post, 10, 1, {"LINER_PATH_SELECTION": "hybrid"}),
        "R": lambda: lp_value(post, 10, 1, {"LINER_PATH_BUDGET": "adaptive"}),
        "S": lambda: lp_value(post, 20)}
for k in WANT:
    t0 = time.perf_counter()
    if k in runs:
        out["scenarios"][k] = runs[k]()
    elif k in "EH":
        pre_all, post_all = pools_for(SEED, {"LINER_CLASS_SCREEN": "all"})
        out["pool"][f"{k}_pre_by_class"] = dict(Counter(c["vessel_class"] for v in pre_all.values() for c in v))
        out["pool"][f"{k}_post_by_class"] = dict(Counter(c["vessel_class"] for v in post_all.values() for c in v))
        out["scenarios"][k] = lp_value(post_all, 10) if k == "E" else lp_value(pre_all, BIG, 100)
    print(f"seed {SEED} scenario {k}: {out['scenarios'][k]['lp_profit_usd_wk']} cov {out['scenarios'][k]['lp_coverage_pct']} "
          f"models {out['scenarios'][k]['models']} paths {out['scenarios'][k]['paths_in_model']} ({time.perf_counter()-t0:.0f}s)", flush=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
out["wall_sec"] = round(time.perf_counter() - t_all, 1)
OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
