"""Task 10 diagnostics: why is each registered class (not) offered, and what would it earn?

usage: python -I class_diagnostics.py <project_root> <out.json> <seed>

Builds the regional candidate pools exactly like ``pool_experiment.py`` (demand loops on,
legacy class assignment), then evaluates EVERY registered class on EVERY distinct rotation
of the pool with the production ``ClassScreener`` and reports, per class:

  * feasible / infeasible rotations and the infeasibility reasons,
  * rotations on which the class has a positive stand-alone profit ("promising"),
  * how often the legacy nearest-capacity rule would have offered it,
  * how often the legacy regional margin rule (capacity x 0.5 x 150 USD > one vessel's
    weekly hire) would have removed it,
  * how often the screening (k = 1) picks it.
"""
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))
OUT, SEED = Path(sys.argv[2]), int(sys.argv[3])
os.environ["LINER_DEMAND_LOOP_BUDGET"] = "60"
os.environ["LINER_CLASS_SCREEN"] = "0"

from src.agents.service_generator_agent import ServiceGeneratorAgent      # noqa: E402
from src.data.network_loader import NetworkLoader                         # noqa: E402
from src.decomposition.port_clustering import PortClustering              # noqa: E402
from src.decomposition.regional_splitter import RegionalSplitter          # noqa: E402
from src.network.economics import assumptions_for_problem                 # noqa: E402
from src.optimization.data import Problem                                 # noqa: E402
from src.services.class_screening import ClassScreener, ClassScreeningConfig  # noqa: E402
from src.services.service_feasibility import rank_vessel_classes          # noqa: E402

ws = ROOT / "data" / "raw" / "WorldSmall"
L = NetworkLoader()
ports = L.load_ports(ws / "ports.csv")
demands = L.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
dist = L.load_distance_matrix(ws / "dist_dense.csv")
fleet = L.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
for p in ports:
    dist.setdefault(p.id, {})
problem = Problem(ports=ports, services=[], demands=demands, distance_matrix=dist, fleet=fleet)
clusters = PortClustering(n_clusters=3).cluster_ports(problem.ports)
regional = RegionalSplitter(problem).split(clusters)

rotations = {}           # canonical rotation -> (ports, target capacity (first seen))
for idx, (ci, rp) in enumerate(sorted(regional.items())):
    random.seed(SEED * 100 + idx)
    agent = ServiceGeneratorAgent(name="diag", model="none")
    for s in agent.generate_services(rp, archetype_params=None):
        key = ClassScreener._rotation_key(s.ports)
        rotations.setdefault(key, (list(s.ports), s.capacity))

sc = ClassScreener(problem, fleet, assumptions_for_problem(problem), ClassScreeningConfig(k=1))
classes = [c.vessel_class for c in fleet.classes]
feasible = Counter(); promising = Counter(); picked = Counter(); legacy_offer = Counter()
margin_removes = Counter(); infeasible = defaultdict(Counter); profit_sum = defaultdict(float)
n_with_promising = 0
for key, (route, target) in rotations.items():
    res = sc.screen(route, target)
    if any(e.promising for e in res.evaluations):
        n_with_promising += 1
    for e in res.evaluations:
        if e.feasible:
            feasible[e.vessel_class] += 1
            if e.promising:
                promising[e.vessel_class] += 1
                profit_sum[e.vessel_class] += e.standalone_profit_best
                fc = fleet.get_class(e.vessel_class)
                if not (fc.capacity_teu * 0.5 * 150 > fc.tc_rate_daily * 7):
                    margin_removes[e.vessel_class] += 1
        else:
            for r in e.reasons:
                infeasible[e.vessel_class][r] += 1
    if res.legacy_class:
        legacy_offer[res.legacy_class] += 1
    for e in res.selected:
        picked[e.vessel_class] += 1

inv = {c.vessel_class: c.quantity for c in fleet.classes}
cap = {c.vessel_class: c.capacity_teu for c in fleet.classes}
hire = {c.vessel_class: c.tc_rate_daily * 7 for c in fleet.classes}
out = {
    "seed": SEED, "distinct_rotations": len(rotations), "rotations_with_a_profitable_class": n_with_promising,
    "per_class": {
        c: {"capacity_teu": cap[c], "inventory": inv[c], "weekly_hire_per_vessel": hire[c],
            "legacy_margin_rule_passes": cap[c] * 0.5 * 150 > hire[c],
            "feasible_rotations": feasible[c], "infeasible_by_reason": dict(infeasible[c]),
            "rotations_profitable_standalone": promising[c],
            "profitable_but_removed_by_legacy_margin_rule": margin_removes[c],
            "legacy_nearest_capacity_offers": legacy_offer[c],
            "screening_k1_picks": picked[c],
            "mean_standalone_profit_when_profitable": (profit_sum[c] / promising[c]) if promising[c] else None}
        for c in classes},
    "screening_report": sc.report.to_dict(),
}
OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "per_class"}, indent=1)[:600])
for c in classes:
    r = out["per_class"][c]
    print(f"{c:14s} cap={r['capacity_teu']:>6.0f} inv={r['inventory']:>3d} margin_rule_ok={r['legacy_margin_rule_passes']!s:5s} "
          f"feasible={r['feasible_rotations']:>5d} profitable={r['rotations_profitable_standalone']:>4d} "
          f"removed_by_margin_rule={r['profitable_but_removed_by_legacy_margin_rule']:>4d} legacy_offers={r['legacy_nearest_capacity_offers']:>5d} "
          f"k1_picks={r['screening_k1_picks']:>5d} infeasible={dict(r['infeasible_by_reason'])}")
