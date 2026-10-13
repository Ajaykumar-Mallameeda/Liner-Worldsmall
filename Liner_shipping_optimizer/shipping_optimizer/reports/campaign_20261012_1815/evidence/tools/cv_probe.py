"""Controlled global-stage experiment for Tasks 15, 16 and 19-21 (WorldSmall only).

(Tasks 19-21 copy of the Tasks 14-16 harness; additions: path-set identity, transfer-count
histogram, strategy report, per-run path configuration from the environment.)

For one generator seed the SAME production candidate pool (default configuration:
demand-coherent loops budget 60 + class screening k=1, regional ``_filter_services``)
goes through the SAME production global stage ``src.network.reconcile.reconcile``
(NetworkPlanner = path MILP + independent ledger + regional partition).  The only thing
that varies between strategies is the solve step: ``src.network.plan.solve_network`` is
replaced, inside this process only, by the strategy under test.  Planning, path
construction, the independent ledger and the regional partition are the production code.

usage:
    python -I global_stage_experiment.py <tree_root> <out.json> <seed> <time_limit_sec> <strategy> [...]

strategy grammar
    prod                   production: LP relaxation -> restrict to its support -> integer solve
    fullint                unrestricted integer problem (no restriction)
    two:<T1>               two-stage: production restricted solve with budget T1, then the
                           unrestricted integer problem warm-started from its incumbent for the
                           remaining budget; the best valid incumbent is kept
    A_sa                   restricted to LP support  U  stand-alone-profitable candidates
    A_pert                 restricted to the union of the supports of the LP and two LPs with
                           perturbed vessel costs (x0.8, x1.2)
    A_top<K>               restricted to the K LP-support services carrying the most LP revenue
    A_pool<K>              restricted to LP support U the K candidates of largest LP-ranked
                           stand-alone profit (K integer)
    prog:<k1,k2,..>        CBC only: nested restrictions of the LP support (top-k by LP revenue),
                           smallest first, each warm-started from the previous incumbent; the
                           best valid incumbent is kept
    highs                  (information only) the unrestricted integer model solved by HiGHS
                           through scipy.optimize.milp - NOT a production solver

Environment: nothing is set here; the production defaults apply (so the pool is the
production default).  ``T16_FILTER`` is read by the tree under test, not by this tool.
"""
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))
OUT = Path(sys.argv[2])
SEED = int(sys.argv[3])
TL = float(sys.argv[4])
STRATS = sys.argv[5:]

import pulp                                                            # noqa: E402

import src.network.network_milp as nm                                  # noqa: E402
import src.network.plan as planmod                                     # noqa: E402
from src.agents.regional_agent import RegionalAgent                    # noqa: E402
from src.agents.service_generator_agent import ServiceGeneratorAgent   # noqa: E402
from src.data.network_loader import NetworkLoader                      # noqa: E402
from src.decomposition.port_clustering import PortClustering           # noqa: E402
from src.decomposition.regional_splitter import RegionalSplitter       # noqa: E402
from src.network.metrics import canonical_network_economics            # noqa: E402
from src.network.reconcile import canonical_rotation, collect_candidates, reconcile  # noqa: E402
from src.optimization.adaptive_budget import (                         # noqa: E402
    AdaptiveBudget, compute_complexity_signals,
)
from src.optimization.data import Problem                              # noqa: E402

ORIG_SOLVE = nm.solve_network
REGIONS = ["Asia", "Europe", "Americas"]            # orchestrator: regional_agents[:3]
DIAG = {}                                           # strategy diagnostics of the current solve
FILTER_LOG = []                                     # per-region filter decisions (Task 16)

if os.environ.get("T16_FILTER"):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import t16_filter_variants as _t16                                  # noqa: E402
    from src.network.economics import assumptions_for_problem as _afp  # noqa: E402
    from src.services.class_screening import ClassScreener as _CS, ClassScreeningConfig as _CSC  # noqa: E402

    def _log(region, variant, rows, cap):
        FILTER_LOG.append({"region": region, "variant": variant, "cap": cap, "candidates": rows})

    _t16.install(RegionalAgent, _CS, _CSC, _afp, _log)

ws = ROOT / "data" / "raw" / "WorldSmall"
_L = NetworkLoader()
_ports = _L.load_ports(ws / "ports.csv")
_demands = _L.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
_dist = _L.load_distance_matrix(ws / "dist_dense.csv")
_fleet = _L.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
for _p in _ports:
    _dist.setdefault(_p.id, {})


def fresh_problem() -> Problem:
    return Problem(ports=_ports, services=[], demands=_demands, distance_matrix=_dist, fleet=_fleet)


# ----------------------------------------------------------------------------- pool
def build_pools(seed: int) -> dict:
    base = fresh_problem()
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


# appended to the Tasks 19-21 harness header (pool construction) by assemble_od_diagnosis.py
from collections import Counter                                          # noqa: E402
from src.network.economics import assumptions_for_problem               # noqa: E402
from src.network.class_variants import augment_candidates                # noqa: E402

built = build_pools(SEED)
problem = fresh_problem()
cands, owner = collect_candidates({k: [dict(c) for c in v] for k, v in built["pools"].items()})
assump = assumptions_for_problem(problem)
print(f"seed={SEED} unique candidates={len(cands)} by class={dict(Counter(c.vessel_class for c in cands))}", flush=True)
inventory = {c.vessel_class: int(c.quantity) for c in problem.fleet.classes}
print("inventory", inventory, flush=True)
t0 = time.perf_counter()
extra, rep = augment_candidates(problem, assump, cands, fraction=1.0)
dt = time.perf_counter() - t0
print(f"augment(fraction=1.0): {dt:.1f}s evaluated={rep['rotations_evaluated']} feasible={rep['variants_feasible']} "
      f"positive={rep['variants_positive_standalone']} available={rep.get('scored_variants_available')} added={rep['added']}", flush=True)
print("over-subscribed:", rep["over_subscribed_classes"], "targets:", rep["target_classes"], flush=True)
print("additions by target class:", dict(Counter(a["vessel_class"] for a in rep["additions"])), flush=True)
print("additions by source class:", dict(Counter(a["source_class"] for a in rep["additions"])), flush=True)
adds = rep["additions"]
for frac in (0.05, 0.10, 0.20):
    n = max(1, int(round(frac * len(cands))))
    sub = adds[:n]
    print(f"  fraction {frac}: n={n} vessels at f=1 (sum)={sum(a['vessels_at_best'] for a in sub)} "
          f"mean profit/vessel={sum(a['profit_per_vessel_usd_per_week'] for a in sub)/max(1,len(sub)):,.0f} "
          f"classes={dict(Counter(a['vessel_class'] for a in sub))}", flush=True)
OUT.write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
