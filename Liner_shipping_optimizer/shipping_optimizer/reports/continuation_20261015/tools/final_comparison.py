"""Final matched-seed comparison tables (Workstream 9) from the per-seed CSVs.  usage: final_comparison.py <continuation_dir> <out_prefix>

Every arm of every batch is summarised over the seeds where it produced a valid plan; the number of seeds it did NOT solve is shown next to it.
Pairs are compared only inside one batch (same time, same load); absolute levels of different batches are not comparable.
"""
import csv
import json
import statistics as st
import sys
from pathlib import Path

D, PFX = Path(sys.argv[1]), Path(sys.argv[2])
CLASSES = ["Feeder_450", "Feeder_800", "Panamax_1200", "Panamax_2400", "Post_panamax", "Super_panamax"]


def load(path):
    return list(csv.DictReader(Path(path).open(encoding="utf-8")))


def num(r, k):
    try:
        return float(r[k])
    except (KeyError, TypeError, ValueError):
        return None


def summ(rows, arm):
    r = [x for x in rows if x["arm"] == arm]
    ok = [x for x in r if x["status"] == "feasible"]
    def mean(k):
        v = [num(x, k) for x in ok if num(x, k) is not None]
        return st.mean(v) if v else None
    out = {"arm": arm, "seeds": len(r), "solved": len(ok), "not_solved_or_invalid": len(r) - len(ok),
           "failed_seeds": [int(x["seed"]) for x in r if x["status"] != "feasible"],
           "profit_M": (mean("profit_usd_wk") or 0) / 1e6 if ok else None,
           "profit_median_M": st.median([num(x, "profit_usd_wk") for x in ok]) / 1e6 if ok else None,
           "profit_min_max_M": [min(num(x, "profit_usd_wk") for x in ok) / 1e6, max(num(x, "profit_usd_wk") for x in ok) / 1e6] if ok else None,
           "revenue_M": (mean("revenue_usd_wk") or 0) / 1e6 if ok else None,
           "cost_M": {k: (mean(c) or 0) / 1e6 for k, c in (("vessel", "vessel_cost"), ("fuel", "fuel_cost"), ("port_call_incl_canal", "port_call_fixed"),
                                                        ("handling", "handling"), ("transshipment", "transshipment"), ("total", "total_cost"))} if ok else None,
           "coverage_pct": mean("coverage_pct"), "served_teu": mean("served_teu"), "services": mean("services"),
           "departures": mean("departures_per_week"), "assigned": mean("vessels_used"), "owned": mean("inventory"), "idle": mean("idle_vessels"),
           "deployment_ratio": (mean("vessels_used") / mean("inventory")) if ok and mean("inventory") else None,
           "productive_load_factor": mean("load_factor_network"), "profit_per_assigned_k": (mean("profit_per_vessel") or 0) / 1e3 if ok else None,
           "profit_per_owned_k": ((mean("profit_usd_wk") or 0) / mean("inventory") / 1e3) if ok and mean("inventory") else None,
           "assigned_by_class": {c: mean(f"used_{c}") for c in CLASSES} if ok else None,
           "stage_wall_sec_mean": mean("stage_wall_sec"), "ledger_violation_seeds": [int(x["seed"]) for x in ok if num(x, "ledger_violations")],
           "transit_violation_seeds": [int(x["seed"]) for x in ok if num(x, "transit_violations")],
           "solver_status_raw": sorted({x["solver_status"] for x in r})}
    return out


batches = {}
spec = [("frozen_C3_20_seeds (earlier, healthy machine; reference only)", D.parent / "class_mismatch_campaign" / "per_seed_C3.csv", ["C3"]),
        ("head_drift_control_3_seeds", D / "per_seed_C3head.csv", ["C3head"]),
        ("Z1_clean_sequential_seeds_0_9", D / "per_seed_Z1.csv", ["C3z", "L1z", "P2z"]),
        ("Y_clean_sequential_seeds_0_9", D / "per_seed_Y.csv", ["C3y", "P3"]),
        ("L1_first_batch_CONTAMINATED_seeds_0_14", D / "per_seed_L1_partial.csv", ["C3c", "L1"])]
for name, path, arms in spec:
    if not Path(path).exists():
        continue
    rows = load(path)
    batches[name] = [summ(rows, a) for a in arms]
res = {"batches": batches}
pairs = {}
for ctrl, arm, csvn in (("C3z", "L1z", "per_seed_Z1.csv"), ("C3z", "P2z", "per_seed_Z1.csv"), ("C3y", "P3", "per_seed_Y.csv"), ("C3c", "L1", "per_seed_L1_partial.csv")):
    p = D / csvn
    if not p.exists():
        continue
    rows = load(p)
    by = {(r["arm"], int(r["seed"])): r for r in rows}
    d, c = [], []
    for s in sorted({s for (a, s) in by}):
        a_, c_ = by.get((arm, s)), by.get((ctrl, s))
        if a_ and c_ and a_["status"] == "feasible" and c_["status"] == "feasible":
            d.append(num(a_, "profit_usd_wk") - num(c_, "profit_usd_wk"))
            c.append(num(a_, "coverage_pct") - num(c_, "coverage_pct"))
    pairs[f"{arm} - {ctrl}"] = {"pairs": len(d), "mean_delta_M": st.mean(d) / 1e6 if d else None, "median_delta_M": st.median(d) / 1e6 if d else None,
                                 "min_max_delta_M": [min(d) / 1e6, max(d) / 1e6] if d else None, "arm_higher": sum(1 for x in d if x > 0),
                                 "seeds_losing_over_3M": sum(1 for x in d if x < -3e6), "mean_cov_delta_pp": st.mean(c) if c else None,
                                 "deltas_M": [round(x / 1e6, 2) for x in d]}
res["paired"] = pairs
Path(str(PFX) + ".json").write_text(json.dumps(res, indent=1), encoding="utf-8")

L = ["# Final matched-seed comparison (generated by tools/final_comparison.py)", ""]
for name, arms in batches.items():
    L += [f"## {name}", "", "| arm | solved/seeds | failed seeds | profit M (median; min-max) | coverage % | services | assigned/owned | idle | prod. load | profit per assigned k | wall s |",
          "|---|---|---|---|---:|---:|---|---:|---:|---:|---:|"]
    for a in arms:
        if a["solved"]:
            L.append(f"| {a['arm']} | {a['solved']}/{a['seeds']} | {a['failed_seeds'] or '-'} | {a['profit_M']:.2f} ({a['profit_median_M']:.2f}; {a['profit_min_max_M'][0]:.1f}-{a['profit_min_max_M'][1]:.1f}) | "
                     f"{a['coverage_pct']:.1f} | {a['services']:.1f} | {a['assigned']:.0f}/{a['owned']:.0f} | {a['idle']:.0f} | {a['productive_load_factor']:.3f} | "
                     f"{a['profit_per_assigned_k']:.0f} | {a['stage_wall_sec_mean']:.0f} |")
        else:
            L.append(f"| {a['arm']} | 0/{a['seeds']} | {a['failed_seeds']} | - | - | - | - | - | - | - | - |")
    L.append("")
L += ["## Paired differences (same batch, both arms solved)", "", "| pair | pairs | mean M | median M | min..max M | arm higher | seeds losing > 3 M | coverage pp |", "|---|---:|---:|---:|---|---:|---:|---:|"]
for k, v in pairs.items():
    if v["pairs"]:
        L.append(f"| {k} | {v['pairs']} | {v['mean_delta_M']:+.2f} | {v['median_delta_M']:+.2f} | {v['min_max_delta_M'][0]:+.1f}..{v['min_max_delta_M'][1]:+.1f} | {v['arm_higher']} | {v['seeds_losing_over_3M']} | {v['mean_cov_delta_pp']:+.1f} |")
    else:
        L.append(f"| {k} | 0 | - | - | - | - | - | - |")
Path(str(PFX) + ".md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
