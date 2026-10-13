# appended to the Tasks 19-21 harness header: stand-alone economics of EVERY class on every rotation of the
# production pool (canonical model, ClassScreener.evaluate_class) - why is Feeder_450 never operated?
import statistics as st                                                  # noqa: E402
from collections import Counter, defaultdict                             # noqa: E402
from src.network.economics import assumptions_for_problem               # noqa: E402
from src.services.class_screening import ClassScreener, ClassScreeningConfig  # noqa: E402

built = build_pools(SEED)
problem = fresh_problem()
cands, owner = collect_candidates({k: [dict(c) for c in v] for k, v in built["pools"].items()})
assump = assumptions_for_problem(problem)
scr = ClassScreener(problem, problem.fleet, assump, ClassScreeningConfig(k=1))
classes = [c.vessel_class for c in problem.fleet.classes]
rots = sorted({tuple(c.ports) for c in cands})
print(f"seed={SEED} unique rotations={len(rots)}", flush=True)
by_class = defaultdict(list)
infeasible = defaultdict(Counter)
for r in rots:
    for cls in classes:
        ev = scr.evaluate_class(list(r), problem.fleet.get_class(cls))
        if ev.feasible:
            by_class[cls].append(ev)
        else:
            for reason in ev.reasons:
                infeasible[cls][reason] += 1
inv = {c.vessel_class: (int(c.quantity), c.capacity_teu, c.tc_rate_daily, c.design_speed, c.bunker_consumption_tons_per_day) for c in problem.fleet.classes}
print("class: (inventory, capacity as loaded, TC USD/day, design kn, bunker t/day)")
out = {"seed": SEED, "rotations": len(rots), "classes": {}}
for cls in classes:
    evs = by_class[cls]
    pos = [e for e in evs if e.standalone_profit_best > 0]
    row = {"inventory": inv[cls][0], "capacity": inv[cls][1], "tc_daily": inv[cls][2], "design_speed": inv[cls][3],
           "feasible_rotations": len(evs), "positive_standalone": len(pos),
           "best_standalone_profit": max((e.standalone_profit_best for e in evs), default=None),
           "median_standalone_profit": st.median([e.standalone_profit_best for e in evs]) if evs else None,
           "median_profit_per_vessel_positive": st.median([e.profit_per_vessel for e in pos]) if pos else None,
           "median_fixed_cost_f1": st.median([e.fixed_cost_best for e in evs]) if evs else None,
           "median_served_teu_best": st.median([e.served_teu_best for e in evs]) if evs else None,
           "infeasible_reasons": dict(infeasible[cls])}
    out["classes"][cls] = row
    print(f"{cls:14s} inv={inv[cls][0]:3d} cap={inv[cls][1]:6.0f} TC={inv[cls][2]:6.0f} {inv[cls][3]:4.1f}kn | feasible {len(evs):5d} "
          f"positive {len(pos):4d} | best {row['best_standalone_profit'] or 0:12,.0f} median {row['median_standalone_profit'] or 0:12,.0f} "
          f"| median fixed(f=1) {row['median_fixed_cost_f1'] or 0:11,.0f} | median served TEU {row['median_served_teu_best'] or 0:7,.0f} | infeasible {dict(infeasible[cls])}", flush=True)
OUT.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
