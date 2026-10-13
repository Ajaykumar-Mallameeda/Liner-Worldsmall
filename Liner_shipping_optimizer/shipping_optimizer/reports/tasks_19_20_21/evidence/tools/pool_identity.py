"""Candidate-pool and path-set identity of a tree for several generator seeds (no solver).

Used for the rollback gate: with every Tasks 19-21 switch off the pool and the path set of the
live tree must equal the frozen baseline's element by element and in order.

usage: python -I pool_identity.py <tree_root> <out.json> <seed> [<seed> ...]
Environment variables of the caller select the configuration (LINER_*).
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pool_tools as PT                                              # noqa: E402

ROOT, OUT = Path(sys.argv[1]), Path(sys.argv[2])
SEEDS = [int(s) for s in sys.argv[3:]]
PT.init(ROOT)

from src.network.economics import assumptions_for_problem            # noqa: E402
from src.network.paths import build_paths                            # noqa: E402
from src.network.plan import NetworkPlanner                          # noqa: E402
from src.network.reconcile import collect_candidates                 # noqa: E402

res = {"tree": str(ROOT), "env": {k: v for k, v in os.environ.items() if k.startswith("LINER_")},
       "seeds": {}}
for seed in SEEDS:
    built = PT.build_pools(seed)
    ident = PT.pool_identity(built["pools"])
    problem = PT.fresh_problem()
    cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in built["pools"].items()})
    a = assumptions_for_problem(problem)
    pl = NetworkPlanner(problem, assumptions=a)
    models, _ = pl.build_models(cands)
    kw = {"config": pl.path_config} if hasattr(pl, "path_config") else {}   # the baseline has none
    paths, st = build_paths(list(problem.demands), models, pl.port_lookup, a, max_paths_per_od=10, **kw)
    res["seeds"][str(seed)] = {**ident, "paths": sum(len(v) for v in paths.values()),
                               "path_pool_sha256": PT.path_pool_identity(paths, models),
                               "by_section": {r: {} for r in built["pools"]}}
    print(seed, ident["unique_candidates"], ident["unique_order_sha256"][:16],
          res["seeds"][str(seed)]["path_pool_sha256"][:16], flush=True)
OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
