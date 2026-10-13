"""CBC vs HiGHS on the same pools: rollback and default configurations, seeds 0-4.
usage: python -I highs_cbc_pairs.py [highs_tag highs_suffix]   (default M8 highs300)"""
import json
import statistics
import sys

tag = sys.argv[1] if len(sys.argv) > 1 else "M8"
suf = sys.argv[2] if len(sys.argv) > 2 else "highs300"


def run(batch, var, s, suffix):
    return json.load(open(f"outputs/{batch}_seed{s}_{var}_{suffix}.json", encoding="utf-8"))["runs"][0]


def m(xs):
    return statistics.mean(xs)


rows = {}
for label, batch, var, suffix in (("CBC 120 s rollback (= frozen B0)", "M7", "RB", "cbc120"),
                                  ("CBC 120 s default", "M7", "D", "cbc120"),
                                  (f"HiGHS rollback ({suf})", tag, "RB", suf),
                                  (f"HiGHS default ({suf})", tag, "D", suf)):
    try:
        rs = [run(batch, var, s, suffix) for s in range(5)]
    except FileNotFoundError:
        continue
    rows[label] = rs
    prof = [r["ledger"]["profit"] / 1e6 for r in rs]
    cov = [r["ledger"]["coverage_pct"] for r in rs]
    gap = [r["solver"].get("gap_to_bound_pct") for r in rs]
    bound = [r["solver"].get("relaxation_bound") for r in rs]
    over = sum(1 for r in rs if r["solver"].get("relaxation_bound") is not None
               and r["ledger"]["profit"] > r["solver"]["relaxation_bound"] + 1.0)
    print("{:38s} profit {:6.2f} M (sd {:.2f}) coverage {:5.1f} % margin {:5.1f} % solve {:5.0f} s  "
          "profit above the capped model's dual bound on {}/5 seeds".format(
              label, m(prof), statistics.pstdev(prof), m(cov),
              m([r["ledger"]["margin_pct"] for r in rs]), m([r["solver"]["runtime_sec"] for r in rs]), over))
    if suffix.startswith("highs"):
        print("   per-seed gap to the capped model's dual bound %:", [None if g is None else round(g, 1) for g in gap])
