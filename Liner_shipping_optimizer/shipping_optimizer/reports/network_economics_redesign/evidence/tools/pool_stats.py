import pickle, sys, collections
from pathlib import Path
ROOT = Path(sys.argv[1]); sys.path.insert(0, str(ROOT))
from src.data.network_loader import NetworkLoader
from src.network.economics import assumptions_for_problem
from src.network.plan import NetworkPlanner
from src.network.reconcile import collect_candidates
from src.optimization.data import Problem
data = pickle.loads(Path(sys.argv[2]).read_bytes())
call = data["captured"][int(sys.argv[3])]
ws = ROOT/"data"/"raw"/"WorldSmall"; L = NetworkLoader()
ports = L.load_ports(ws/"ports.csv"); dem = L.load_demands(ws/"Demand_WorldSmall_Fixed_Sep.csv")
dist = L.load_distance_matrix(ws/"dist_dense.csv"); fleet = L.load_fleet(ws/"fleet_WorldSmall.csv", ws/"fleet_data.csv")
for p in ports: dist.setdefault(p.id, {})
problem = Problem(ports=ports, services=[], demands=dem, distance_matrix=dist, fleet=fleet)
cands, owner = collect_candidates(call["pools"])
pl = NetworkPlanner(problem, assumptions=assumptions_for_problem(problem))
models, rej = pl.build_models(cands)
print("candidates", len(cands), "modelled", len(models), "rejected", len(rej))
print("by #ports:", sorted(collections.Counter(len(m.ports) for m in models).items()))
print("by class:", collections.Counter(m.vessel_class for m in models))
print("by region owner:", collections.Counter(owner.values()))
cyc = sorted(m.cycle_time_days for m in models)
print("cycle days pct 0/25/50/75/100:", [cyc[int(q*(len(cyc)-1))] for q in (0,.25,.5,.75,1)])
# ride-feasible directed OD pairs per service
lim = {}
for d in dem:
    if d.weekly_teu > 0: lim[(d.origin, d.destination)] = (d.max_transit_days, d.weekly_teu)
feas = []
for m in models:
    n = 0; teu = 0.0
    for a in m.ports:
        for b in m.ports:
            if a == b or (a, b) not in lim: continue
            r = m.ride(a, b)
            if r and (lim[(a, b)][0] is None or r[1] <= lim[(a, b)][0] + 1e-9):
                n += 1; teu += lim[(a, b)][1]
    feas.append((len(m.ports), n, teu, m.capacity_teu))
import statistics
for k in sorted({f[0] for f in feas}):
    sub = [f for f in feas if f[0] == k]
    print(f"ports={k}: n={len(sub)} median ride-feasible ODs={statistics.median(f[1] for f in sub)} "
          f"median directly-servable TEU/wk={statistics.median(f[2] for f in sub):,.0f} median cap={statistics.median(f[3] for f in sub):,.0f}")
