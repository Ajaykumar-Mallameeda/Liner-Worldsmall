"""D-07 read-only feasibility study: value of a fortnightly (sub-weekly) frequency option.  NO production change.

For one seed the production candidate pool (after the regional filter) is modelled twice with the production
service model, solved as the UNRESTRICTED integer problem with HiGHS (VUB inequality on, same limit):

  W  weekly frequencies only (production)
  F  every candidate gets a fortnightly TWIN: one departure every 14 days
        capacity per leg per week  = capacity / 2          (half a vessel-load per week)
        fuel and port/canal fixed  = rotation cost / 2     (one rotation per fortnight)
        vessels                    = ceil(T / 14)          (the twin's cycle is modelled as T / 2 for the
                                                            ``ceil(cycle x f / 7)`` relation with f integer)
     twin and weekly service may be combined (1.5 departures per week); transfer wait is NOT doubled for twins
     (optimistic for connections; stated limitation).

Reported: objective, HiGHS dual bound and gap (both models), operated twins, cargo on twins, vessels.
usage: fortnightly_study.py <tree_root> <seed> <out.json> [time_limit_sec]
"""
import dataclasses
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
TL = float(sys.argv[4]) if len(sys.argv) > 4 else 240.0

import pulp                                                              # noqa: E402

import src.network.network_milp as nm                                    # noqa: E402
from src.agents.regional_agent import RegionalAgent                      # noqa: E402
from src.agents.service_generator_agent import ServiceGeneratorAgent     # noqa: E402
from src.data.network_loader import NetworkLoader                        # noqa: E402
from src.decomposition.port_clustering import PortClustering             # noqa: E402
from src.decomposition.regional_splitter import RegionalSplitter         # noqa: E402
from src.network.paths import build_paths                                # noqa: E402
from src.network.plan import NetworkPlanner                              # noqa: E402
from src.network.reconcile import collect_candidates                     # noqa: E402
from src.optimization.adaptive_budget import AdaptiveBudget, compute_complexity_signals  # noqa: E402
from src.optimization.data import Problem                                # noqa: E402

REGIONS = ["Asia", "Europe", "Americas"]
full = NetworkLoader().load_problem()
dist = full.distance_matrix
for p in full.ports:
    dist.setdefault(p.id, {})
base = Problem(ports=full.ports, services=[], demands=full.demands, distance_matrix=dist, fleet=full.fleet)
clusters = PortClustering(n_clusters=3).cluster_ports(base.ports)
regional = RegionalSplitter(base).split(clusters)
pools = {}
for idx, (ci, rp) in enumerate(sorted(regional.items())):
    region = REGIONS[idx]
    random.seed(SEED * 100 + idx)
    services = ServiceGeneratorAgent(name=f"svc_gen_{region}", model="none").generate_services(rp, archetype_params=None)
    prefix = region.lower()
    for i, s in enumerate(services):
        s.id = f"{prefix}_svc_{i:03d}"
    rp.services = services
    sig = compute_complexity_signals(num_ports=len(rp.ports), demands=rp.demands, fleet=rp.fleet)
    rp = RegionalAgent(f"regional_{prefix}", region, "none")._filter_services(rp, AdaptiveBudget.from_signals(sig))
    pools[region] = [{"id": str(s.id), "ports": list(s.ports), "vessel_class": s.vessel_class} for s in rp.services]
cands, _ = collect_candidates(pools)
planner = NetworkPlanner(Problem(ports=full.ports, services=[], demands=full.demands, distance_matrix=dist, fleet=full.fleet))
models0, rejected = planner.build_models(cands)
total_dem = sum(d.weekly_teu for d in full.demands)
limits = {c.vessel_class: int(c.quantity) for c in full.fleet.classes}


def twin(m):
    return dataclasses.replace(
        m, service_id=m.service_id + "_bw", capacity_teu=m.capacity_teu / 2.0,
        fuel_cost_per_rotation=m.fuel_cost_per_rotation / 2.0, fuel_tonnes_per_rotation=m.fuel_tonnes_per_rotation / 2.0,
        port_fixed_per_rotation=m.port_fixed_per_rotation / 2.0, canal_fee_per_rotation=m.canal_fee_per_rotation / 2.0,
        cycle_time_days=m.cycle_time_days / 2.0)


def solve(models):
    paths, _ = build_paths(full.demands, models, planner.port_lookup, planner.assumptions, max_paths_per_od=10,
                           config=planner.path_config)
    t0 = time.perf_counter()
    res = nm._build_and_solve(models, full.demands, paths, limits, list(range(len(models))), integer=True, penalty=0.0,
                              fixed=None, initial=None, max_departures_cap=None, time_limit_sec=TL, threads=None,
                              solve=False, vub=True)
    info = nm._solve_highs(res, time.perf_counter() + TL)
    prob = res["prob"]
    ok = prob.status == pulp.LpStatusOptimal
    out = {"models": len(models), "paths": sum(len(v) for v in paths.values()), "highs_message": info.get("message"),
           "mip_gap": info.get("mip_gap"), "dual_bound_usd_wk": info.get("dual_bound"), "solved": bool(ok),
           "sec": round(time.perf_counter() - t0, 1)}
    if ok:
        out["objective_usd_wk"] = float(pulp.value(prob.objective))
        served = sum(float(v.varValue or 0.0) for v in res["q"].values())
        out["served_teu"] = served
        out["coverage_pct"] = round(100 * served / total_dem, 2)
        ops = {}
        twin_flow = 0.0
        twin_idx = {si for si in res["active"] if models[si].service_id.endswith("_bw")}
        for si in res["active"]:
            fv = round(res["f"][si].varValue or 0.0)
            if fv > 0:
                ops[models[si].service_id] = int(fv)
        for (di, k), v in res["q"].items():
            val = float(v.varValue or 0.0)
            if val > 1e-6 and any(s in twin_idx for s in paths[di][k].services):
                twin_flow += val
        out["services_operated"] = len(ops)
        out["twins_operated"] = sum(1 for s in ops if s.endswith("_bw"))
        out["cargo_on_paths_using_a_twin_teu"] = twin_flow
        out["vessels"] = sum(models[si].vessels(int(round(res["f"][si].varValue or 0.0))) if not
                             models[si].service_id.endswith("_bw") else
                             -(-int(round(res["f"][si].varValue or 0.0)) * models[si].cycle_time_days // 7)
                             for si in res["active"] if (res["f"][si].varValue or 0.0) > 0.5)
    return out


rep = {"seed": SEED, "time_limit_sec": TL, "pool_candidates": len(cands), "modelled": len(models0)}
rep["W_weekly_only"] = solve(models0)
OUT.write_text(json.dumps(rep, indent=1), encoding="utf-8")
rep["F_with_fortnightly_twins"] = solve(models0 + [twin(m) for m in models0])
OUT.write_text(json.dumps(rep, indent=1), encoding="utf-8")
w, f = rep["W_weekly_only"], rep["F_with_fortnightly_twins"]
if w.get("solved") and f.get("solved"):
    rep["delta_objective_usd_wk"] = f["objective_usd_wk"] - w["objective_usd_wk"]
    rep["delta_coverage_pp"] = f["coverage_pct"] - w["coverage_pct"]
OUT.write_text(json.dumps(rep, indent=1), encoding="utf-8")
print(json.dumps({k: rep[k] for k in rep if k.startswith(("delta", "W_", "F_"))}, indent=1))
