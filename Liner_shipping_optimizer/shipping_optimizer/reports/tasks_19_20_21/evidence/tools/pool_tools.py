"""Production candidate pool of one generator seed (WorldSmall only), importable.

Same construction as ``global_stage_experiment.build_pools`` of the Tasks 14-16 harness
(default configuration: demand-coherent loops, class screening, regional ``_filter_services``
as selected by ``LINER_REGIONAL_FILTER``), so a pool is comparable with every earlier
controlled experiment.  ``init(root)`` must be called once; it puts ``root`` on ``sys.path``.
"""
import hashlib
import random
import sys
from collections import Counter
from pathlib import Path

REGIONS = ["Asia", "Europe", "Americas"]       # orchestrator: regional_agents[:3]
_state = {}


def init(root):
    root = Path(root)
    sys.path.insert(0, str(root))
    from src.data.network_loader import NetworkLoader
    ws = root / "data" / "raw" / "WorldSmall"
    L = NetworkLoader()
    ports = L.load_ports(ws / "ports.csv")
    demands = L.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
    dist = L.load_distance_matrix(ws / "dist_dense.csv")
    fleet = L.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
    for p in ports:
        dist.setdefault(p.id, {})
    _state.update(root=root, ports=ports, demands=demands, dist=dist, fleet=fleet)
    return _state


def fresh_problem():
    from src.optimization.data import Problem
    s = _state
    return Problem(ports=s["ports"], services=[], demands=s["demands"], distance_matrix=s["dist"],
                   fleet=s["fleet"])


def build_pools(seed: int, feedback=None) -> dict:
    from src.agents.regional_agent import RegionalAgent
    from src.agents.service_generator_agent import ServiceGeneratorAgent
    from src.decomposition.port_clustering import PortClustering
    from src.decomposition.regional_splitter import RegionalSplitter
    from src.optimization.adaptive_budget import AdaptiveBudget, compute_complexity_signals
    base = fresh_problem()
    if feedback:
        base.network_feedback = feedback      # Task 21 elitism: travels to every regional problem
    clusters = PortClustering(n_clusters=3).cluster_ports(base.ports)
    regional = RegionalSplitter(base).split(clusters)
    pools, gen, region_of_od = {}, {}, {}
    for idx, (ci, rp) in enumerate(sorted(regional.items())):
        region = REGIONS[idx]
        for d in rp.demands:
            region_of_od[(d.origin, d.destination)] = region
        random.seed(seed * 100 + idx)
        agent = ServiceGeneratorAgent(name=f"svc_gen_{region}", model="none")
        services = agent.generate_services(rp, archetype_params=None)
        prefix = region.lower().replace(" ", "_")
        for i, s in enumerate(services):
            s.id = f"{prefix}_svc_{i:03d}"
        rp.services = services
        sig = compute_complexity_signals(num_ports=len(rp.ports), demands=rp.demands, fleet=rp.fleet)
        budget = AdaptiveBudget.from_signals(sig)
        ra = RegionalAgent(f"regional_{prefix}", region, "none")
        n_generated = len(services)
        rp = ra._filter_services(rp, budget)
        pools[region] = [
            {"id": str(s.id), "ports": list(s.ports), "vessel_class": s.vessel_class,
             "section": getattr(s, "origin_section", "unknown")}
            for s in rp.services]
        gen[region] = {"generated": n_generated, "after_filter": len(rp.services),
                       "filter_max_services": budget.filter_max_services,
                       "by_class_after_filter": dict(Counter(s.vessel_class for s in rp.services))}
    return {"pools": pools, "gen": gen, "region_of_od": region_of_od}


def pool_identity(pools: dict) -> dict:
    from src.network.reconcile import collect_candidates
    h = hashlib.sha256()
    for region in sorted(pools):
        for c in pools[region]:
            h.update(f"{region}|{c['id']}|{','.join(c['ports'])}|{c['vessel_class']}\n".encode())
    cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in pools.items()})
    u = hashlib.sha256()
    for c in cands:
        u.update(f"{','.join(c.ports)}|{c.vessel_class}\n".encode())
    return {"regional_pool_sha256": h.hexdigest(), "unique_candidates": len(cands),
            "unique_order_sha256": u.hexdigest(),
            "regional_sizes": {k: len(v) for k, v in pools.items()}}


def path_pool_identity(paths: dict, models) -> str:
    """Order-sensitive SHA-256 of a path set (OD index, services by id, ports, hubs)."""
    h = hashlib.sha256()
    for di in sorted(paths):
        for p in paths[di]:
            segs = ";".join(f"{models[s.service].service_id}:{s.from_port}>{s.to_port}" for s in p.segments)
            h.update(f"{di}|{p.kind}|{segs}\n".encode())
    return h.hexdigest()
