"""Why do some ODs have no path?  For one seed: ODs with no time-feasible direct / one-/two-transfer
journey in the pool, their demand share, their transit limit and the SHORTEST journey the pool
offers (ignoring the limit).  Diagnostic only - nothing here changes any model.

usage: python -I unreachable_ods.py <tree_root> <out.json> <seed>
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pool_tools as PT                                              # noqa: E402

ROOT, OUT, SEED = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
PT.init(ROOT)
from src.network.economics import assumptions_for_problem            # noqa: E402
from src.network.plan import NetworkPlanner                          # noqa: E402
from src.network.reconcile import collect_candidates                 # noqa: E402

built = PT.build_pools(SEED)
problem = PT.fresh_problem()
cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in built["pools"].items()})
a = assumptions_for_problem(problem)
pl = NetworkPlanner(problem, assumptions=a)
models, _ = pl.build_models(cands)
dwell = a.transfer_dwell_days
by_port = defaultdict(list)
for si, m in enumerate(models):
    for p in m.ports:
        by_port[p].append(si)

limits = [d.max_transit_days for d in problem.demands if d.weekly_teu > 0 and d.max_transit_days is not None]
rows = []
tot = sum(d.weekly_teu for d in problem.demands if d.weekly_teu > 0)
for di, d in enumerate(problem.demands):
    if not d.weekly_teu > 0:
        continue
    o, t = d.origin, d.destination
    best_direct = min((models[s].ride(o, t)[1] for s in by_port.get(o, ()) if models[s].ride(o, t)), default=None)
    best_one = None
    for s1 in by_port.get(o, ()):
        for h in models[s1].ports:
            if h in (o, t):
                continue
            r1 = models[s1].ride(o, h)
            if r1 is None:
                continue
            for s2 in by_port.get(h, ()):
                if s2 == s1:
                    continue
                r2 = models[s2].ride(h, t)
                if r2 is None:
                    continue
                v = r1[1] + dwell + r2[1]
                if best_one is None or v < best_one:
                    best_one = v
    rows.append({"od": di, "origin": o, "destination": t, "teu": d.weekly_teu,
                 "rev": d.revenue_per_teu, "limit": d.max_transit_days,
                 "best_direct": best_direct, "best_one_transfer": best_one})

def feasible(r, key):
    v = r[key]
    return v is not None and (r["limit"] is None or v <= r["limit"] + 1e-9)

no_path = [r for r in rows if not feasible(r, "best_direct") and not feasible(r, "best_one_transfer")]
no_conn = [r for r in no_path if r["best_direct"] is None and r["best_one_transfer"] is None]
print(f"ODs={len(rows)} no <=1-transfer path in limit={len(no_path)} "
      f"({sum(r['teu'] for r in no_path) / tot * 100:.2f}% of demand); "
      f"no connection at all <=1 transfer={len(no_conn)}")
slack = [r["best_one_transfer"] - r["limit"] for r in no_path if r["best_one_transfer"] and r["limit"]]
slack_d = [r["best_direct"] - r["limit"] for r in no_path if r["best_direct"] and r["limit"]]
print("limit distribution (days):", Counter(round(x) for x in limits).most_common(12))
print("no-path ODs: shortest 1-transfer exceeds limit by (days) median",
      sorted(slack)[len(slack) // 2] if slack else None, "min", min(slack) if slack else None,
      "| shortest direct exceeds by median", sorted(slack_d)[len(slack_d) // 2] if slack_d else None)
print("no-path ODs: revenue/TEU mean", sum(r["rev"] for r in no_path) / max(1, len(no_path)),
      "teu mean", sum(r["teu"] for r in no_path) / max(1, len(no_path)))
OUT.write_text(json.dumps({"seed": SEED, "n_od": len(rows), "no_path": no_path,
                           "no_path_teu_share": sum(r["teu"] for r in no_path) / tot,
                           "limit_hist": Counter(round(x) for x in limits)}, indent=1, default=str),
               encoding="utf-8")
