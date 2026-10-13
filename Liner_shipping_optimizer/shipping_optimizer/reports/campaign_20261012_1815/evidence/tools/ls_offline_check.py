"""Run the PRODUCTION local search (src/network/local_search.py) on a recorded plan (state pickle of
``od_diagnosis_t22_v3.py``) without any MILP: speed and behaviour check on a real instance.

usage: python ls_offline_check.py <tree_root> <state.pkl> [budget_sec]
"""
import dataclasses
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))
STATE = pickle.loads(Path(sys.argv[2]).read_bytes())
BUDGET = float(sys.argv[3]) if len(sys.argv) > 3 else 25.0

from src.data.network_loader import NetworkLoader                       # noqa: E402
from src.network.economics import assumptions_for_problem               # noqa: E402
from src.network.local_search import LocalSearchConfig, local_search    # noqa: E402
from src.network.network_milp import NetworkSolution                    # noqa: E402
from src.network.paths import BUDGET_FIXED, SELECT_FASTEST, build_paths # noqa: E402
from src.network.plan import NetworkPlanner                             # noqa: E402
from src.optimization.data import Problem                               # noqa: E402

ws = ROOT / "data" / "raw" / "WorldSmall"
L = NetworkLoader()
ports = L.load_ports(ws / "ports.csv")
dem = L.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
dist = L.load_distance_matrix(ws / "dist_dense.csv")
fleet = L.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
for p in ports:
    dist.setdefault(p.id, {})
problem = Problem(ports=ports, services=[], demands=dem, distance_matrix=dist, fleet=fleet)
assump = assumptions_for_problem(problem)
planner = NetworkPlanner(problem, assumptions=assump)

models, demands, paths = STATE["models"], STATE["demands"], STATE["paths"]
ops = {int(k): int(v) for k, v in STATE["frequencies"].items() if int(v) > 0}
flows = STATE["flows"]
rev = sum(demands[di].revenue_per_teu * t for di, k, t in flows)
port = sum(paths[di][k].port_cost_per_teu * t for di, k, t in flows)
comp = {"revenue": rev, "per_teu_port_cost": port,
        "vessel_cost": sum(models[s].vessel_week_cost * models[s].vessels(f) for s, f in ops.items()),
        "fuel_cost": sum(models[s].fuel_cost_per_rotation * f for s, f in ops.items()),
        "port_fixed_cost": sum(models[s].port_fixed_per_rotation * f for s, f in ops.items()),
        "unserved_penalty": 0.0}
sol = NetworkSolution(status="feasible", frequencies=dict(ops),
                      vessels={s: models[s].vessels(f) for s, f in ops.items()}, flows=list(flows),
                      objective_components=comp,
                      objective_value=rev - port - comp["vessel_cost"] - comp["fuel_cost"] - comp["port_fixed_cost"])
sol.unserved = {}
limits = {c.vessel_class: c.quantity for c in fleet.classes}
cfg_ls = dataclasses.replace(planner.path_config, selection=SELECT_FASTEST, budget=BUDGET_FIXED)


def all_paths():
    return build_paths(demands, models, planner.port_lookup, assump, max_paths_per_od=10 ** 9, config=cfg_ls)


print(f"start: services={len(ops)} profit={sol.objective_value:,.0f} served={sum(t for _, _, t in flows):,.0f}")
t0 = time.perf_counter()
rep = local_search(models, demands, paths, sol, limits, all_paths,
                   config=LocalSearchConfig(enabled=True, reserve_sec=BUDGET),
                   deadline=t0 + BUDGET)
dt = time.perf_counter() - t0
print(f"done in {dt:.1f}s: applied={rep['applied']} terminated_by={rep['terminated_by']} "
      f"evaluations={rep['evaluations']} setup={rep['setup_sec']}s search={rep['search_sec']}s")
print("reason:", rep["reason"])
if rep["profit_before"] is not None:
    print(f"profit {rep['profit_before']:,.0f} -> {rep['profit_after']:,.0f} (gain {rep['gain_usd']:,.0f}); "
          f"served {rep['served_before']:,.0f} -> {rep['served_after']:,.0f}")
for m in rep["moves"]:
    print("  ", m)
print("objective after:", f"{sol.objective_value:,.0f}", "services:", sum(1 for f in sol.frequencies.values() if f > 0))
