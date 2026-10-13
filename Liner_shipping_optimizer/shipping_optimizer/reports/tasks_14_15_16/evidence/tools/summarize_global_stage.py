"""Summarise ``global_stage_experiment.py`` outputs (one JSON per seed) as markdown.

usage: python -I summarize_global_stage.py <out.md> <title> <baseline_strategy> <json> [<json> ...]

Tables: per-seed raw metrics for every strategy (nothing is dropped), mean / sd / min / max
per strategy, and the paired difference against ``baseline_strategy`` (same seed, same pool).
Profit is the INDEPENDENT LEDGER's operating profit (the verified figure); ``reconciled`` is
the MILP-objective == ledger check; ``viol`` the number of ledger violations.
"""
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

out, title, base = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
files = [Path(p) for p in sys.argv[4:]]
runs = defaultdict(dict)            # strategy -> seed -> row
pools = {}
order = []
for f in files:
    j = json.loads(f.read_text(encoding="utf-8"))
    seed = j["seed"]
    pools[seed] = j.get("pool", {})
    for r in j["runs"]:
        runs[r["strategy"]][seed] = r
        if r["strategy"] not in order:
            order.append(r["strategy"])
seeds = sorted(pools)


def g(r, *path, default=None):
    cur = r
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def fm(v, d=2):
    return "n/a" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v/1e6:.{d}f}"


def mean_sd(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None, None, None
    return (st.mean(vals), st.stdev(vals) if len(vals) > 1 else 0.0, min(vals), max(vals))


L = [f"# {title}", ""]
L.append(f"Seeds: {seeds}. Pool per seed (unique candidates): "
         + ", ".join(f"{s}: {pools[s].get('unique_candidates')}" for s in seeds)
         + ". Profit = independent-ledger operating profit, USD M / week.")
L.append("")
L.append("## 1. Every run (seed x strategy)")
L.append("")
L.append("| seed | strategy | status | solver | profit M | MILP obj M | reconciled | coverage % | margin % | "
         "services | vessels | bound M | gap to bound % | solve s | wall s | viol | regional==ledger |")
L.append("|---:|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
for strat in order:
    for s in seeds:
        r = runs[strat].get(s)
        if r is None:
            continue
        led, sol = r.get("ledger", {}), r.get("solver", {})
        rec = g(r, "ledger", "reconciliation", "reconciled")
        L.append(
            f"| {s} | {strat} | {r.get('status')} | {sol.get('solution_status')} | "
            f"{fm(led.get('profit'))} | {fm(sol.get('objective_usd_per_week'))} | {rec} | "
            f"{(led.get('coverage_pct') or float('nan')):.1f} | "
            f"{(led.get('margin_pct') if led.get('margin_pct') is not None else float('nan')):.1f} | "
            f"{led.get('services')} | {led.get('vessels')} | {fm(sol.get('relaxation_bound'), 1)} | "
            f"{(sol.get('gap_to_bound_pct') if sol.get('gap_to_bound_pct') is not None else float('nan')):.1f} | "
            f"{sol.get('runtime_sec')} | {r.get('wall_sec_total')} | {len(led.get('violations', []))} | "
            f"{g(r, 'regional_reconciliation', 'accounting_verified')} |")
L.append("")
L.append("## 2. Per-strategy summary over seeds (mean, sd, min .. max)")
L.append("")
L.append("| strategy | n | profit M mean (sd) | min .. max | coverage % | services | vessels | "
         "solve s mean | reconciled | verified (ledger) | usable runs | violations |")
L.append("|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for strat in order:
    rr = [runs[strat][s] for s in seeds if s in runs[strat]]
    prof = [g(r, "ledger", "profit") for r in rr]
    m, sd, lo, hi = mean_sd(prof)
    cov = mean_sd([g(r, "ledger", "coverage_pct") for r in rr])[0]
    svc = mean_sd([g(r, "ledger", "services") for r in rr])[0]
    ves = mean_sd([g(r, "ledger", "vessels") for r in rr])[0]
    t = mean_sd([g(r, "solver", "runtime_sec") for r in rr])[0]
    rec = sum(1 for r in rr if g(r, "ledger", "reconciliation", "reconciled"))
    ok = sum(1 for r in rr if r.get("ok"))
    usable = sum(1 for r in rr if g(r, "ledger", "profit") is not None)
    viol = sum(len(g(r, "ledger", "violations", default=[])) for r in rr)
    L.append(f"| {strat} | {len(rr)} | {fm(m)} ({fm(sd)}) | {fm(lo)} .. {fm(hi)} | "
             f"{cov if cov is not None else float('nan'):.1f} | {svc if svc is not None else float('nan'):.1f} | "
             f"{ves if ves is not None else float('nan'):.0f} | {t if t is not None else float('nan'):.0f} | "
             f"{rec}/{len(rr)} | {ok}/{len(rr)} | {usable}/{len(rr)} | {viol} |")
L.append("")
L.append(f"## 3. Paired difference in ledger profit vs `{base}` (same seed, same pool; USD M; + = better)")
L.append("")
hdr = "| strategy | " + " | ".join(f"seed {s}" for s in seeds) + " | mean | seeds better |"
L.append(hdr)
L.append("|---|" + "---:|" * (len(seeds) + 2))
for strat in order:
    if strat == base:
        continue
    diffs = []
    cells = []
    for s in seeds:
        a, b = g(runs[strat].get(s, {}), "ledger", "profit"), g(runs[base].get(s, {}), "ledger", "profit")
        if a is None or b is None:
            cells.append("n/a")
        else:
            diffs.append(a - b)
            cells.append(f"{(a - b) / 1e6:+.2f}")
    L.append(f"| {strat} | " + " | ".join(cells) + f" | {fm(st.mean(diffs)) if diffs else 'n/a'} | "
             f"{sum(1 for d in diffs if d > 0)}/{len(diffs)} |")
L.append("")
L.append("## 4. Solver diagnostics")
L.append("")
L.append("| seed | strategy | services considered | in integer problem | variables | constraints | paths | notes |")
L.append("|---:|---|---:|---:|---:|---:|---:|---|")
for strat in order:
    for s in seeds:
        r = runs[strat].get(s)
        if r is None:
            continue
        sol = r.get("solver", {})
        note = json.dumps(r.get("diag", {}), default=str)[:160]
        L.append(f"| {s} | {strat} | {sol.get('services_considered')} | {sol.get('services_in_integer_problem')} | "
                 f"{sol.get('variables')} | {sol.get('constraints')} | {sol.get('paths')} | {note} |")
out.write_text("\n".join(L) + "\n", encoding="utf-8")
print("wrote", out)
