"""Iteration-structured controlled experiment (Task 21 elitism).

The orchestrator runs three iterations; each rebuilds the candidate pool and runs the global
stage, and the best verified iteration is reported.  This emulates that loop WITHOUT the regional
GA / regional MILP hints (the same simplification as every controlled experiment of Tasks 15-16):

    iteration i   pool = production generation with generator seed ``seed * 10 + i``
                  (+ the elites / route-operator variants when LINER_ELITISM / LINER_ROUTE_OPERATORS
                  are set and a verified earlier iteration exists), production global stage
                  (``reconcile``: path MILP + independent ledger), time limit TL
    feedback      ``OrchestratorAgent._update_network_feedback`` (the production code) stores the
                  operated rotations and unserved OD demand of the best verified iteration so far

The environment decides the variant (LINER_*); with nothing set this is the baseline: three
independent iterations.  Paired seeds use identical pools in iteration 0 across variants.

usage: python -I iteration_experiment.py <tree_root> <out.json> <seed> <time_limit_sec> [iterations]
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pool_tools as PT                                              # noqa: E402

ROOT, OUT, SEED, TL = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4])
ITERS = int(sys.argv[5]) if len(sys.argv) > 5 else 3
PT.init(ROOT)

from src.agents.orchestrator_agent import OrchestratorAgent          # noqa: E402
from src.network.reconcile import reconcile                          # noqa: E402

REGIONS = PT.REGIONS
result = {"seed": SEED, "time_limit_sec": TL, "iterations": ITERS, "tree": str(ROOT),
          "env": {k: v for k, v in os.environ.items() if k.startswith(("LINER_", "NETWORK_MILP", "T15_"))},
          "runs": []}
problem = PT.fresh_problem()
best = None
for it in range(ITERS):
    t0 = time.perf_counter()
    built = PT.build_pools(SEED * 10 + it, feedback=getattr(problem, "network_feedback", None))
    t_pool = time.perf_counter() - t0
    # the global stage runs on the (feedback-free) global problem object
    gproblem = PT.fresh_problem()
    t1 = time.perf_counter()
    stage = reconcile(gproblem, {k: [dict(c) for c in v] for k, v in built["pools"].items()},
                      built["region_of_od"], REGIONS, hints=None, time_limit_sec=TL, iteration=it,
                      max_paths_per_od=int(os.environ.get("T15_MAX_PATHS", "10")))
    wall = time.perf_counter() - t1
    row = {"iteration": it, "pool": PT.pool_identity(built["pools"]), "pool_sec": round(t_pool, 1),
           "stage_ok": stage.ok, "status": stage.status, "wall_sec": round(wall, 1),
           "feedback_used": bool(getattr(problem, "network_feedback", None)),
           "feedback_elites": len((getattr(problem, "network_feedback", None) or {}).get("operated", []))}
    led = stage.plan.ledger if stage.plan is not None else None
    if stage.ok and led is not None:
        verified = bool(stage.network_ledger.get("verified"))
        row.update({"verified": verified, "profit": led.operating_profit, "revenue": led.revenue,
                    "cost": led.operating_cost, "coverage_pct": led.coverage * 100.0,
                    "served_teu": led.served_teu, "services": len(led.service_rows),
                    "vessels": sum(led.vessels_by_class.values()), "violations": len(led.violations),
                    "milp_status": stage.plan.status,
                    "paths": sum(len(v) for v in stage.plan.paths.values()),
                    "by_section": None})
        if verified and (best is None or led.operating_profit > best["profit"]):
            best = {"iteration": it, "profit": led.operating_profit, "coverage_pct": led.coverage * 100.0,
                    "served_teu": led.served_teu, "services": len(led.service_rows)}
        OrchestratorAgent._update_network_feedback(problem, stage.network_ledger, it)
    result["runs"].append(row)
    print(f"seed={SEED} it={it} fb={row['feedback_used']}({row['feedback_elites']}) "
          f"pool={row['pool']['unique_candidates']} status={row['status']} "
          f"profit={row.get('profit', float('nan')):>12,.0f} cov={row.get('coverage_pct', float('nan')):5.1f}% "
          f"svc={row.get('services')} viol={row.get('violations')}", flush=True)
    result["best"] = best
    OUT.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
print("best:", best)
