"""Markdown per-seed rows for a paired batch (baseline variant vs candidate variant).
usage: python -I paired_rows.py <batch> <base_variant> <cand_variant> <suffix> <seeds e.g. 0-9>"""
import json
import statistics
import sys

batch, a, b, suffix, rng = sys.argv[1:6]
lo, hi = (int(x) for x in rng.split("-"))
rows, dp, dc = [], [], []
print("| seed | " + a + " profit M | " + b + " profit M | Δ profit M | " + a + " coverage % | " + b +
      " coverage % | Δ coverage pp | " + b + " services / vessels | re-routing gain M | ledger viol. |")
print("|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|")
for s in range(lo, hi + 1):
    ra = json.load(open(f"outputs/{batch}_seed{s}_{a}_{suffix}.json", encoding="utf-8"))["runs"][0]
    rb = json.load(open(f"outputs/{batch}_seed{s}_{b}_{suffix}.json", encoding="utf-8"))["runs"][0]
    la, lb = ra["ledger"], rb["ledger"]
    fr = (lb.get("reconciliation") or {}).get("flow_reoptimisation") or {}
    dp.append((lb["profit"] - la["profit"]) / 1e6)
    dc.append(lb["coverage_pct"] - la["coverage_pct"])
    print("| {} | {:.2f} | {:.2f} | {:+.2f} | {:.1f} | {:.1f} | {:+.1f} | {} / {} | {:.2f} | {} |".format(
        s, la["profit"] / 1e6, lb["profit"] / 1e6, dp[-1], la["coverage_pct"], lb["coverage_pct"], dc[-1],
        lb["services"], lb["vessels"], (fr.get("gain_usd") or 0) / 1e6, len(la["violations"]) + len(lb["violations"])))
print("| **mean (sd)** | | | **{:+.2f}** ({:.2f}) | | | **{:+.1f}** ({:.1f}) | | | |".format(
    statistics.mean(dp), statistics.stdev(dp), statistics.mean(dc), statistics.stdev(dc)))
