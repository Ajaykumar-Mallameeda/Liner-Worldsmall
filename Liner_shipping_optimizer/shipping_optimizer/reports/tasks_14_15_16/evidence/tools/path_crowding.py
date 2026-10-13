"""How much of the path set does the per-OD cap discard, for the pool of a given filter variant?

usage: T16_FILTER=<variant> python -I path_crowding.py <tree_root> <seed> <out.json>

Builds the seed's pool under the variant, builds models and OD paths exactly as the production
planner does (``max_paths_per_od`` = 10), and reports: candidates, paths built, paths dropped
by the cap, ODs that hit the cap, and the share of the kept paths that are direct / transfer,
and the class mix of the services on the kept paths.
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT, SEED, OUT = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(ROOT))
TOOLS = Path(__file__).resolve().parent
src = (TOOLS / "global_stage_experiment.py").read_text(encoding="utf-8")
head = src.split("# ----------------------------------------------------------------------------- main")[0]
sys.argv = [sys.argv[0], str(ROOT), str(OUT), str(SEED), "120"]
ns = {"__file__": str(TOOLS / "global_stage_experiment.py"), "__name__": "harness_head"}
exec(compile(head, "global_stage_experiment_head", "exec"), ns)

from src.network.economics import assumptions_for_problem                     # noqa: E402
from src.network.paths import build_paths                                     # noqa: E402
from src.network.plan import NetworkPlanner                                   # noqa: E402
from src.network.reconcile import collect_candidates                          # noqa: E402

built = ns["build_pools"](SEED)
problem = ns["fresh_problem"]()
cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in built["pools"].items()})
planner = NetworkPlanner(problem, assumptions=assumptions_for_problem(problem))
models, _ = planner.build_models(cands)
res = {"variant": os.environ.get("T16_FILTER", "legacy"), "seed": SEED, "candidates": len(cands)}
for cap in (10, 10000):
    paths, st = build_paths(problem.demands, models, planner.port_lookup, planner.assumptions,
                            max_paths_per_od=cap)
    kept = [p for pl in paths.values() for p in pl]
    cls = Counter()
    for p in kept:
        for si in set(p.services):
            cls[models[si].vessel_class] += 1
    res[f"cap{cap}"] = {
        "paths_built": st.paths_built, "paths_dropped_by_cap": st.paths_dropped_by_cap,
        "ods_with_paths": len(paths), "ods_at_cap": sum(1 for pl in paths.values() if len(pl) >= cap),
        "direct": sum(1 for p in kept if p.kind == "direct"),
        "transfer": sum(1 for p in kept if p.kind == "transfer"),
        "path_service_incidences_by_class": dict(cls),
        "od_without_path": st.od_without_path,
    }
OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps(res, indent=1))
