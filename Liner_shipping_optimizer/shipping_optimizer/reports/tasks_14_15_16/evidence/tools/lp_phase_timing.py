"""Time the phases of the production global solve on one seed's pool (WorldSmall only).

usage: python -I lp_phase_timing.py <tree_root> <seed> <out.json>

Reports: model + path construction time, LP relaxation time and value, LP support size,
number of services carrying LP flow, how the LP's fractional frequencies are distributed
(how many support services have f < 1 in the relaxation), then the time to the FIRST integer
incumbent of the restricted problem (CBC, 120 s cap).
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT, SEED, OUT = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(ROOT))
os.environ["T15_POOL_ONLY"] = "1"
import runpy                                                                  # noqa: E402

import pulp                                                                   # noqa: E402

TOOLS = Path(__file__).resolve().parent
# reuse the harness definitions without running its main part: import by exec of the head
src = (TOOLS / "global_stage_experiment.py").read_text(encoding="utf-8")
head = src.split("# ----------------------------------------------------------------------------- main")[0]
sys.argv = [sys.argv[0], str(ROOT), str(OUT), str(SEED), "120"]
ns = {"__file__": str(TOOLS / "global_stage_experiment.py"), "__name__": "harness_head"}
exec(compile(head, "global_stage_experiment_head", "exec"), ns)

import src.network.network_milp as nm                                         # noqa: E402
from src.network.economics import assumptions_for_problem                     # noqa: E402
from src.network.paths import build_paths                                     # noqa: E402
from src.network.plan import NetworkPlanner                                   # noqa: E402
from src.network.reconcile import collect_candidates                          # noqa: E402

built = ns["build_pools"](SEED)
problem = ns["fresh_problem"]()
cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in built["pools"].items()})
planner = NetworkPlanner(problem, assumptions=assumptions_for_problem(problem))
t0 = time.perf_counter()
models, rejected = planner.build_models(cands)
t_models = time.perf_counter() - t0
t0 = time.perf_counter()
paths, pstats = build_paths(problem.demands, models, planner.port_lookup, planner.assumptions)
t_paths = time.perf_counter() - t0
limits = {c.vessel_class: c.quantity for c in problem.fleet.classes}
referenced = sorted({s for pl in paths.values() for p in pl for s in p.services})

res = {"seed": SEED, "candidates": len(cands), "modelled": len(models), "rejected": len(rejected),
       "referenced": len(referenced), "paths": sum(len(v) for v in paths.values()),
       "model_build_sec": round(t_models, 1), "path_build_sec": round(t_paths, 1)}

kw = dict(penalty=0.0, fixed=None, max_departures_cap=None, threads=None, total_vessel_limit=None,
          port_capacity=None, min_served_fraction=None)
t0 = time.perf_counter()
lp = nm._build_and_solve(models, problem.demands, paths, limits, referenced, integer=False,
                         initial=None, time_limit_sec=60.0, **kw)
res["lp_sec"] = round(time.perf_counter() - t0, 1)
res["lp_status"] = pulp.LpStatus.get(lp["prob"].status)
res["lp_objective"] = float(pulp.value(lp["prob"].objective) or 0.0)
fv = {si: (lp["f"][si].varValue or 0.0) for si in lp["active"]}
support = [si for si, v in fv.items() if v > 1e-6]
res["lp_active_services"] = len(lp["active"])
res["lp_support"] = len(support)
res["lp_support_f_lt_1"] = sum(1 for si in support if fv[si] < 1.0 - 1e-6)
res["lp_support_f_lt_0.5"] = sum(1 for si in support if fv[si] < 0.5)
res["lp_support_class"] = dict(Counter(models[si].vessel_class for si in support))
res["lp_total_vessels_fractional"] = sum((lp["n"][si].varValue or 0.0) for si in support)
res["lp_vessels_by_class"] = {}
for si in support:
    c = models[si].vessel_class
    res["lp_vessels_by_class"][c] = res["lp_vessels_by_class"].get(c, 0.0) + (lp["n"][si].varValue or 0.0)
res["fleet_by_class"] = limits

# integer solve on the LP support: wall time of the whole solve, status
t0 = time.perf_counter()
it = nm._build_and_solve(models, problem.demands, paths, limits, support, integer=True,
                         initial=None, time_limit_sec=100.0, **kw)
res["int_sec"] = round(time.perf_counter() - t0, 1)
res["int_pulp_status"] = pulp.LpStatus.get(it["prob"].status)
res["int_sol_status"] = int(getattr(it["prob"], "sol_status", -1))
res["int_objective"] = float(pulp.value(it["prob"].objective) or 0.0) if it["prob"].status == pulp.LpStatusOptimal else None
OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps(res, indent=1))
