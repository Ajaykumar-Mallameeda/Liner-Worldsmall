"""Read-only diagnostic: for every rotation of the production pool (seed S), the stand-alone result of EVERY vessel
class (feasibility reason / vessels / profit / profit per vessel).  Explains why Post_panamax & Super_panamax get no
candidates.  usage: class_diag.py <tree_root> <seed> <out.json>"""
import json, sys, random
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(sys.argv[1]); SEED = int(sys.argv[2]); OUT = Path(sys.argv[3])
sys.path.insert(0, str(ROOT))
from src.agents.regional_agent import RegionalAgent
from src.agents.service_generator_agent import ServiceGeneratorAgent
from src.data.network_loader import NetworkLoader
from src.decomposition.port_clustering import PortClustering
from src.decomposition.regional_splitter import RegionalSplitter
from src.network.economics import assumptions_for_problem
from src.network.reconcile import collect_candidates
from src.optimization.adaptive_budget import AdaptiveBudget, compute_complexity_signals
from src.optimization.data import Problem
from src.services.class_screening import ClassScreener, ClassScreeningConfig
REG = ["Asia", "Europe", "Americas"]
ws = ROOT / "data" / "raw" / "WorldSmall"; L = NetworkLoader()
ports = L.load_ports(ws / "ports.csv"); dem = L.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
dist = L.load_distance_matrix(ws / "dist_dense.csv"); fleet = L.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
for p in ports: dist.setdefault(p.id, {})
base = Problem(ports=ports, services=[], demands=dem, distance_matrix=dist, fleet=fleet)
cl = PortClustering(n_clusters=3).cluster_ports(base.ports); reg = RegionalSplitter(base).split(cl)
pools = {}
for idx, (ci, rp) in enumerate(sorted(reg.items())):
    region = REG[idx]; random.seed(SEED * 100 + idx)
    svcs = ServiceGeneratorAgent(name=f"g{region}", model="none").generate_services(rp, archetype_params=None)
    for i, s in enumerate(svcs): s.id = f"{region.lower()}_svc_{i:03d}"
    rp.services = svcs
    b = AdaptiveBudget.from_signals(compute_complexity_signals(num_ports=len(rp.ports), demands=rp.demands, fleet=rp.fleet))
    rp = RegionalAgent(f"r_{region}", region, "none")._filter_services(rp, b)
    pools[region] = [{"id": str(s.id), "ports": list(s.ports), "vessel_class": s.vessel_class, "section": getattr(s, "origin_section", "unknown")} for s in rp.services]
cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in pools.items()})
a = assumptions_for_problem(base)
sc = ClassScreener(base, fleet, a, ClassScreeningConfig(k=1))
inv = {c.vessel_class: int(c.quantity) for c in fleet.classes}
res = defaultdict(lambda: Counter()); profit = defaultdict(list); rows = []
for c in cands:
    row = {"id": c.service_id, "ports": list(c.ports), "assigned": c.vessel_class, "n_ports": len(c.ports)}
    for cls in fleet.classes:
        ev = sc.evaluate_class(list(c.ports), cls)
        k = cls.vessel_class
        if not ev.feasible:
            r = (ev.reasons or ["infeasible"])[0]; res[k][r] += 1; row[k] = {"feasible": False, "why": r}; continue
        fits = ev.vessels_at_best <= inv[k]
        res[k]["feasible"] += 1
        if ev.standalone_profit_best > 0: res[k]["positive_standalone"] += 1
        if not fits: res[k]["needs_more_vessels_than_owned"] += 1
        row[k] = {"feasible": True, "profit": round(ev.standalone_profit_best, 0), "vessels": ev.vessels_at_best,
                  "ppv": round(ev.profit_per_vessel, 0), "served_teu": round(ev.served_teu_best, 1), "fixed_cost": round(ev.fixed_cost_best, 0), "f": ev.best_frequency}
        profit[k].append(ev.standalone_profit_best)
    rows.append(row)
summary = {k: dict(v) for k, v in res.items()}
best = Counter(); best_ppv = Counter()
for r in rows:
    f = {k: v for k, v in r.items() if isinstance(v, dict) and v.get("feasible")}
    if f:
        best[max(f, key=lambda k: f[k]["profit"])] += 1
        best_ppv[max(f, key=lambda k: f[k]["ppv"])] += 1
out = {"seed": SEED, "n_candidates": len(cands), "assigned_class": dict(Counter(c.vessel_class for c in cands)),
       "inventory": inv, "per_class": summary, "best_by_profit": dict(best), "best_by_profit_per_vessel": dict(best_ppv),
       "top_positive_by_class": {k: sorted([r for r in rows if isinstance(r.get(k), dict) and r[k].get("feasible")], key=lambda r: -r[k]["profit"])[:5] for k in inv}}
OUT.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: out[k] for k in ("n_candidates", "assigned_class", "inventory", "per_class", "best_by_profit", "best_by_profit_per_vessel")}, indent=1))
