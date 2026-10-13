"""Does the LP-guided restriction lose the services of the proven optimum?  (Task 15, strategy A)

usage: python -I support_vs_optimum.py <tree_root> <seed> <optimum_json> <out.json>

Rebuilds the seed's production pool (deterministic), solves the LP relaxation exactly as the
production solver does, and compares its support with the services operated in the proven
optimum (``optimum_json`` = a ``global_stage_experiment.py`` output with a ``highs`` run).
Reports, for every optimum service: in the LP support or not, its LP frequency, its rank by LP
revenue, its stand-alone profit, class and number of ports.
"""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT, SEED, OPT, OUT = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
sys.path.insert(0, str(ROOT))
TOOLS = Path(__file__).resolve().parent
src = (TOOLS / "global_stage_experiment.py").read_text(encoding="utf-8")
head = src.split("# ----------------------------------------------------------------------------- main")[0]
sys.argv = [sys.argv[0], str(ROOT), str(OUT), str(SEED), "120"]
ns = {"__file__": str(TOOLS / "global_stage_experiment.py"), "__name__": "harness_head"}
exec(compile(head, "global_stage_experiment_head", "exec"), ns)

import pulp                                                                   # noqa: E402

import src.network.network_milp as nm                                         # noqa: E402
from src.network.economics import assumptions_for_problem                     # noqa: E402
from src.network.paths import build_paths                                     # noqa: E402
from src.network.plan import NetworkPlanner                                   # noqa: E402
from src.network.reconcile import collect_candidates                          # noqa: E402

built = ns["build_pools"](SEED)
problem = ns["fresh_problem"]()
cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in built["pools"].items()})
planner = NetworkPlanner(problem, assumptions=assumptions_for_problem(problem))
models, _ = planner.build_models(cands)
paths, _ = build_paths(problem.demands, models, planner.port_lookup, planner.assumptions)
limits = {c.vessel_class: c.quantity for c in problem.fleet.classes}
referenced = sorted({s for pl in paths.values() for p in pl for s in p.services})
kw = dict(penalty=0.0, fixed=None, max_departures_cap=None, threads=None, total_vessel_limit=None,
          port_capacity=None, min_served_fraction=None)
lp = nm._build_and_solve(models, problem.demands, paths, limits, referenced, integer=False,
                         initial=None, time_limit_sec=60.0, **kw)
f_lp = {models[si].service_id: (lp["f"][si].varValue or 0.0) for si in lp["active"]}
value = defaultdict(float)
for (di, k), v in lp["q"].items():
    qv = v.varValue or 0.0
    if qv > 1e-9:
        pth = paths[di][k]
        for si in set(pth.services):
            value[models[si].service_id] += qv * problem.demands[di].revenue_per_teu / max(1, len(set(pth.services)))
ranked = sorted((sid for sid, v in f_lp.items() if v > 1e-6), key=lambda s: (-value[s], s))
rank = {sid: i + 1 for i, sid in enumerate(ranked)}
sa = ns["_standalone_profit"](models, problem.demands)
sa_by_id = {models[si].service_id: v for si, v in sa.items()}
cls_by_id = {m.service_id: m.vessel_class for m in models}
ports_by_id = {m.service_id: len(m.ports) for m in models}

opt = json.loads(OPT.read_text(encoding="utf-8"))
sel = next(r for r in opt["runs"] if r["strategy"] == "highs")["selected"]
rows = []
for s in sel:
    sid = s["id"]
    rows.append({"id": sid, "class": cls_by_id.get(sid), "n_ports": ports_by_id.get(sid),
                 "f_in_optimum": s["f"], "in_lp_support": f_lp.get(sid, 0.0) > 1e-6,
                 "lp_frequency": f_lp.get(sid, 0.0), "lp_revenue_rank": rank.get(sid),
                 "standalone_profit": sa_by_id.get(sid), "revenue": s["revenue"]})
res = {"seed": SEED, "candidates": len(cands), "lp_support": len(ranked),
       "optimum_services": len(rows),
       "optimum_services_outside_support": sum(1 for r in rows if not r["in_lp_support"]),
       "optimum_services_in_top120": sum(1 for r in rows if (r["lp_revenue_rank"] or 10**9) <= 120),
       "optimum_services_in_top60": sum(1 for r in rows if (r["lp_revenue_rank"] or 10**9) <= 60),
       "optimum_revenue_outside_support": sum(r["revenue"] for r in rows if not r["in_lp_support"]),
       "optimum_revenue_total": sum(r["revenue"] for r in rows),
       "services": rows}
OUT.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k != "services"}, indent=1))
