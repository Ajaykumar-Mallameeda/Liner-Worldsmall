"""Read-only prototype: greedy class-forced growth of long rotations for Post_panamax / Super_panamax using the canonical
service model (ClassScreener / demand_coherent._Evaluator).  Does the pool lack profitable trunk rotations for large classes?"""
import json, sys, math
from collections import defaultdict
from pathlib import Path
ROOT = Path(sys.argv[1]); OUT = Path(sys.argv[2]); MAXP = int(sys.argv[3]) if len(sys.argv) > 3 else 8
sys.path.insert(0, str(ROOT))
from src.data.network_loader import NetworkLoader
from src.network.economics import assumptions_for_problem
from src.optimization.data import Problem
from src.services.demand_coherent import _Demand, _Evaluator, DemandCoherentConfig
ws = ROOT / "data" / "raw" / "WorldSmall"; L = NetworkLoader()
ports = L.load_ports(ws / "ports.csv"); dem = L.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
dist = L.load_distance_matrix(ws / "dist_dense.csv"); fleet = L.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
for p in ports: dist.setdefault(p.id, {})
base = Problem(ports=ports, services=[], demands=dem, distance_matrix=dist, fleet=fleet)
a = assumptions_for_problem(base)
lookup = {p.id: p for p in ports}
D = _Demand(dem, lookup); cfg = DemandCoherentConfig(max_ports=MAXP)
ev = _Evaluator(base, fleet, a, D, set(), cfg); known = set(dist)
res = {}
for cname in ("Post_panamax", "Super_panamax", "Panamax_2400"):
    cls = fleet.get_class(cname)
    elig = [p for p in lookup if p in known and (float(getattr(lookup[p], "draft", 0) or 0) >= cls.draft - 1e-9)]
    seeds = sorted([k for k in D.teu if k[0] in elig and k[1] in elig and k[0] < k[1]], key=lambda k: -D.opportunity(k))[:60]
    best = []
    for sd in seeds:
        ports_ = list(sd); cur, why = ev.evaluate(ports_, cls)
        sc = cur["standalone"] if cur else -math.inf
        for _ in range(MAXP - 2):
            link = defaultdict(float)
            for m_ in ports_:
                for k in D.by_port.get(m_, ()):
                    o = k[1] if k[0] == m_ else k[0]
                    if o not in ports_ and o in elig: link[o] += D.opportunity(k)
            if not link: break
            nb = sorted(link, key=lambda p: (-link[p], p))[:14]
            bb = None
            for P in nb:
                for pos in range(len(ports_)):
                    new = ports_[:pos + 1] + [P] + ports_[pos + 1:]
                    m, w = ev.evaluate(new, cls)
                    if m is None: continue
                    if bb is None or m["standalone"] > bb[0]: bb = (m["standalone"], new, m)
            if bb is None or bb[0] <= sc + 1e-9: break
            sc, ports_, cur = bb
        if cur: best.append({"ports": ports_, "standalone": round(cur["standalone"]), "vessels": cur["vessels"], "served": round(cur["served"]), "cap_teu": cls.capacity_teu, "fixed": round(cur["fixed"])})
    best.sort(key=lambda r: -r["standalone"])
    res[cname] = {"eligible_ports": len(elig), "n_rotations": len(best), "n_positive": sum(1 for r in best if r["standalone"] > 0), "top": best[:4]}
    print(cname, res[cname]["eligible_ports"], res[cname]["n_rotations"], res[cname]["n_positive"]); [print("  ", r) for r in best[:3]]
OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
