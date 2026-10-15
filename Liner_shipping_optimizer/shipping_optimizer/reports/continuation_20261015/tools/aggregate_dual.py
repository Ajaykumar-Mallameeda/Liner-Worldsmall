"""Aggregate the dual-pricing study (T_STUDY=dual).  usage: aggregate_dual.py <outputs_dir> <arm> <out_prefix>"""
import glob, json, re, statistics as st, sys
from pathlib import Path
OUTD, ARM, PFX = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])

def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]: j += 1
        for k in range(i, j + 1): r[o[k]] = (i + j) / 2 + 1
        i = j + 1
    return r

def spearman(a, b):
    if len(a) < 3: return None
    ra, rb = rank(a), rank(b); ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb)); den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else None

rows, per_seed = [], []
for f in sorted(glob.glob(str(OUTD / f"{ARM}_seed*.json")), key=lambda p: int(re.search(r"seed(\d+)", p).group(1))):
    d = json.load(open(f)); r = d["runs"][0]; s = r.get("study") or {}
    if not s.get("available") or not s.get("evaluated"): continue
    ev = [e for e in s["evaluated"] if e.get("actual_delta_bound_usd_per_week") is not None and e.get("value_usd_per_week") is not None]
    per_seed.append({"seed": d["seed"], "rejected": s["rejected_distinct"], "priced_positive": s["priced_positive"], "evaluated": len(ev),
                     "spearman_dual_vs_actual": spearman([e["value_usd_per_week"] for e in ev], [e["actual_delta_bound_usd_per_week"] for e in ev]),
                     "spearman_standalone_vs_actual": spearman([e["standalone_usd_per_week"] for e in ev], [e["actual_delta_bound_usd_per_week"] for e in ev])})
    for e in ev: rows.append({**e, "seed": d["seed"]})
def grp(tag):
    g = [e for e in rows if tag in e["selected_by"]]
    return {"n": len(g), "mean_actual_dLP_M": st.mean(e["actual_delta_bound_usd_per_week"] for e in g) / 1e6 if g else None,
            "share_positive": sum(1 for e in g if e["actual_delta_bound_usd_per_week"] > 1e3) / len(g) if g else None,
            "mean_dual_price_M": st.mean(e["value_usd_per_week"] for e in g) / 1e6 if g else None,
            "max_actual_dLP_M": max(e["actual_delta_bound_usd_per_week"] for e in g) / 1e6 if g else None}
out = {"arm": ARM, "seeds": [p["seed"] for p in per_seed], "per_seed": per_seed, "by_selection": {t: grp(t) for t in ("dual_top", "standalone_top", "random")},
       "all_evaluated": len(rows), "actual_increment_negative_share": sum(1 for e in rows if e["actual_delta_bound_usd_per_week"] < -1e3) / len(rows) if rows else None,
       "spearman_dual_vs_actual_pooled": spearman([e["value_usd_per_week"] for e in rows], [e["actual_delta_bound_usd_per_week"] for e in rows]),
       "spearman_standalone_vs_actual_pooled": spearman([e["standalone_usd_per_week"] for e in rows], [e["actual_delta_bound_usd_per_week"] for e in rows]),
       "note": "actual increment = LP bound of pool + candidate minus the pool's LP bound (one at a time, capped 10-path model); it can be NEGATIVE because a new service can displace "
               "paths inside the per-OD cap. The dual price is an LP-side estimate and is never an integer-plan profit."}
Path(str(PFX) + ".json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "per_seed"}, indent=1)); print(per_seed)
