"""Controlled candidate-pool experiment (Tasks 9 and 10).

For each (seed, configuration) the SAME WorldSmall problem goes through the SAME
production steps up to and including the regional filter, then the SAME global stage
(``NetworkPlanner`` = path MILP + independent ledger). Only the generator
configuration changes, so any difference is attributable to it.

    regional split (KMeans random_state=42) -> ServiceGeneratorAgent.generate_services
    -> region-prefixed ids -> RegionalAgent._filter_services (adaptive cap)
    -> union + de-duplication (reconcile.collect_candidates) -> global plan

The regional GAs / LLM calls are bypassed: the global stage consumes the filtered
candidate pools, not the GA output (``RegionalAgent.last_candidate_pool``).  The pool
generator's only randomness (``CandidateServiceGenerator``) is seeded per region with
``random.seed(seed + region_index)``, so every run is repeatable.

usage:
    python -I pool_experiment.py <project_root> <out.json> <time_limit> <seeds_csv> <config> [<config> ...]

config grammar (env switches are set inside the process):
    old                   LINER_DEMAND_LOOP_BUDGET=0
    loops<N>              demand-coherent loops, budget N
    <config>+<flag>[+..]  extra switches:
        screen<K>         Task 10 class screening, K alternatives per rotation
        noexempt          ablation: strip the "economically screened" mark before the
                          regional filter, so screened classes face the legacy margin
                          test and cap like every other candidate
        fullint           solve the global stage WITHOUT the LP-guided restriction
                          (full integer problem; shows what the pool allows)
"""
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))
OUT = Path(sys.argv[2])
TL = float(sys.argv[3])
SEEDS = [int(x) for x in sys.argv[4].split(",")]
CONFIGS = sys.argv[5:]

from src.agents.regional_agent import RegionalAgent                  # noqa: E402
from src.agents.service_generator_agent import ServiceGeneratorAgent  # noqa: E402
from src.data.network_loader import NetworkLoader                    # noqa: E402
from src.decomposition.port_clustering import PortClustering         # noqa: E402
from src.decomposition.regional_splitter import RegionalSplitter     # noqa: E402
from src.network.economics import assumptions_for_problem            # noqa: E402
from src.network.plan import NetworkPlanner                          # noqa: E402
from src.network.reconcile import canonical_rotation, collect_candidates  # noqa: E402
from src.optimization.adaptive_budget import (                       # noqa: E402
    AdaptiveBudget, compute_complexity_signals,
)
from src.optimization.data import Problem                            # noqa: E402

ws = ROOT / "data" / "raw" / "WorldSmall"
L = NetworkLoader()
_ports = L.load_ports(ws / "ports.csv")
_demands = L.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
_dist = L.load_distance_matrix(ws / "dist_dense.csv")
_fleet = L.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
for p in _ports:
    _dist.setdefault(p.id, {})


def fresh_problem() -> Problem:
    return Problem(ports=_ports, services=[], demands=_demands, distance_matrix=_dist, fleet=_fleet)


REGIONS = ["Asia", "Europe", "Americas"]          # orchestrator: regional_agents[:3]


def apply_config(cfg: str) -> dict:
    """Set the environment switches of ``cfg`` and return its description."""
    parts = cfg.split("+")
    base, flags = parts[0], parts[1:]
    for k in ("LINER_DEMAND_LOOP_BUDGET", "LINER_CLASS_SCREEN", "POOLEXP_FULLINT", "POOLEXP_NOEXEMPT"):
        os.environ.pop(k, None)
    # explicit legacy class assignment unless a screen<K> flag says otherwise: the
    # production default for an unset variable is screening with k = 1
    os.environ["LINER_CLASS_SCREEN"] = "0"
    if base == "old":
        os.environ["LINER_DEMAND_LOOP_BUDGET"] = "0"
    elif base.startswith("loops"):
        os.environ["LINER_DEMAND_LOOP_BUDGET"] = base[len("loops"):]
    else:
        raise SystemExit(f"unknown config {cfg}")
    for f in flags:
        if f.startswith("screen"):                    # Task 10: alternatives per rotation
            os.environ["LINER_CLASS_SCREEN"] = f[len("screen"):]
        elif f == "fullint":
            os.environ["POOLEXP_FULLINT"] = "1"
        elif f == "noexempt":
            os.environ["POOLEXP_NOEXEMPT"] = "1"
        else:
            raise SystemExit(f"unknown flag {f}")
    return {"config": cfg, "env": {k: os.environ[k] for k in
                                   ("LINER_DEMAND_LOOP_BUDGET", "LINER_CLASS_SCREEN", "POOLEXP_FULLINT",
                                    "POOLEXP_NOEXEMPT")
                                   if k in os.environ}}


def build_pools(seed: int, clusters) -> dict:
    prob = fresh_problem()
    regional = RegionalSplitter(prob).split(clusters)
    pools, gen_reports = {}, {}
    for idx, (ci, rp) in enumerate(sorted(regional.items())):
        region = REGIONS[idx]
        random.seed(seed * 100 + idx)
        agent = ServiceGeneratorAgent(name=f"svc_gen_{region}", model="none")
        services = agent.generate_services(rp, archetype_params=None)
        if os.environ.get("POOLEXP_NOEXEMPT") == "1":
            for s_ in services:
                if getattr(s_, "economically_screened", False):
                    s_.economically_screened = False
        prefix = region.lower().replace(" ", "_")
        for i, s in enumerate(services):
            s.id = f"{prefix}_svc_{i:03d}"
        rp.services = services
        sig = compute_complexity_signals(num_ports=len(rp.ports), demands=rp.demands, fleet=rp.fleet)
        budget = AdaptiveBudget.from_signals(sig)
        ra = RegionalAgent(f"regional_{prefix}", region, "none")
        rp = ra._filter_services(rp, budget)
        pools[region] = [
            {"id": str(s.id), "ports": list(s.ports), "vessel_class": s.vessel_class,
             "section": getattr(s, "origin_section", "unknown")}
            for s in rp.services]
        gen_reports[region] = {
            "generated": agent.last_candidate_report.generated,
            "accepted": agent.last_candidate_report.accepted,
            "rejected": agent.last_candidate_report.rejected,
            "rejections_by_reason": dict(agent.last_candidate_report.rejections_by_reason),
            "accepted_by_section": dict(agent.last_candidate_report.accepted_by_section),
            "accepted_by_class": dict(agent.last_candidate_report.accepted_by_class),
            "class_fallbacks": agent.last_candidate_report.class_fallbacks,
            "demand_coherent": (agent.last_demand_coherent_report.to_dict()
                                if agent.last_demand_coherent_report is not None else None),
            "class_screening": (agent.last_class_screening_report.to_dict()
                                if agent.last_class_screening_report is not None else None),
            "filter_max_services": budget.filter_max_services,
            "after_filter": len(rp.services),
        }
    return {"pools": pools, "gen": gen_reports}


def standalone_stats(problem, models) -> dict:
    """Stand-alone weekly profit at f=1 (own capacity, direct cargo, LP per candidate)."""
    import numpy as np
    from scipy.optimize import linprog
    P = {p.id: p for p in problem.ports}
    dem = {}
    for d in problem.demands:
        if d.weekly_teu > 0:
            dem[(d.origin, d.destination)] = d

    def var_cost(o, t):
        g = lambda pid, a: float(getattr(P[pid], a, 0.0) or 0.0)
        return g(o, "handling_cost") + g(t, "handling_cost") + g(o, "variable_port_call_cost") + g(t, "variable_port_call_cost")

    out = {}
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
            out[m.service_id] = (-fixed, 0)
            continue
        c = -np.array([x[2] for x in ods])
        A = np.zeros((legs, len(ods)))
        for j, (_, lg, _) in enumerate(ods):
            for l in lg:
                A[l, j] = 1.0
        res = linprog(c, A_ub=A, b_ub=np.full(legs, m.capacity_teu),
                      bounds=[(0, x[0].weekly_teu) for x in ods], method="highs")
        out[m.service_id] = ((-res.fun if res.success else 0.0) - fixed, len(ods))
    return out


def run_global(pools: dict, tl: float) -> dict:
    prob = fresh_problem()
    cands, owner = collect_candidates({k: [dict(c) for c in v] for k, v in pools.items()})
    section_of = {}
    for region, pool in pools.items():
        for c in pool:
            section_of[(canonical_rotation(c["ports"]), c["vessel_class"])] = c.get("section", "unknown")
    planner = NetworkPlanner(prob, assumptions=assumptions_for_problem(prob))
    t0 = time.perf_counter()
    kw = {"lp_guided": False} if os.environ.get("POOLEXP_FULLINT") == "1" else {}
    plan = planner.plan(cands, demands=prob.demands, time_limit_sec=tl, **kw)
    dt = time.perf_counter() - t0
    led = plan.ledger
    n_offered = sum(len(v) for v in pools.values())
    res = {
        "candidates_in_regional_pools": n_offered,
        "candidates_unique_offered": len(cands),
        "duplicate_rate": 1.0 - len(cands) / n_offered if n_offered else 0.0,
        "modelled": len(plan.models), "rejected_in_global": len(plan.rejected_candidates),
        "rejected_reasons": dict(Counter(r for b in plan.rejected_candidates for r in b.get("reasons", []))),
        "by_n_ports": dict(sorted(Counter(len(m.ports) for m in plan.models).items())),
        "by_class": dict(Counter(m.vessel_class for m in plan.models)),
        "by_section": dict(Counter(
            section_of.get((canonical_rotation(c.ports), c.vessel_class), "unknown") for c in cands)),
        "status": plan.status, "ok": plan.ok, "milp_runtime_sec": round(dt, 1),
        "path_model": plan.path_stats.to_dict() if plan.path_stats else {},
    }
    st = standalone_stats(prob, plan.models)
    res["standalone_profitable"] = sum(1 for v in st.values() if v[0] > 0)
    sec_by_id = {}
    for c in cands:
        sec_by_id[c.service_id] = section_of.get((canonical_rotation(c.ports), c.vessel_class), "unknown")
    res["standalone_profitable_by_section"] = dict(Counter(
        sec_by_id.get(sid, "unknown") for sid, v in st.items() if v[0] > 0))
    res["standalone_profitable_by_n_ports"] = dict(Counter(
        len(m.ports) for m in plan.models if st.get(m.service_id, (0, 0))[0] > 0))
    if led is not None:
        used_sections = Counter(sec_by_id.get(sid, "unknown") for sid in led.service_rows)
        res.update({
            "profit": led.operating_profit, "revenue": led.revenue, "total_cost": led.operating_cost,
            "fuel_cost": led.fuel_cost, "vessel_cost": led.vessel_cost,
            "margin_pct": 100 * led.operating_profit / led.revenue if led.revenue > 0 else None,
            "coverage_pct": led.coverage * 100, "served_teu": led.served_teu,
            "total_demand_teu": led.total_demand_teu,
            "n_services": len(led.service_rows), "vessels": sum(led.vessels_by_class.values()),
            "vessels_by_class": dict(led.vessels_by_class),
            "selected_by_section": dict(used_sections),
            "selected_by_n_ports": dict(Counter(len(r["ports"]) for r in led.service_rows.values())),
            "violations": list(led.violations), "reconciled": plan.reconciliation.get("reconciled"),
            "relaxation_bound": plan.solution.relaxation_bound if plan.solution else None,
            "selected": [{"id": sid, "ports": r["ports"], "class": r["vessel_class"], "f": r["frequency"],
                          "section": sec_by_id.get(sid, "unknown"), "revenue": r["revenue"]}
                         for sid, r in led.service_rows.items()],
        })
    return res


results = {"time_limit_sec": TL, "seeds": SEEDS, "configs": CONFIGS, "runs": []}
base_problem = fresh_problem()
clusters = PortClustering(n_clusters=3).cluster_ports(base_problem.ports)
for seed in SEEDS:
    for cfg in CONFIGS:
        desc = apply_config(cfg)
        t0 = time.perf_counter()
        built = build_pools(seed, clusters)
        t_gen = time.perf_counter() - t0
        g = run_global(built["pools"], TL)
        row = {"seed": seed, **desc, "generation_sec": round(t_gen, 1), "generator": built["gen"], **g}
        results["runs"].append(row)
        print(f"seed={seed} {cfg:14s} pool={g['candidates_unique_offered']:4d} 2p/3p/4p/5p+="
              f"{g['by_n_ports']} standalone+={g['standalone_profitable']:3d} "
              f"profit={g.get('profit', float('nan')):>12,.0f} cov={g.get('coverage_pct', float('nan')):5.1f}% "
              f"svc={g.get('n_services')} ves={g.get('vessels')} st={g['status']} {g['milp_runtime_sec']}s", flush=True)
        OUT.write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
print("wrote", OUT)
