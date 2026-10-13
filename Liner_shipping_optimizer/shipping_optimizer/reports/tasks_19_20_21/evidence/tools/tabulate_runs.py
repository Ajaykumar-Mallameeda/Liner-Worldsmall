"""Tabulate controlled-experiment outputs (one JSON per seed x variant) as a paired table.

usage: python -I tabulate_runs.py "<glob>" [--md out.md] [--base B0]
The variant name is the third '_'-separated field of the file name (TAG_seedN_VARIANT_solverTL).
Prints, per seed, profit / coverage / services / vessels of each variant, then mean (sd), the
paired difference against ``--base`` and the number of seeds on which a variant is better.
"""
import collections
import glob
import json
import statistics
import sys
from pathlib import Path

args = sys.argv[1:]
pattern = args[0]
md = args[args.index("--md") + 1] if "--md" in args else None
base = args[args.index("--base") + 1] if "--base" in args else "B0"

rows = collections.defaultdict(dict)
for f in sorted(glob.glob(pattern)):
    name = Path(f).name[:-5]
    parts = name.split("_")
    var = parts[2]
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    seed = int(d["seed"])
    r = d["runs"][0]
    led = r.get("ledger") or {}
    s = r.get("solver") or {}
    sr = r.get("strategy_report") or {}
    util = (sr.get("utilisation") or {}).get("network") or {}
    rows[var][seed] = dict(
        profit=led.get("profit"), cov=led.get("coverage_pct"), rev=led.get("revenue"),
        cost=led.get("total_cost"), margin=led.get("margin_pct"), teu=led.get("served_teu"),
        svc=led.get("services"), ves=led.get("vessels"), viol=len(led.get("violations", [])),
        status=r.get("status"), sol=s.get("solution_status"), vars=s.get("variables"),
        paths=r.get("paths_total"), gap=s.get("gap_to_bound_pct"), sec=s.get("runtime_sec"),
        lf=util.get("load_factor"), recon=((led.get("reconciliation") or {}).get("reconciled")),
        valid=led.get("valid"))
variants = sorted(rows, key=lambda v: (v != base, v))
seeds = sorted({s for v in rows.values() for s in v})
out = []


def p(line=""):
    print(line)
    out.append(line)


p("| seed | " + " | ".join(variants) + " |")
p("|---:|" + "|".join(["---:"] * len(variants)) + "|")
for s in seeds:
    cells = []
    for v in variants:
        x = rows[v].get(s)
        cells.append("" if not x or x["profit"] is None
                     else f"{x['profit'] / 1e6:.2f} M ({x['cov']:.1f} %, {x['svc']} svc)")
    p(f"| {s} | " + " | ".join(cells) + " |")
p()
p("| variant | n | profit M/wk mean (sd) | paired vs " + base + " | seeds better | coverage % | served TEU | "
  "revenue M | cost M | margin % | services | vessels | paths | model vars | load factor | "
  "violations | reconciled |")
p("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for v in variants:
    seeds_v = [s for s in seeds if s in rows[v] and rows[v][s]["profit"] is not None]
    if not seeds_v:
        continue

    def col(k):
        vals = [rows[v][s][k] for s in seeds_v if rows[v][s][k] is not None]
        return statistics.mean(vals) if vals else float("nan")
    pr = [rows[v][s]["profit"] for s in seeds_v]
    paired = [rows[v][s]["profit"] - rows[base][s]["profit"] for s in seeds_v
              if s in rows.get(base, {}) and rows[base][s]["profit"] is not None]
    better = sum(1 for x in paired if x > 0)
    sd = statistics.pstdev(pr) if len(pr) > 1 else 0.0
    viol = sum(rows[v][s]["viol"] for s in seeds_v)
    rec = sum(1 for s in seeds_v if rows[v][s]["recon"])
    p(f"| {v} | {len(seeds_v)} | {statistics.mean(pr) / 1e6:.2f} ({sd / 1e6:.2f}) | "
      f"{(statistics.mean(paired) / 1e6 if paired else float('nan')):+.2f} | {better}/{len(paired)} | "
      f"{col('cov'):.1f} | {col('teu'):,.0f} | {col('rev') / 1e6:.1f} | {col('cost') / 1e6:.1f} | "
      f"{col('margin'):.1f} | {col('svc'):.1f} | {col('ves'):.0f} | {col('paths'):,.0f} | "
      f"{col('vars'):,.0f} | {col('lf'):.3f} | {viol} | {rec}/{len(seeds_v)} |")
if md:
    Path(md).write_text("\n".join(out) + "\n", encoding="utf-8")
