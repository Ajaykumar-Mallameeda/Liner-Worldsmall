"""For ODs without any time-feasible path (``unreachable_ods.py`` output): is the transit limit
physically attainable at all?  Pure sailing time of the OD's directed distance at the FASTEST
class design speed (no port stay, no transfer) against its limit, and whether the pool offers a
two-port rotation of that OD.  Diagnostic only.

usage: python -I unreachable_cause.py <tree_root> <unreachable_ods.json> <out.json> <seed>
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pool_tools as PT                                              # noqa: E402

ROOT, SRC, OUT, SEED = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4])
PT.init(ROOT)
from src.network.reconcile import collect_candidates                 # noqa: E402

problem = PT.fresh_problem()
fleet = problem.fleet
speeds = {c.vessel_class: c.design_speed for c in fleet.classes}
vmax = max(speeds.values())
print("design speeds (kn):", speeds)
built = PT.build_pools(SEED)
cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in built["pools"].items()})
two_port = {frozenset(c.ports) for c in cands if len(c.ports) == 2}
dist = problem.distance_matrix
data = json.loads(SRC.read_text(encoding="utf-8"))
tot = sum(d.weekly_teu for d in problem.demands if d.weekly_teu > 0)
rows, cls = [], Counter()
for r in data["no_path"]:
    o, t, lim = r["origin"], r["destination"], r["limit"]
    nm_ = (dist.get(o) or {}).get(t)
    pure = nm_ / (vmax * 24.0) if nm_ else None
    has_two_port = frozenset((o, t)) in two_port
    if pure is None:
        c = "no_distance"
    elif lim is not None and pure > lim + 1e-9:
        c = "limit_below_pure_sailing_time_at_fastest_class"
    elif has_two_port:
        c = "two_port_service_exists_but_not_time_feasible_with_its_class"
    else:
        c = "attainable_but_no_two_port_candidate_in_pool"
    cls[c] += 1
    rows.append({**r, "pure_sailing_days_fastest_class": pure, "has_two_port_candidate": has_two_port,
                 "cause": c})
share = {k: sum(r["teu"] for r in rows if r["cause"] == k) / tot for k in cls}
print(json.dumps({"count": dict(cls), "share_of_total_demand": share}, indent=1))
OUT.write_text(json.dumps({"seed": SEED, "design_speeds": speeds, "count": dict(cls),
                           "share_of_total_demand": share, "rows": rows}, indent=1, default=str),
               encoding="utf-8")
