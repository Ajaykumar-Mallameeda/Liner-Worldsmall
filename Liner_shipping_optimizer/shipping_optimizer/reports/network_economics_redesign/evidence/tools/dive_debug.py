import pickle
import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1])
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
print("models", len(models), "referenced", len(referenced))

t0 = time.perf_counter()
keep = list(referenced)
floor = {}
for rnd in range(14):
    t1 = time.perf_counter()
    lp = nm._build_and_solve(models, problem.demands, paths, limits, keep, integer=False, penalty=0.0,
                             fixed=None, initial=None, max_departures_cap=None, time_limit_sec=60,
                             threads=None, min_departures=floor)
    obj = pulp.value(lp["prob"].objective)
    fv = {s: float(lp["f"][s].varValue or 0) for s in lp["active"]}
    pos = {s: v for s, v in fv.items() if v > 1e-6}
    frac = {s: v for s, v in pos.items() if abs(v - round(v)) > 1e-6}
    print(f"round {rnd}: status={pulp.LpStatus[lp['prob'].status]} obj={obj:,.0f} active={len(lp['active'])} "
          f"positive={len(pos)} fractional={len(frac)} floors={len(floor)} t={time.perf_counter()-t1:.1f}s", flush=True)
    if not frac:
        break
    for s, v in pos.items():
        if s not in frac:
            floor[s] = max(floor.get(s, 0), int(round(v)))
    order = sorted(frac, key=lambda s: -frac[s])
    for s in order[:max(1, len(order) // 4)]:
        floor[s] = max(floor.get(s, 0), int(-(-frac[s] // 1)))
    keep = sorted(pos)
t2 = time.perf_counter()
res = nm._build_and_solve(models, problem.demands, paths, limits, keep, integer=True, penalty=0.0, fixed=None,
                          initial=None, max_departures_cap=None, time_limit_sec=60, threads=None,
                          min_departures=floor)
print("final integer: status", pulp.LpStatus[res["prob"].status], "obj", pulp.value(res["prob"].objective),
      f"t={time.perf_counter()-t2:.1f}s services_kept={len(keep)}")
