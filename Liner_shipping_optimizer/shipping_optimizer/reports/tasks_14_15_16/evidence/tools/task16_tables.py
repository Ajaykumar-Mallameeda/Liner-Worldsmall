"""Task 16 tables from the recorded runs (nothing typed by hand).

usage: python -I task16_tables.py <outputs_dir> <out.md>

Sources: ``T16_seed*_<variant>_<solver>.json`` (variants legacy / exempt_screened / econ_cap /
nofilter; solver highs = production HiGHS backend 600 s, cbc = production CBC 120 s),
``T16prod_cbc*`` / ``T16prod_highs*`` (production economic filter via LINER_REGIONAL_FILTER),
``T16P30_*`` (path cap 30 instead of 10).
"""
import glob
import json
import statistics as st
import sys
from pathlib import Path

d, out = Path(sys.argv[1]), Path(sys.argv[2])


def load(pattern):
    res = {}
    for f in sorted(glob.glob(str(d / pattern))):
        j = json.loads(Path(f).read_text(encoding="utf-8"))
        res[j["seed"]] = (j, j["runs"][0])
    return res


def fm(v, n=2):
    return "n/a" if v is None else f"{v / 1e6:.{n}f}"


seeds = [0, 1, 2, 3, 4]
variants = ["legacy", "exempt_screened", "econ_cap", "nofilter"]
L = ["# Task 16 - candidate-filter experiment (tables generated from recorded runs)", ""]

for solver, title in (("highs", "HiGHS backend, 600 s (proves the optimum of each pool when it can)"),
                      ("cbc", "production CBC strategy (LP restriction), 120 s")):
    L.append(f"## {title}")
    L.append("")
    L.append("| variant | pool (unique cand.) | " + " | ".join(f"seed {s}" for s in seeds)
             + " | mean | sd | paired vs legacy (mean) | seeds better | coverage % | services | vessels | "
               "margin % | violations |")
    L.append("|---|---:|" + "---:|" * len(seeds) + "---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    base = load(f"T16_seed*_legacy_{solver}.json")
    for v in variants:
        runs = load(f"T16_seed*_{v}_{solver}.json")
        vals = [runs[s][1]["ledger"]["profit"] if s in runs and "ledger" in runs[s][1] else None for s in seeds]
        got = [x for x in vals if x is not None]
        pools = [runs[s][0]["pool"]["unique_candidates"] for s in seeds if s in runs]
        cells = []
        for s, x in zip(seeds, vals):
            if x is None:
                cells.append("n/a")
                continue
            r = runs[s][1]["solver"]
            tag = "*" if (solver == "highs" and r["solution_status"] != "optimal") else ""
            cells.append(f"{x / 1e6:.2f}{tag}")
        diffs = [vals[i] - base[s][1]["ledger"]["profit"] for i, s in enumerate(seeds)
                 if vals[i] is not None and s in base]
        led = [runs[s][1]["ledger"] for s in seeds if s in runs and "ledger" in runs[s][1]]
        viol = sum(len(l["violations"]) for l in led)
        L.append(f"| {v} | {st.mean(pools):.0f} | " + " | ".join(cells) + f" | {fm(st.mean(got)) if got else 'n/a'} | "
                 f"{fm(st.stdev(got)) if len(got) > 1 else 'n/a'} | "
                 f"{fm(st.mean(diffs)) if diffs else 'n/a'} | {sum(1 for x in diffs if x > 0)}/{len(diffs)} | "
                 f"{st.mean(l['coverage_pct'] for l in led):.1f} | {st.mean(l['services'] for l in led):.1f} | "
                 f"{st.mean(l['vessels'] for l in led):.0f} | {st.mean(l['margin_pct'] for l in led):.1f} | {viol} |")
    L.append("")
    if solver == "highs":
        L.append("`*` = incumbent at the 600 s limit, not proven optimal (relative gap to the MIP dual bound: "
                 + ", ".join(
                     f"{v} s{s}: {runs_[s][1]['solver'].get('gap_to_bound_pct'):.1f} %"
                     for v in ("econ_cap",) for runs_ in [load(f'T16_seed*_{v}_highs.json')] for s in seeds
                     if s in runs_ and runs_[s][1]["solver"]["solution_status"] != "optimal"
                     and runs_[s][1]["solver"].get("gap_to_bound_pct") is not None) + ").")
        L.append("")

# production-path validation
L.append("## Production code path (`LINER_REGIONAL_FILTER=economic`) vs the harness variant `econ_cap`")
L.append("")
L.append("| seed | pool hash == harness econ_cap | CBC 120 s: profit M | HiGHS 120 s: profit M | HiGHS status | "
         "violations | regional==ledger |")
L.append("|---:|---|---:|---:|---|---:|---|")
pc = load("T16prod_cbc_seed*_prod.json")
ph = load("T16prod_highs_seed*_prod.json")
ec = load("T16_seed*_econ_cap_cbc.json")
for s in seeds:
    same = (s in pc and s in ec and pc[s][0]["pool"]["unique_order_sha256"] == ec[s][0]["pool"]["unique_order_sha256"])
    pcl = pc[s][1].get("ledger", {}).get("profit") if s in pc else None
    phl = ph[s][1].get("ledger", {}).get("profit") if s in ph else None
    v = (len(pc[s][1].get("ledger", {}).get("violations", [])) if s in pc else 0) + \
        (len(ph[s][1].get("ledger", {}).get("violations", [])) if s in ph else 0)
    rv = all(x[s][1].get("regional_reconciliation", {}).get("accounting_verified") for x in (pc, ph) if s in x)
    L.append(f"| {s} | {same} | {fm(pcl)} | {fm(phl)} | {ph[s][1]['solver']['solution_status'] if s in ph else 'n/a'} | {v} | {rv} |")
L.append("")

# path cap sensitivity
L.append("## Path-cap sensitivity (`max_paths_per_od` 10 -> 30), HiGHS 600 s")
L.append("")
L.append("| filter | cap 10 (profit M, per seed) | cap 30 (profit M, per seed) | mean 10 | mean 30 | mean gain |")
L.append("|---|---|---|---:|---:|---:|")
for name, base_pat, p30_pat in (("legacy", "T16_seed*_legacy_highs.json", "T16P30_legacy_seed*_prod.json"),
                                ("economic", "T16_seed*_econ_cap_highs.json", "T16P30_econ_seed*_prod.json")):
    b, p = load(base_pat), load(p30_pat)
    bs = [b[s][1]["ledger"]["profit"] if s in b else None for s in seeds]
    ps = [p[s][1]["ledger"]["profit"] if s in p and "ledger" in p[s][1] else None for s in seeds]
    both = [(x, y) for x, y in zip(bs, ps) if x is not None and y is not None]
    L.append(f"| {name} | {', '.join(fm(x) for x in bs)} | {', '.join(fm(x) for x in ps)} | "
             f"{fm(st.mean([x for x, _ in both])) if both else 'n/a'} | "
             f"{fm(st.mean([y for _, y in both])) if both else 'n/a'} | "
             f"{fm(st.mean([y - x for x, y in both])) if both else 'n/a'} |")
out.write_text("\n".join(L) + "\n", encoding="utf-8")
print("wrote", out)
