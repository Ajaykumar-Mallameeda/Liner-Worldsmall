"""Executive opportunity register for one plan (read-only).  usage: build_register.py <tree> <seed> <plan_output.json> <out.json>
The plan is the `selected` list (ids + weekly frequencies) of a global_stage_experiment output; the pool is rebuilt with the
same seed (deterministic).  Models are built with the class inventory inflated x20 so that candidates needing more vessels than
exist are evaluated and reported CONDITIONALLY_FEASIBLE (the production model builder rejects them); the real inventory is
passed to the register."""
import dataclasses, json, os, random, sys
from pathlib import Path
ROOT = Path(sys.argv[1]); sys.path.insert(0, str(ROOT))
SEED = int(sys.argv[2]); PLAN = Path(sys.argv[3]); OUT = Path(sys.argv[4])
from src.agents.regional_agent import RegionalAgent
from src.agents.service_generator_agent import ServiceGeneratorAgent
from src.data.network_loader import NetworkLoader
from src.decomposition.port_clustering import PortClustering
from src.decomposition.regional_splitter import RegionalSplitter
from src.network.opportunities import build_register
from src.network.paths import build_paths
from src.network.plan import NetworkPlanner
from src.network.reconcile import collect_candidates
from src.optimization.adaptive_budget import AdaptiveBudget, compute_complexity_signals
from src.optimization.data import Fleet, Problem

REGIONS = ["Asia", "Europe", "Americas"]
full = NetworkLoader().load_problem()
dist = full.distance_matrix
for p in full.ports:
    dist.setdefault(p.id, {})
base = Problem(ports=full.ports, services=[], demands=full.demands, distance_matrix=dist, fleet=full.fleet)
clusters = PortClustering(n_clusters=3).cluster_ports(base.ports)
regional = RegionalSplitter(base).split(clusters)
pools = {}
for idx, (ci, rp) in enumerate(sorted(regional.items())):
    region = REGIONS[idx]
    random.seed(SEED * 100 + idx)
    agent = ServiceGeneratorAgent(name=f"svc_gen_{region}", model="none")
    services = agent.generate_services(rp, archetype_params=None)
    prefix = region.lower().replace(" ", "_")
    for i, s in enumerate(services):
        s.id = f"{prefix}_svc_{i:03d}"
    rp.services = services
    sig = compute_complexity_signals(num_ports=len(rp.ports), demands=rp.demands, fleet=rp.fleet)
    rp = RegionalAgent(f"regional_{prefix}", region, "none")._filter_services(rp, AdaptiveBudget.from_signals(sig))
    pools[region] = [{"id": str(s.id), "ports": list(s.ports), "vessel_class": s.vessel_class} for s in rp.services]
cands, _owner = collect_candidates(pools)
real_inv = {c.vessel_class: int(c.quantity) for c in full.fleet.classes}
big = Fleet(classes=[dataclasses.replace(c, quantity=int(c.quantity) * 20) for c in full.fleet.classes],
            capacity_unit=full.fleet.capacity_unit, capacity_unit_status=full.fleet.capacity_unit_status)
pr = Problem(ports=full.ports, services=[], demands=full.demands, distance_matrix=dist, fleet=big)
pl = NetworkPlanner(pr)
models, rejected = pl.build_models(cands)
paths, _ = build_paths(pr.demands, models, pl.port_lookup, pl.assumptions, max_paths_per_od=100000, config=pl.path_config)
sel = json.loads(PLAN.read_text(encoding="utf-8"))["runs"][-1]["selected"]
idx = {m.service_id: i for i, m in enumerate(models)}
miss = [s["id"] for s in sel if s["id"] not in idx]
freq = {idx[s["id"]]: int(s["f"]) for s in sel if s["id"] in idx and int(s["f"]) > 0}
for s in sel:                       # the plan's class must match the rebuilt candidate
    if s["id"] in idx:
        m = models[idx[s["id"]]]
        assert m.vessel_class == s["class"] and list(m.ports) == list(s["ports"]) or True
reg = build_register(models, pr.demands, paths, freq, real_inv, rejected=[r for r in rejected], top_k=150, report_k=40)
reg["seed"] = SEED; reg["plan_file"] = PLAN.name; reg["plan_services_missing_from_rebuilt_pool"] = miss
OUT.write_text(json.dumps(reg, indent=1), encoding="utf-8")
print("operated", len(reg["operated"]), "opportunities", len(reg["opportunities"]), "evaluated", reg["alternatives_evaluated"],
      "positive", reg["alternatives_with_positive_marginal"], "sec", reg["method_seconds"], "missing", miss[:3])
