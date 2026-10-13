"""Dump the regional candidate pools of ONE tree, for an exact before/after comparison.

usage: python -I pool_dump.py <tree_root> <out.json> <seed> [<seed> ...]

Works on the frozen baseline tree and on the final tree alike (it uses only APIs both
have): clusters the WorldSmall ports like the orchestrator, then for every region runs
``ServiceGeneratorAgent.generate_services`` (generator randomness seeded per region as in
``pool_experiment.py``) and ``RegionalAgent._filter_services``, and records the ordered
list of (ports, vessel class, capacity, cycle time). The environment switches
``LINER_DEMAND_LOOP_BUDGET`` and ``LINER_CLASS_SCREEN`` are read by the final tree only; a
tree that does not know them ignores them. A fresh interpreter per tree is required.
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))
OUT = Path(sys.argv[2])
SEEDS = [int(x) for x in sys.argv[3:]]

from src.agents.regional_agent import RegionalAgent                  # noqa: E402
from src.agents.service_generator_agent import ServiceGeneratorAgent  # noqa: E402
from src.data.network_loader import NetworkLoader                    # noqa: E402
from src.decomposition.port_clustering import PortClustering         # noqa: E402
from src.decomposition.regional_splitter import RegionalSplitter     # noqa: E402
from src.optimization.adaptive_budget import (                       # noqa: E402
    AdaptiveBudget, compute_complexity_signals,
)
from src.optimization.data import Problem                            # noqa: E402

ws = ROOT / "data" / "raw" / "WorldSmall"
L = NetworkLoader()
ports = L.load_ports(ws / "ports.csv")
demands = L.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
dist = L.load_distance_matrix(ws / "dist_dense.csv")
fleet = L.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
for p in ports:
    dist.setdefault(p.id, {})
REGIONS = ["Asia", "Europe", "Americas"]
result = {}
for seed in SEEDS:
    problem = Problem(ports=ports, services=[], demands=demands, distance_matrix=dist, fleet=fleet)
    clusters = PortClustering(n_clusters=3).cluster_ports(problem.ports)
    regional = RegionalSplitter(problem).split(clusters)
    out = {}
    for idx, (ci, rp) in enumerate(sorted(regional.items())):
        random.seed(seed * 100 + idx)
        agent = ServiceGeneratorAgent(name=f"dump_{idx}", model="none")
        services = agent.generate_services(rp, archetype_params=None)
        prefix = REGIONS[idx].lower()
        for i, s in enumerate(services):
            s.id = f"{prefix}_svc_{i:03d}"
        rp.services = services
        sig = compute_complexity_signals(num_ports=len(rp.ports), demands=rp.demands, fleet=rp.fleet)
        budget = AdaptiveBudget.from_signals(sig)
        rp = RegionalAgent(f"regional_{prefix}", REGIONS[idx], "none")._filter_services(rp, budget)
        out[REGIONS[idx]] = [[list(s.ports), s.vessel_class, float(s.capacity), int(s.cycle_time)]
                             for s in rp.services]
    result[str(seed)] = out
OUT.write_text(json.dumps(result), encoding="utf-8")
print("seeds", SEEDS, {s: {r: len(v) for r, v in d.items()} for s, d in result.items()})
