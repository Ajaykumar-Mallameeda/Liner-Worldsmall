"""Aggregate the multi-cause unserved-demand diagnosis (T_STUDY=coverage) over seeds.  usage: aggregate_coverage.py <outputs_dir> <arm> <out_prefix>"""
import glob, json, re, statistics as st, sys
from collections import defaultdict
from pathlib import Path
OUTD, ARM, PFX = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
seeds, rows = [], []
for f in sorted(glob.glob(str(OUTD / f"{ARM}_seed*.json")), key=lambda p: int(re.search(r"seed(\d+)", p).group(1))):
    d = json.load(open(f)); r = d["runs"][0]; s = r.get("study") or {}
    if r["status"] != "feasible" or not s.get("available"):
        continue
    seeds.append(d["seed"]); rows.append((d["seed"], r, s))
n = len(rows)
flags = defaultdict(list); combos = defaultdict(list); unserved = []; overlay_n = []; overlay_v = []; contra = 0
single = []; multi = []
for seed, r, s in rows:
    unserved.append(s["unserved_pct"]); contra += s["contradictions_reopt_should_have_used_path"]
    for k, v in s["flags_not_exclusive"].items(): flags[k].append(v["share_of_total_demand_pct"])
    seen = set()
    sc = mc = 0.0
    for k, v in s["exclusive_combinations"].items():
        combos[k].append(v["share_of_total_demand_pct"]); seen.add(k)
        base = k.split(" | ")[0]
        nflags = 0 if base == "none" else base.count("+") + 1
        if nflags <= 1: sc += v["share_of_total_demand_pct"]
        else: mc += v["share_of_total_demand_pct"]
    single.append(sc); multi.append(mc)
    overlay_n.append(s["targeted_overlay"]["ods"]); overlay_v.append(s["targeted_overlay"]["plausible_value_usd_per_week_sum"])
def m(v): return sum(v) / n if n else None
def pad(v): return list(v) + [0.0] * (n - len(v))
out = {"arm": ARM, "seeds": seeds, "unserved_pct_mean": m(unserved), "unserved_pct_min_max": [min(unserved), max(unserved)] if n else None,
       "flags_not_exclusive_share_pct_mean": {k: m(pad(v)) for k, v in sorted(flags.items())},
       "exclusive_combinations_share_pct_mean": dict(sorted(((k, m(pad(v))) for k, v in combos.items()), key=lambda kv: -kv[1])),
       "ods_with_single_cause_share_pct_mean": m(single), "ods_with_overlapping_causes_share_pct_mean": m(multi),
       "reopt_contradictions_total": contra, "targeted_overlay_ods_mean": m(overlay_n), "targeted_overlay_plausible_value_M_mean": m(overlay_v) / 1e6 if n else None,
       "note": "flags overlap and are NOT additive; exclusive combinations are additive (they sum to the unserved share); the overlay value is an upper-bound-style "
               "margin x unserved TEU that ignores fixed cost, capacity and vessels"}
Path(str(PFX) + ".json").write_text(json.dumps(out, indent=1), encoding="utf-8")
L = [f"# Unserved-demand diagnosis, arm {ARM}, {n} seeds ({seeds})", "", f"unserved share of demand: mean {out['unserved_pct_mean']:.1f} % (min {out['unserved_pct_min_max'][0]:.1f}, max {out['unserved_pct_min_max'][1]:.1f})",
     f"ODs with one cause only: {out['ods_with_single_cause_share_pct_mean']:.1f} % of demand; with overlapping causes: {out['ods_with_overlapping_causes_share_pct_mean']:.1f} %", "",
     "## Causes present (overlapping; share of ALL demand in ODs where the cause applies to at least one path)", "| cause | % of demand |", "|---|---:|"]
L += [f"| {k} | {v:.1f} |" for k, v in sorted(out["flags_not_exclusive_share_pct_mean"].items(), key=lambda kv: -kv[1])]
L += ["", "## Exclusive combinations (additive; sum = unserved share)", "| combination | % of demand |", "|---|---:|"]
L += [f"| {k} | {v:.1f} |" for k, v in list(out["exclusive_combinations_share_pct_mean"].items())[:14]]
L += ["", f"flow re-optimisation contradictions (an operated path with room and positive margin that was not used): {contra}",
      f"ODs with an excluded positive-margin path: {out['targeted_overlay_ods_mean']:.0f} per seed (margin x unserved TEU = {out['targeted_overlay_plausible_value_M_mean']:.1f} M/week, an upper-bound-style figure)"]
Path(str(PFX) + ".md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
