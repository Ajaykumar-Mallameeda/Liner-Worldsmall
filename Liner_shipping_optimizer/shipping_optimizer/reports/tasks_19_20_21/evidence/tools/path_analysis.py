"""Path-set analysis for one generator seed (no solver): how many valid paths exist, how many
each selection rule keeps, build time, which ODs have no path, how much demand sits behind
them and what two-transfer journeys add.

usage: python -I path_analysis.py <tree_root> <out.json> <seed> [<variant> ...]
variants (default: all): base | cost | cost_mh | cost_mh_all | adaptive | adaptive_mh | cost30
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pool_tools as PT                                              # noqa: E402

ROOT, OUT, SEED = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
VARIANTS = sys.argv[4:] or ["base", "cost", "cost_mh", "cost_mh_all", "adaptive", "adaptive_mh", "cost30"]
PT.init(ROOT)

from src.network.economics import assumptions_for_problem            # noqa: E402
from src.network.paths import PathConfig, build_paths                # noqa: E402
from src.network.plan import NetworkPlanner                          # noqa: E402
from src.network.reconcile import collect_candidates                 # noqa: E402

t0 = time.perf_counter()
built = PT.build_pools(SEED)
problem = PT.fresh_problem()
cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in built["pools"].items()})
assumptions = assumptions_for_problem(problem)
planner = NetworkPlanner(problem, assumptions=assumptions)
models, rejected = planner.build_models(cands)
demands = list(problem.demands)
total_teu = sum(d.weekly_teu for d in demands if d.weekly_teu > 0)
print(f"seed={SEED} pool={len(cands)} models={len(models)} rejected={len(rejected)} "
      f"setup={time.perf_counter() - t0:.1f}s", flush=True)

CFG = {
    "base": (10, PathConfig()),
    "cost": (10, PathConfig(selection="cost_aware")),
    "cost_mh": (10, PathConfig(selection="cost_aware", max_transfers=2)),
    "cost_mh_all": (10, PathConfig(selection="cost_aware", max_transfers=2, multi_hop_min_alternatives=10_000)),
    "adaptive": (10, PathConfig(selection="cost_aware", budget="adaptive")),
    "adaptive_mh": (10, PathConfig(selection="cost_aware", budget="adaptive", max_transfers=2)),
    "cost30": (30, PathConfig(selection="cost_aware")),
    "fast_mh": (10, PathConfig(selection="fastest", max_transfers=2)),
}
result = {"seed": SEED, "pool_unique": len(cands), "models": len(models), "total_demand_teu": total_teu,
          "variants": {}}
for name in VARIANTS:
    cap, cfg = CFG[name]
    t1 = time.perf_counter()
    paths, st = build_paths(demands, models, planner.port_lookup, assumptions,
                            max_paths_per_od=cap, config=cfg)
    sec = time.perf_counter() - t1
    kinds = Counter(p.kind for pl in paths.values() for p in pl)
    served_ods = set(paths)
    unreach_teu = sum(d.weekly_teu for di, d in enumerate(demands) if d.weekly_teu > 0 and di not in served_ods)
    # per-path economics: carrying cost vs revenue
    n_pos = n_all = 0
    cost_sum = 0.0
    for di, pl in paths.items():
        rev = demands[di].revenue_per_teu
        for p in pl:
            n_all += 1
            c = p.port_cost_per_teu + (p.slot_cost_per_teu or 0.0)
            cost_sum += c
            if rev > c:
                n_pos += 1
    row = {"variant": name, "cap": cap, "config": cfg.describe(), "build_sec": round(sec, 2),
           "stats": st.to_dict(), "kept_by_kind": dict(kinds),
           "ods_with_paths": len(paths), "unreachable_od_teu": unreach_teu,
           "unreachable_od_pct": 100.0 * unreach_teu / total_teu,
           "paths_with_revenue_above_full_load_cost": n_pos, "paths": n_all,
           "path_pool_sha256": PT.path_pool_identity(paths, models)}
    result["variants"][name] = row
    s = row["stats"]
    print(f"  {name:12s} cap={cap:2d} paths={n_all:6d} valid={s['paths_valid']:7d} at_cap={s['od_at_cap']:5d} "
          f"noPath={s['od_without_path']:3d} unreach={row['unreachable_od_pct']:5.2f}% "
          f"mh_enum={s['od_multi_hop_enumerated']:4d} rescued={s['od_rescued_by_multi_hop']:3d} "
          f"mh_kept={s['paths_multi_hop_kept']:5d} t={sec:5.1f}s kinds={dict(kinds)}", flush=True)
    OUT.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
print("wrote", OUT)
