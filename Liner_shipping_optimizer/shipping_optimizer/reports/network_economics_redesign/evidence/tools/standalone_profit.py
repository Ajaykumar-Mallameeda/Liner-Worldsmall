"""Standalone weekly profit of every candidate at f = 1 (direct cargo only, own capacity)."""
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))
from src.data.network_loader import NetworkLoader                # noqa: E402
from src.network.economics import assumptions_for_problem        # noqa: E402
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
pl = NetworkPlanner(problem, assumptions=assumptions_for_problem(problem))
models, _ = pl.build_models(cands)
P = {p.id: p for p in ports}
dem = {(d.origin, d.destination): d for d in demands if d.weekly_teu > 0}


def var_cost(o, t):
    g = lambda pid, a: float(getattr(P[pid], a, 0.0) or 0.0)
    return g(o, "handling_cost") + g(t, "handling_cost") + g(o, "variable_port_call_cost") + g(t, "variable_port_call_cost")


rows = []
for m in models:
    legs = len(m.ports)
    ods = []
    for a in m.ports:
        for b in m.ports:
            d = dem.get((a, b)) if a != b else None
            if d is None:
                continue
            r = m.ride(a, b)
            if r is None:
                continue
            if d.max_transit_days is not None and r[1] > d.max_transit_days + 1e-9:
                continue
            ods.append((d, r[0], d.revenue_per_teu - var_cost(a, b)))
    fixed = m.weekly_fixed_cost(1)
    if not ods:
        rows.append((m.service_id, m.vessel_class, len(m.ports), m.cycle_time_days, m.vessels(1), 0, -fixed, 0.0))
        continue
    c = -np.array([x[2] for x in ods])
    A = np.zeros((legs, len(ods)))
    for j, (_, legs_used, _) in enumerate(ods):
        for lg in legs_used:
            A[lg, j] = 1.0
    res = linprog(c, A_ub=A, b_ub=np.full(legs, m.capacity_teu), bounds=[(0, x[0].weekly_teu) for x in ods], method="highs")
    contrib = -res.fun if res.success else 0.0
    rows.append((m.service_id, m.vessel_class, len(m.ports), m.cycle_time_days, m.vessels(1), len(ods), contrib - fixed, contrib))

pos = [r for r in rows if r[6] > 0]
print("candidates:", len(rows), "| positive standalone profit at f=1:", len(pos))
print("by #ports among positive:", sorted(Counter(r[2] for r in pos).items()))
print("by class among positive:", dict(Counter(r[1] for r in pos)))
rows.sort(key=lambda r: -r[6])
print("top 15 standalone (id, class, ports, T, vessels, ods, profit/wk, profit per vessel):")
for r in rows[:15]:
    print(f"  {r[0]:<22}{r[1]:<14}{r[2]:>3}p T={r[3]:>3} v={r[4]:>2} ods={r[5]:>2} profit={r[6]:>12,.0f} per_vessel={r[6]/max(1,r[4]):>10,.0f}")
tot_v = sum(r[4] for r in pos)
print(f"sum of positive standalone profits: {sum(r[6] for r in pos):,.0f} using {tot_v} vessels (overlap not netted)")
