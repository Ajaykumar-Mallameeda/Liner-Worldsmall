"""Task 16 summary: per vessel class, what each filter variant does to the candidate pool.

usage: python -I summarize_filter.py <out.md> <json> [<json> ...]

Each JSON is one ``global_stage_experiment.py`` output run with ``T16_FILTER=<variant>`` (so it
carries ``filter_decisions``).  The tables are computed from the per-candidate decision rows;
no number is estimated.
"""
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

out = Path(sys.argv[1])
files = [Path(p) for p in sys.argv[2:]]
runs = []                           # (variant, seed, json)
for f in files:
    j = json.loads(f.read_text(encoding="utf-8"))
    fd = j.get("filter_decisions") or []
    variant = fd[0]["variant"] if fd else "?"
    runs.append((variant, j["seed"], j))

CLASSES = ["Feeder_450", "Feeder_800", "Panamax_1200", "Panamax_2400", "Post_panamax", "Super_panamax"]
L = ["# Task 16 - candidate-filter decisions by vessel class", ""]
variants = sorted({v for v, _, _ in runs})
seeds = sorted({s for _, s, _ in runs})
L.append(f"Variants: {variants}; seeds: {seeds}.  Counts are summed over the three regional problems and "
         f"averaged over seeds.  `legacy_pass` = the production margin guess and corridor test; "
         f"`exempt` = demand-coherent loops (exempt in production); `kept` = survives the variant "
         f"(including the cap).")
L.append("")

for variant in variants:
    L.append(f"## Variant `{variant}`")
    L.append("")
    L.append("| class | generated | exempt loops | legacy pass | legacy reject: margin guess | legacy reject: "
             "no corridor | feasible (canonical) | stand-alone profitable | stand-alone profit mean USD/wk "
             "(non-loop) | kept by this variant |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    sel = [(s, j) for v, s, j in runs if v == variant]
    for cls in CLASSES:
        agg = defaultdict(list)
        for s, j in sel:
            c = Counter()
            profits = []
            for reg in j["filter_decisions"]:
                for r in reg["candidates"]:
                    if r["class"] != cls:
                        continue
                    c["generated"] += 1
                    if r["section"] == "demand_loop":
                        c["exempt"] += 1
                    c[f"legacy_{r['legacy']}"] += 1
                    c["feasible"] += 1 if r["feasible"] else 0
                    sp = r.get("standalone_profit")
                    if sp is not None and sp > 0:
                        c["profitable"] += 1
                    if sp is not None and r["section"] != "demand_loop":
                        profits.append(sp)
                    c["kept"] += 1 if r.get("kept") else 0
            for k in ("generated", "exempt", "legacy_pass", "legacy_margin_guess", "legacy_no_corridor",
                      "feasible", "profitable", "kept"):
                agg[k].append(c[k])
            agg["profit_mean"].append(st.mean(profits) if profits else None)
        def m(k):
            v = [x for x in agg[k] if x is not None]
            return f"{st.mean(v):.1f}" if v else "n/a"
        L.append(f"| {cls} | {m('generated')} | {m('exempt')} | {m('legacy_pass')} | {m('legacy_margin_guess')} | "
                 f"{m('legacy_no_corridor')} | {m('feasible')} | {m('profitable')} | "
                 f"{(st.mean([x for x in agg['profit_mean'] if x is not None]) if any(x is not None for x in agg['profit_mean']) else float('nan')):,.0f} | {m('kept')} |")
    L.append("")
out.write_text("\n".join(L) + "\n", encoding="utf-8")
print("wrote", out)
