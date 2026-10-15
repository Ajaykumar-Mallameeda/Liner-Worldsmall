"""Paired comparison of one experimental arm against its concurrent control, with the predeclared retention criteria.

usage: python -I paired_report.py <per_seed.csv> <control_arm> <arm> <out.json> [--min-mean 0.5e6] [--min-higher 14] [--max-loss 3e6]
                                      [--min-cov-delta -0.5] [--max-wall 125]
Every seed present in either arm is listed; a seed missing or not solved in one arm is reported as such (never dropped from the
count).  Differences are over the seeds where BOTH arms produced a valid plan; failures are counted separately.
"""
import csv
import json
import statistics as st
import sys
from pathlib import Path

CSV, CTRL, ARM, OUT = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
opts = dict(zip(sys.argv[5::2], sys.argv[6::2]))
MIN_MEAN = float(opts.get("--min-mean", 0.5e6))
MIN_HIGHER = int(opts.get("--min-higher", 14))
MAX_LOSS = float(opts.get("--max-loss", 3e6))
MIN_COV = float(opts.get("--min-cov-delta", -0.5))
MAX_WALL = float(opts.get("--max-wall", 125))

rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
by = {(r["arm"], int(r["seed"])): r for r in rows}


def valid(r):
    return r is not None and r.get("status") == "feasible" and r.get("ledger_valid") in ("True", "true", "1") \
        and float(r.get("ledger_violations") or 0) == 0 and float(r.get("transit_violations") or 0) == 0


def f(r, k):
    try:
        return float(r[k])
    except (KeyError, TypeError, ValueError):
        return None


seeds = sorted({s for (a, s) in by if a in (CTRL, ARM)})
per_seed, diffs, covd, fails = [], [], [], []
for s in seeds:
    c, a = by.get((CTRL, s)), by.get((ARM, s))
    row = {"seed": s, "control_status": c and c["status"], "arm_status": a and a["status"]}
    if valid(c) and valid(a):
        d = f(a, "profit_usd_wk") - f(c, "profit_usd_wk")
        row.update({"control_profit": f(c, "profit_usd_wk"), "arm_profit": f(a, "profit_usd_wk"), "delta": d,
                    "control_cov": f(c, "coverage_pct"), "arm_cov": f(a, "coverage_pct"),
                    "cov_delta": f(a, "coverage_pct") - f(c, "coverage_pct"),
                    "arm_wall": f(a, "stage_wall_sec"), "control_wall": f(c, "stage_wall_sec")})
        diffs.append(d)
        covd.append(row["cov_delta"])
    else:
        fails.append({"seed": s, "control": row["control_status"], "arm": row["arm_status"]})
        if valid(c) is False and c is not None:
            pass
    per_seed.append(row)
n = len(diffs)
arm_failed_where_control_ok = [x for x in fails if x["control"] == "feasible" and x["arm"] != "feasible"]
walls = [r["arm_wall"] for r in per_seed if r.get("arm_wall") is not None]
res = {"control": CTRL, "arm": ARM, "seeds_listed": len(seeds), "seeds_compared": n, "failures_or_missing": fails,
       "mean_delta": st.mean(diffs) if diffs else None, "median_delta": st.median(diffs) if diffs else None,
       "sd_delta": st.pstdev(diffs) if len(diffs) > 1 else None, "min_delta": min(diffs) if diffs else None,
       "max_delta": max(diffs) if diffs else None, "higher_in_arm": sum(1 for d in diffs if d > 0),
       "seeds_losing_more_than_max_loss": [r["seed"] for r in per_seed if r.get("delta") is not None and r["delta"] < -MAX_LOSS],
       "mean_cov_delta_pp": st.mean(covd) if covd else None, "max_arm_wall_sec": max(walls) if walls else None,
       "per_seed": per_seed}
crit = {
    "all_compared_seeds_valid_and_no_arm_failure": (not arm_failed_where_control_ok) and n == len(seeds),
    f"mean_delta>={MIN_MEAN:.0f}": bool(diffs) and res["mean_delta"] >= MIN_MEAN,
    f"higher_in_>={MIN_HIGHER}_of_{len(seeds)}": res["higher_in_arm"] >= MIN_HIGHER,
    f"no_seed_loses_>{MAX_LOSS:.0f}": not res["seeds_losing_more_than_max_loss"],
    f"coverage_delta>={MIN_COV}pp": bool(covd) and res["mean_cov_delta_pp"] >= MIN_COV,
    f"max_wall<={MAX_WALL}s": bool(walls) and res["max_arm_wall_sec"] <= MAX_WALL,
}
res["criteria"] = crit
res["verdict"] = "RETAINED (all predeclared criteria met)" if all(crit.values()) else "NOT RETAINED (" + ", ".join(k for k, v in crit.items() if not v) + ")"
OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps({k: res[k] for k in ("control", "arm", "seeds_compared", "mean_delta", "median_delta", "min_delta", "max_delta", "higher_in_arm",
                                      "seeds_losing_more_than_max_loss", "mean_cov_delta_pp", "failures_or_missing", "verdict")}, indent=1))
for r in per_seed:
    print(r["seed"], r.get("control_status"), r.get("arm_status"), None if r.get("delta") is None else round(r["delta"] / 1e6, 2),
          None if r.get("cov_delta") is None else round(r["cov_delta"], 1))
