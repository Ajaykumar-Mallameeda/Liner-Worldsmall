"""End-to-end comparison table from recorded orchestrator artifacts.

usage: python -I final_tables.py <runs_dir> <out.md> <group>=<label>,<label>,... [<group>=...]

Each column is a group of runs (mean over its runs; min..max in a second table). Every
number comes from the run's own ``pipeline_output.json`` (the verified network ledger),
nothing is recomputed here.
"""
import json
import statistics as st
import sys
from pathlib import Path

RUNS, OUT = Path(sys.argv[1]), Path(sys.argv[2])
groups = []
for arg in sys.argv[3:]:
    name, _, labels = arg.partition("=")
    groups.append((name, [x for x in labels.split(",") if x]))


def load(label):
    d = json.loads((RUNS / f"{label}.pipeline_output.json").read_text(encoding="utf-8"))
    nl = d["network_ledger"]
    w = nl["weekly_usd"]
    dm = nl["demand_teu_per_week"]
    assum = nl.get("assumptions", {})
    meta = (RUNS / f"{label}.meta.txt").read_text(encoding="utf-8", errors="replace")
    elapsed = next((float(l.split(":")[1]) for l in meta.splitlines() if l.startswith("elapsed_s")), None)
    log = (RUNS / f"{label}.log").read_text(encoding="utf-8", errors="replace")
    import re
    sc = re.search(r"Passed\s*:\s*(\d+)/(\d+)", log)
    return {
        "profit": w["operating_profit"], "margin": 100 * (w.get("profit_margin_on_revenue") or 0),
        "coverage": dm["coverage_pct"], "served": dm["served"], "demand": dm["total"],
        "services": nl["services"]["operated"],
        "vessels": sum(v.get("used", 0) for v in nl["fleet_by_class"].values()),
        "fuel": w["fuel_cost"], "revenue": w["revenue"], "total_cost": w["total_operating_cost"],
        "candidates": nl["services"]["candidates_offered"],
        "global_stage_s": nl.get("runtime_sec"), "pipeline_s": d["summary_metrics"].get("total_runtime"),
        "elapsed_s": elapsed, "violations": len(nl.get("violations") or []),
        "verified": bool(nl.get("verified")), "milp": nl.get("status"),
        "assertions": f"{sc.group(1)}/{sc.group(2)}" if sc else "",
        "bound": (nl.get("optimality") or {}).get("relaxation_upper_bound_usd_per_week"),
    }


data = {n: [load(l) for l in ls] for n, ls in groups}
rows = [
    ("Verified weekly profit (USD)", "profit", "{:,.0f}"),
    ("Profit margin on revenue (%)", "margin", "{:.1f}"),
    ("Cargo coverage (% of demand)", "coverage", "{:.1f}"),
    ("Unique served TEU / week", "served", "{:,.0f}"),
    ("Selected services", "services", "{:.1f}"),
    ("Vessels deployed", "vessels", "{:.0f}"),
    ("Fuel cost per week (USD)", "fuel", "{:,.0f}"),
    ("Candidate count (modelled pool)", "candidates", "{:,.0f}"),
    ("Global-stage runtime (s)", "global_stage_s", "{:.0f}"),
    ("Whole pipeline runtime (s)", "pipeline_s", "{:.0f}"),
    ("Ledger violations (sum)", "violations", "{:.0f}"),
]
L = ["| Metric | " + " | ".join(f"{n} (n={len(data[n])})" for n, _ in groups) + " |",
     "|---|" + "---:|" * len(groups)]
for title, key, fmt in rows:
    cells = []
    for n, _ in groups:
        vals = [r[key] for r in data[n] if r[key] is not None]
        if not vals:
            cells.append("n/a")
        elif key == "violations":
            cells.append(fmt.format(sum(vals)))
        else:
            cells.append(fmt.format(st.mean(vals)))
    L.append(f"| {title} | " + " | ".join(cells) + " |")
L += ["", "Per-run weekly profit (USD) / coverage (%) / assertions:", ""]
for n, ls in groups:
    L.append(f"* **{n}**: " + "; ".join(
        f"`{l}` {r['profit']:,.0f} / {r['coverage']:.1f}% / {r['assertions']} (verified {r['verified']}, MILP {r['milp']})"
        for l, r in zip(ls, data[n])))
OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
