"""Greedy commit dive prototype: commit the most-used services one batch at a time."""
import math
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1])
FRAC = float(sys.argv[4]) if len(sys.argv) > 4 else 0.10
sys.path.insert(0, str(ROOT))
import pulp                                                      # noqa: E402
from src.data.network_loader import NetworkLoader                # noqa: E402
from src.network import network_milp as nm                       # noqa: E402
from src.network.economics import assumptions_for_problem        # noqa: E402
from src.network.paths import build_paths                        # noqa: E402
from src.network.plan import NetworkPlanner                      # noqa: E402
from src.network.reconcile import collect_candidates             # noqa: E402
from src.optimization.data import Problem                        # noqa: E402

data = pickle.loads(Path(sys.argv[2]).read_bytes())
call = data["captured"][int(sys.argv[3])]
ws = ROOT / "data" / "raw" / "WorldSmall"
L = NetworkLoader()
ports = L.load_ports(ws / "ports.csv")
demands = L.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
dist = L.load_distance_matrix(ws / "dist_dense.csv")
fleet = L.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
for p in ports:
    dist.setdefault(p.id, {})
problem = Problem(ports=ports, services=[], demands=demands, distance_matrix=dist, fleet=fleet)
cands, _ = collect_candidates(call["pools"])
A = assumptions_for_problem(problem)
pl = NetworkPlanner(problem, assumptions=A)
models, _ = pl.build_models(cands)
paths, st = build_paths(problem.demands, models, pl.port_lookup, A, max_paths_per_od=10)
referenced = sorted({s for pl_ in paths.values() for p in pl_ for s in p.services})
limits = {c.vessel_class: c.quantity for c in fleet.classes}
print("models", len(models), "referenced", len(referenced), "batch fraction", FRAC)


def lp(keep, floor):
    return nm._build_and_solve(models, problem.demands, paths, limits, keep, integer=False, penalty=0.0,
                               fixed=None, initial=None, max_departures_cap=None, time_limit_sec=60,
                               threads=None, min_departures=floor)


t0 = time.perf_counter()
committed, eliminated = {}, set()
last_batch = []
fails = 0
pos = {}
for rnd in range(120):
    keep = [s for s in referenced if s not in eliminated]
    r = lp(keep, committed)
    if r["prob"].status != pulp.LpStatusOptimal:
        fails += 1
        for s in last_batch:
            committed.pop(s, None)
            eliminated.add(s)
        print(f"  round {rnd}: LP infeasible -> eliminated {len(last_batch)} services", flush=True)
        last_batch = []
        if fails > 15:
            break
        continue
    obj = pulp.value(r["prob"].objective)
    pos = {s: float(r["f"][s].varValue or 0) for s in r["active"] if (r["f"][s].varValue or 0) > 1e-6}
    unc = {s: v for s, v in pos.items() if s not in committed}
    if rnd % 5 == 0 or not unc:
        print(f"round {rnd}: LP obj={obj:,.0f} positive={len(pos)} uncommitted={len(unc)} "
              f"committed={len(committed)} eliminated={len(eliminated)} t={time.perf_counter()-t0:.0f}s", flush=True)
    if not unc:
        break
    order = sorted(unc, key=lambda s: -unc[s])
    want = max(1, int(math.ceil(len(order) * FRAC)))
    need = {}
    for s in committed:
        m = models[s]
        need[m.vessel_class] = need.get(m.vessel_class, 0) + m.vessels(committed[s])
    batch = []
    for s in order:
        if len(batch) >= want:
            break
        m = models[s]
        v = m.vessels(1)
        if need.get(m.vessel_class, 0) + v > limits.get(m.vessel_class, m.class_inventory):
            continue                      # would exhaust the class: leave it uncommitted
        need[m.vessel_class] = need.get(m.vessel_class, 0) + v
        batch.append(s)
    if not batch:
        break
    for s in batch:
        committed[s] = 1
    last_batch = batch

final = sorted(set(committed) | set(pos))
t2 = time.perf_counter()
res = nm._build_and_solve(models, problem.demands, paths, limits, final, integer=True, penalty=0.0, fixed=None,
                          initial=None, max_departures_cap=None, time_limit_sec=90, threads=None,
                          min_departures=committed)
print("final integer: status", pulp.LpStatus[res["prob"].status], "obj", pulp.value(res["prob"].objective),
      f"t={time.perf_counter()-t2:.1f}s services_in_final={len(final)} committed={len(committed)} total_t={time.perf_counter()-t0:.0f}s")
if res["prob"].status == pulp.LpStatusOptimal:
    used = {s: int(round(res['f'][s].varValue or 0)) for s in res['active'] if (res['f'][s].varValue or 0) > 0.5}
    print("operated services:", len(used), "vessels:", sum(int(round(res['n'][s].varValue or 0)) for s in used))
