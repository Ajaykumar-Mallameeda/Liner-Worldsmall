"""Replay the captured global-stage inputs under different solver settings.
import logging; logging.basicConfig(level=logging.WARNING)

usage: python replay_global.py <project_root> <pickle> <call_index> <variant> [time_limit_sec]

variants: base | full_int | nolp_hint
Same candidates, same demand, same fleet: only the solve strategy changes.
"""
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))

from src.data.network_loader import NetworkLoader              # noqa: E402
from src.network.economics import assumptions_for_problem      # noqa: E402
from src.network.plan import NetworkPlanner                    # noqa: E402
from src.network.reconcile import collect_candidates           # noqa: E402
from src.optimization.data import Problem                      # noqa: E402

data = pickle.loads(Path(sys.argv[2]).read_bytes())
call = data["captured"][int(sys.argv[3])]
variant = sys.argv[4]
tl = float(sys.argv[5]) if len(sys.argv) > 5 else 120.0

ws = ROOT / "data" / "raw" / "WorldSmall"
L = NetworkLoader()
ports = L.load_ports(ws / "ports.csv")
demands = L.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
dist = L.load_distance_matrix(ws / "dist_dense.csv")
fleet = L.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
for p in ports:
    dist.setdefault(p.id, {})
problem = Problem(ports=ports, services=[], demands=demands, distance_matrix=dist, fleet=fleet)

cands, owner = collect_candidates(call["pools"])
print(f"call={sys.argv[3]} candidates={len(cands)} variant={variant} time_limit={tl}")
planner = NetworkPlanner(problem, assumptions=assumptions_for_problem(problem))
kw = {}
if variant == "full_int":
    kw["lp_guided"] = False
if variant == "allclasses":
    from src.network.plan import Candidate
    have = {(tuple(c.ports), c.vessel_class) for c in cands}
    extra = []
    for c in list(cands):
        for fc in fleet.classes:
            key = (tuple(c.ports), fc.vessel_class)
            if key not in have:
                have.add(key)
                extra.append(Candidate(f"{c.service_id}@{fc.vessel_class}", tuple(c.ports), fc.vessel_class))
    cands = list(cands) + extra
    print("expanded candidates:", len(cands))
t0 = time.perf_counter()
plan = planner.plan(cands, demands=problem.demands, time_limit_sec=tl, **kw)
dt = time.perf_counter() - t0
led = plan.ledger
print(f"status={plan.status} ok={plan.ok} runtime={dt:.1f}s")
if led is not None:
    print(f"profit={led.operating_profit:,.0f} revenue={led.revenue:,.0f} cost={led.operating_cost:,.0f} "
          f"coverage={led.coverage*100:.1f}% services={len(led.service_rows)} vessels={sum(led.vessels_by_class.values())}")
    print("by class:", dict(led.vessels_by_class))
sol = plan.solution
if sol is not None:
    print("dive:", getattr(sol, "dive", None)); print("relaxation_bound:", sol.relaxation_bound, "| considered:", sol.n_services_considered,
          "restricted_to:", sol.n_services_restricted_to, "| msg:", sol.message)
