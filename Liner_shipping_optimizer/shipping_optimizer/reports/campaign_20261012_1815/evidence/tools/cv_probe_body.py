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
