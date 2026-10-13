"""Does a recorded plan carry services that lose money once the cargo is re-routed?

For a recorded run: with every service operated, re-route the cargo over all valid paths (the
LP of ``fixed_network_flow_lp.py``); then for each operated service, drop it (f = 0, its vessels
and fixed costs saved), re-route over the remaining services and compare.  A drop that raises the
profit is a move a local search over the plan would take.  Diagnostic only.

usage: python -I drop_one_lp.py <tree_root> <run_output.json> <out.json>
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pool_tools as PT                                              # noqa: E402

ROOT, RUN, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
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
built = PT.build_pools(seed)
problem = PT.fresh_problem()
cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in built["pools"].items()})
a = assumptions_for_problem(problem)
pl = NetworkPlanner(problem, assumptions=a)
models, _ = pl.build_models(cands)
index = {m.service_id: i for i, m in enumerate(models)}
f_all = {index[s]: fr for s, fr in operated.items() if fr > 0 and s in index}
demands = list(problem.demands)
paths, st = build_paths(demands, models, pl.port_lookup, a, max_paths_per_od=10 ** 9, config=PathConfig())
by_services = defaultdict(list)
for di, plist in paths.items():
    for p in plist:
        if all(s in f_all for s in p.services):
            by_services[di].append(p)


def solve(f):
    usable = [(di, p) for di, pls in by_services.items() for p in pls if all(s in f for s in p.services)]
    if not usable:
        return 0.0, 0.0
    rows_cap, od_row, data, ri, ci, obj = {}, {}, [], [], [], []
    for j, (di, p) in enumerate(usable):
        obj.append(-(demands[di].revenue_per_teu - p.port_cost_per_teu))
        for seg in p.segments:
            for leg in seg.legs:
                k = (seg.service, leg)
                rows_cap.setdefault(k, len(rows_cap))
                data.append(1.0); ri.append(rows_cap[k]); ci.append(j)
    n_cap = len(rows_cap)
    for j, (di, p) in enumerate(usable):
        if di not in od_row:
            od_row[di] = n_cap + len(od_row)
        data.append(1.0); ri.append(od_row[di]); ci.append(j)
    A = coo_matrix((data, (ri, ci)), shape=(n_cap + len(od_row), len(usable))).tocsr()
    b = np.zeros(A.shape[0])
    for (s, leg), i in rows_cap.items():
        b[i] = models[s].capacity_teu * f[s]
    for di, i in od_row.items():
        b[i] = demands[di].weekly_teu
    res = linprog(np.array(obj), A_ub=A, b_ub=b, bounds=(0, None), method="highs")
    return -res.fun, float(res.x.sum())


def fixed(f):
    return sum(models[s].weekly_fixed_cost(fr) for s, fr in f.items())


t0 = time.perf_counter()
m0, s0 = solve(f_all)
base = m0 - fixed(f_all)
rows = []
for s in sorted(f_all):
    f = {k: v for k, v in f_all.items() if k != s}
    m, served = solve(f)
    rows.append({"service": models[s].service_id, "class": models[s].vessel_class,
                 "ports": len(models[s].ports), "f": f_all[s], "vessels": models[s].vessels(f_all[s]),
                 "profit_if_dropped": m - fixed(f), "delta": (m - fixed(f)) - base,
                 "served_if_dropped": served})
rows.sort(key=lambda x: -x["delta"])
out = {"seed": seed, "run": RUN.name, "profit_all_paths_same_network": base, "served": s0,
       "recorded_profit": r["ledger"]["profit"], "drops": rows, "sec": round(time.perf_counter() - t0, 1)}
OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
pos = [x for x in rows if x["delta"] > 1.0]
print(f"seed {seed}: recorded {r['ledger']['profit']:,.0f}  all-paths same network {base:,.0f}  "
      f"drop moves that raise profit: {len(pos)} of {len(rows)}; best {rows[0]['delta']:+,.0f} "
      f"({rows[0]['service']} {rows[0]['class']} f={rows[0]['f']}); sum of positive {sum(x['delta'] for x in pos):+,.0f}")
