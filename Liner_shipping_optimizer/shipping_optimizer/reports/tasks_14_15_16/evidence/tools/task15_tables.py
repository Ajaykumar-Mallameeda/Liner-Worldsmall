"""Compose the Task 15 headline tables from the recorded experiment JSON files.

usage: python -I task15_tables.py <outputs_dir> <out.md>

Sources (all in ``outputs_dir``; every number is read from them, nothing is typed in):
    T15_B0matrix_seed*.json      baseline tree B0, strategies prod / fullint / two:40 / two:60
                                 (its A_sa / A_pert rows are INVALID - harness status bug, kept)
    T15_highs600_seed*.json      baseline tree B0, HiGHS 600 s (the proven optimum of the pool)
    T15_clean_cbc_seed*_*.json   patched tree, CBC strategies, concurrency cap 4
    T15_clean_highsprod_seed*.json  patched tree, production HiGHS backend, 120 s
    T15_prog_seed*_*.json        patched tree, progressive restricted CBC
"""
import glob
import json
import statistics as st
import sys
from pathlib import Path

d, out = Path(sys.argv[1]), Path(sys.argv[2])


def load(pattern):
    rows = []
    for f in sorted(glob.glob(str(d / pattern))):
        j = json.loads(Path(f).read_text(encoding="utf-8"))
        for r in j["runs"]:
            rows.append((j["seed"], r, j))
    return rows


def pick(rows, strategy):
    return {s: r for s, r, _ in rows if r["strategy"] == strategy}


def profit(r):
    return None if r is None else r.get("ledger", {}).get("profit")


def f(v, nd=2):
    return "n/a" if v is None else f"{v / 1e6:.{nd}f}"


def stats(vals):
    v = [x for x in vals if x is not None]
    return (st.mean(v), st.stdev(v) if len(v) > 1 else 0.0, min(v), max(v)) if v else (None,) * 4


b0 = load("T15_B0matrix_seed*.json")
opt = pick(load("T15_highs600_seed*.json"), "highs")
cbc = load("T15_clean_cbc_seed*_*.json")
hp = pick(load("T15_clean_highsprod_seed*.json"), "prod")
prog = load("T15_prog_seed*_*.json")
seeds = sorted(opt)
prod_b0 = pick(b0, "prod")
prod_p = pick(cbc, "prod")

L = ["# Task 15 - solver strategy comparison (tables generated from recorded runs)", ""]
L.append("## 1. Proven optimum of each pool vs what the production strategy realises")
L.append("")
L.append("Optimum = unrestricted integer problem solved by HiGHS to a proven relative gap <= 1e-4 "
         "(`T15_highs600`). Production = LP relaxation -> restriction to its support -> CBC, 120 s. All "
         "values are independent-ledger operating profit, USD M / week.")
L.append("")
L.append("| seed | proven optimum | gap to bound at stop | production CBC (B0) | % of optimum | "
         "reconciled (B0) | production CBC (patched) | HiGHS backend 120 s | % of optimum |")
L.append("|---:|---:|---:|---:|---:|---|---:|---:|---:|")
for s in seeds:
    o = opt[s]
    po = profit(o)
    gap = o["solver"].get("gap_to_bound_pct")
    pb = prod_b0.get(s)
    pp = prod_p.get(s)
    ph = hp.get(s)
    rec = pb.get("ledger", {}).get("reconciliation", {}).get("reconciled") if pb else None
    L.append(f"| {s} | {f(po)} | {gap:.3f} % | {f(profit(pb))} | "
             f"{100 * profit(pb) / po:.1f} | {rec} | {f(profit(pp))} | {f(profit(ph))} | "
             f"{100 * profit(ph) / po:.1f} |")
m = lambda rows: stats([profit(rows.get(s)) for s in seeds])        # noqa: E731
mo, mb, mp, mh = m(opt), m(prod_b0), m(prod_p), m(hp)
L.append(f"| **mean (sd)** | **{f(mo[0])}** ({f(mo[1])}) | | **{f(mb[0])}** ({f(mb[1])}) | "
         f"{100 * mb[0] / mo[0]:.1f} | | **{f(mp[0])}** ({f(mp[1])}) | **{f(mh[0])}** ({f(mh[1])}) | "
         f"{100 * mh[0] / mo[0]:.1f} |")
L.append("")
L.append("## 2. All strategies, 5 paired seeds (same pool per seed), 120 s unless stated")
L.append("")
L.append("| strategy | tree | solver | n | mean M | sd | min .. max | vs production CBC (paired, mean M) "
         "| seeds better | reconciled | solve s | ledger violations |")
L.append("|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|")


def row(label, tree, solver, rows_by_seed, base_by_seed):
    vals = [profit(rows_by_seed.get(s)) for s in seeds]
    mean, sd, lo, hi = stats(vals)
    diffs = [vals[i] - profit(base_by_seed.get(s)) for i, s in enumerate(seeds)
             if vals[i] is not None and profit(base_by_seed.get(s)) is not None]
    rr = [rows_by_seed.get(s) for s in seeds]
    rec = sum(1 for r in rr if r and r.get("ledger", {}).get("reconciliation", {}).get("reconciled"))
    t = stats([r["solver"]["runtime_sec"] for r in rr if r and "solver" in r])[0]
    viol = sum(len(r.get("ledger", {}).get("violations", [])) for r in rr if r)
    n_ok = sum(1 for v in vals if v is not None)
    L.append(f"| {label} | {tree} | {solver} | {n_ok}/{len(seeds)} | {f(mean)} | {f(sd)} | "
             f"{f(lo)} .. {f(hi)} | {f(st.mean(diffs)) if diffs else 'n/a'} | "
             f"{sum(1 for x in diffs if x > 0)}/{len(diffs)} | {rec}/{n_ok} | "
             f"{t:.0f} | {viol} |" if t is not None else
             f"| {label} | {tree} | {solver} | {n_ok}/{len(seeds)} | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |")


row("prod (production)", "B0", "CBC LP-guided", prod_b0, prod_b0)
row("fullint (unrestricted)", "B0", "CBC", pick(b0, "fullint"), prod_b0)
row("two:40", "B0", "CBC", pick(b0, "two:40"), prod_b0)
row("two:60", "B0", "CBC", pick(b0, "two:60"), prod_b0)
row("prod + vessel trim (patch A)", "T15A", "CBC LP-guided", prod_p, prod_b0)
for name in ("A_sa", "A_pert", "A_top120", "A_top60"):
    row(name, "T15A", "CBC", pick(cbc, name), prod_p)
for name in sorted({r["strategy"] for _, r, _ in prog}):
    row(name, "T15A", "CBC progressive", pick(prog, name), prod_p)
row("HiGHS backend (patch B), 120 s", "T15AB", "HiGHS unrestricted", hp, prod_p)
row("HiGHS 600 s (reference optimum)", "B0 pool", "HiGHS unrestricted", opt, prod_p)
L.append("")
L.append("## 3. Time to proven optimality and bounds (HiGHS 600 s reference)")
L.append("")
L.append("| seed | optimum M | dual bound M | gap % | solve s | services | vessels | coverage % | margin % |")
L.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for s in seeds:
    o = opt[s]
    sol, led = o["solver"], o["ledger"]
    L.append(f"| {s} | {f(led['profit'])} | {f(sol['relaxation_bound'])} | {sol['gap_to_bound_pct']:.3f} | "
             f"{sol['runtime_sec']} | {led['services']} | {led['vessels']} | {led['coverage_pct']:.1f} | "
             f"{led['margin_pct']:.1f} |")
L.append("")
L.append("## 4. Cost components (USD M / week) - production CBC (patched) vs HiGHS backend, same pools")
L.append("")
L.append("| seed | solver | revenue | vessel hire | fuel | port calls | handling | transshipment | total cost | "
         "profit | served TEU | unserved TEU |")
L.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for s in seeds:
    for lab, rows in (("CBC", prod_p), ("HiGHS", hp)):
        r = rows.get(s)
        if not r:
            continue
        l = r["ledger"]
        L.append(f"| {s} | {lab} | {f(l['revenue'])} | {f(l['vessel_cost'])} | {f(l['fuel_cost'])} | "
                 f"{f(l['port_call_fixed_cost'])} | {f(l['handling_cost'])} | {f(l['transshipment_cost'])} | "
                 f"{f(l['total_cost'])} | {f(l['profit'])} | {l['served_teu']:,.0f} | {l['unserved_teu']:,.0f} |")
out.write_text("\n".join(L) + "\n", encoding="utf-8")
print("wrote", out)
