"""Markdown tables from ``pool_experiment.py`` output (per configuration, over seeds).

usage: python -I summarize_pool_experiment.py <out.md> <results.json> [<results2.json> ...]

Rows are configurations; every number is the mean over the seeds present for it (the
per-seed values are listed in a second table). Nothing is filtered: all runs found in
the files are used.
"""
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

OUT = Path(sys.argv[1])
runs = []
for f in sys.argv[2:]:
    runs += json.loads(Path(f).read_text(encoding="utf-8"))["runs"]

by = defaultdict(list)
for r in runs:
    by[r["config"]].append(r)
order = []
for r in runs:
    if r["config"] not in order:
        order.append(r["config"])


def mean(rs, key, default=0.0):
    vals = [r.get(key) for r in rs if r.get(key) is not None]
    return st.mean(vals) if vals else default


def sd(rs, key):
    vals = [r.get(key) for r in rs if r.get(key) is not None]
    return st.pstdev(vals) if len(vals) > 1 else 0.0


L = ["| configuration | seeds | pool (unique) | 2-port / 3 / 4 / 5 / 6+ | standalone-profitable | profit USD/wk mean (sd) | min .. max | margin % | coverage % | services | vessels | LP bound M | MILP s | ledger violations |",
     "|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
for cfg in order:
    rs = by[cfg]
    bn = defaultdict(float)
    for r in rs:
        for k, v in r["by_n_ports"].items():
            bn["6+" if int(k) >= 6 else str(k)] += v / len(rs)
    comp = " / ".join(f"{bn.get(k, 0):.0f}" for k in ("2", "3", "4", "5", "6+"))
    profits = [r["profit"] for r in rs if r.get("profit") is not None]
    L.append(
        f"| {cfg} | {len(rs)} | {mean(rs, 'candidates_unique_offered'):.0f} | {comp} | "
        f"{mean(rs, 'standalone_profitable'):.1f} | {mean(rs, 'profit')/1e6:.2f} M ({sd(rs, 'profit')/1e6:.2f}) | "
        f"{min(profits)/1e6:.2f} .. {max(profits)/1e6:.2f} M | {mean(rs, 'margin_pct'):.1f} | "
        f"{mean(rs, 'coverage_pct'):.1f} | {mean(rs, 'n_services'):.1f} | {mean(rs, 'vessels'):.0f} | "
        f"{mean(rs, 'relaxation_bound')/1e6:.1f} | {mean(rs, 'milp_runtime_sec'):.0f} | "
        f"{sum(len(r.get('violations', [])) for r in rs)} |")

seeds = sorted({r["seed"] for r in runs})
L += ["", "Per-seed weekly profit (USD M) and coverage (%):", "",
      "| seed | " + " | ".join(order) + " |", "|---|" + "---:|" * len(order)]
for s in seeds:
    cells = []
    for cfg in order:
        r = next((x for x in by[cfg] if x["seed"] == s), None)
        cells.append("" if r is None else f"{r['profit']/1e6:.2f} / {r['coverage_pct']:.1f}%")
    L.append(f"| {s} | " + " | ".join(cells) + " |")

# paired differences against the first configuration
base = order[0]
L += ["", f"Paired difference in weekly profit vs `{base}` (same seed; USD M; positive = better):", "",
      "| configuration | " + " | ".join(f"seed {s}" for s in seeds) + " | mean | seeds better |",
      "|---|" + "---:|" * (len(seeds) + 2)]
for cfg in order[1:]:
    diffs = []
    for s in seeds:
        a = next((x for x in by[base] if x["seed"] == s), None)
        b = next((x for x in by[cfg] if x["seed"] == s), None)
        diffs.append(None if a is None or b is None else (b["profit"] - a["profit"]) / 1e6)
    valid = [d for d in diffs if d is not None]
    L.append(f"| {cfg} | " + " | ".join("" if d is None else f"{d:+.2f}" for d in diffs) +
             f" | {st.mean(valid):+.2f} | {sum(1 for d in valid if d > 0)}/{len(valid)} |")

# class use
L += ["", "Vessel classes in the operated plan (mean vessels deployed) and classes present in the pool (mean candidates):", ""]
classes = sorted({c for r in runs for c in r.get("vessels_by_class", {})} | {c for r in runs for c in r["by_class"]})
L += ["| configuration | " + " | ".join(f"{c} (deployed / pool)" for c in classes) + " |",
      "|---|" + "---:|" * len(classes)]
for cfg in order:
    rs = by[cfg]
    cells = []
    for c in classes:
        dep = st.mean(r.get("vessels_by_class", {}).get(c, 0) for r in rs)
        pool = st.mean(r["by_class"].get(c, 0) for r in rs)
        cells.append(f"{dep:.1f} / {pool:.0f}")
    L.append(f"| {cfg} | " + " | ".join(cells) + " |")

# where the operated services came from
L += ["", "Operated services by generator section (mean count):", ""]
secs = sorted({s for r in runs for s in r.get("selected_by_section", {})})
L += ["| configuration | " + " | ".join(secs) + " |", "|---|" + "---:|" * len(secs)]
for cfg in order:
    rs = by[cfg]
    L.append(f"| {cfg} | " + " | ".join(
        f"{st.mean(r.get('selected_by_section', {}).get(s, 0) for r in rs):.1f}" for s in secs) + " |")

OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
print(f"wrote {OUT} ({len(runs)} runs, {len(order)} configurations)")
