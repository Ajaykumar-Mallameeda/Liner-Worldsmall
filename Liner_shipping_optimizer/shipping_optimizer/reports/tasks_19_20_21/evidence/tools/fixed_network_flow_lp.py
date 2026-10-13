"""How much does the per-OD path cap cost, holding the NETWORK fixed?

Given the operated services and frequencies of a recorded run (a controlled-experiment output),
re-route the cargo over ALL valid time-feasible paths of the same pool: a pure LP in the flows
(no integer variable, no change of any frequency or vessel):

    max  sum_p (revenue_od - port_charges_p) q_p
    s.t. sum_p q_p <= demand_od                    (every OD at most once)
         sum_{p rides (s, leg)} q_p <= cap_s f_s   (every leg of every operated service)

The recorded plan is feasible in this LP, so the LP value is never lower than the recorded
operating profit; the difference is cargo the 10-fastest-paths rule kept out of reach of
capacity that was already paid for.  Diagnostic only (a production flow re-optimisation is
``src/network/plan.py``).

usage: python -I fixed_network_flow_lp.py <tree_root> <run_output.json> <out.json> [max_transfers]
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pool_tools as PT                                              # noqa: E402

ROOT, RUN, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
MAXT = int(sys.argv[4]) if len(sys.argv) > 4 else 1
PT.init(ROOT)

import numpy as np                                                   # noqa: E402
from scipy.optimize import linprog                                   # noqa: E402
from scipy.sparse import coo_matrix                                  # noqa: E402

from src.network.economics import assumptions_for_problem            # noqa: E402
from src.network.paths import PathConfig, build_paths                # noqa: E402
from src.network.plan import NetworkPlanner                          # noqa: E402
from src.network.reconcile import collect_candidates                 # noqa: E402

run = json.loads(RUN.read_text(encoding="utf-8"))
seed = int(run["seed"])
r = run["runs"][0]
operated = {s["id"]: int(s["f"]) for s in r["selected"]}
recorded = r["ledger"]

built = PT.build_pools(seed)
problem = PT.fresh_problem()
cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in built["pools"].items()})
a = assumptions_for_problem(problem)
pl = NetworkPlanner(problem, assumptions=a)
models, _ = pl.build_models(cands)
index = {m.service_id: i for i, m in enumerate(models)}
f = {index[s]: fr for s, fr in operated.items() if fr > 0 and s in index}
demands = list(problem.demands)
t0 = time.perf_counter()
paths, st = build_paths(demands, models, pl.port_lookup, a, max_paths_per_od=10 ** 9,
                        config=PathConfig(max_transfers=MAXT, multi_hop_min_alternatives=10 ** 9))
usable = []
for di, plist in paths.items():
    for p in plist:
        if all(s in f for s in p.services):
            usable.append((di, p))
cols = {}
rows_cap = {}
data, ri, ci = [], [], []
obj = []
for j, (di, p) in enumerate(usable):
    obj.append(-(demands[di].revenue_per_teu - p.port_cost_per_teu))
    for seg in p.segments:
        for leg in seg.legs:
            k = (seg.service, leg)
            if k not in rows_cap:
                rows_cap[k] = len(rows_cap)
            data.append(1.0)
            ri.append(rows_cap[k])
            ci.append(j)
n_cap = len(rows_cap)
od_row = {}
for j, (di, p) in enumerate(usable):
    if di not in od_row:
        od_row[di] = n_cap + len(od_row)
    data.append(1.0)
    ri.append(od_row[di])
    ci.append(j)
A = coo_matrix((data, (ri, ci)), shape=(n_cap + len(od_row), len(usable))).tocsr()
b = np.zeros(A.shape[0])
for (s, leg), i in rows_cap.items():
    b[i] = models[s].capacity_teu * f[s]
for di, i in od_row.items():
    b[i] = demands[di].weekly_teu
res = linprog(np.array(obj), A_ub=A, b_ub=b, bounds=(0, None), method="highs")
flows = res.x
margin = -res.fun
served = float(flows.sum())
fixed_cost = sum(models[s].weekly_fixed_cost(fr) for s, fr in f.items())
lp_profit = margin - fixed_cost
by_nt = defaultdict(float)
for (di, p), q in zip(usable, flows):
    by_nt[p.n_transfers] += q
out = {
    "seed": seed, "run": RUN.name, "operated_services": len(f), "valid_paths_all": st.paths_valid,
    "paths_through_operated": len(usable), "lp_status": res.status,
    "recorded_profit": recorded["profit"], "lp_profit_same_network": lp_profit,
    "gain_usd_per_week": lp_profit - recorded["profit"],
    "recorded_served_teu": recorded["served_teu"], "lp_served_teu": served,
    "coverage_recorded_pct": recorded["coverage_pct"],
    "coverage_lp_pct": 100.0 * served / recorded["total_demand_teu"],
    "fixed_cost": fixed_cost, "lp_margin_before_fixed": margin, "teu_by_n_transfers": dict(by_nt),
    "sec": round(time.perf_counter() - t0, 1)}
print(json.dumps({k: (round(v, 1) if isinstance(v, float) else v) for k, v in out.items()}))
OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
