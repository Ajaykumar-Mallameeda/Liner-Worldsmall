"""Per-iteration profit / coverage / services of orchestrator runs and which iteration was selected.
usage: python -I iteration_table.py "<glob>" """
import glob
import json
import os
import sys

for f in sorted(glob.glob(sys.argv[1])):
    name = os.path.basename(f).split(".")[0]
    d = json.load(open(f, encoding="utf-8"))
    sel = d.get("final_selected_iteration")
    cards = (d.get("iteration_selection") or {}).get("scorecards") or []
    parts = []
    for c in cards:
        parts.append("it%s%s: %.2f M, %.1f %%, margin %s" % (
            c.get("iteration"), "*" if c.get("iteration") == sel else "",
            (c.get("weekly_profit") or 0) / 1e6, c.get("global_demand_weighted_coverage") or 0,
            "n/a" if c.get("profit_margin_pct") is None else "%.1f" % c["profit_margin_pct"]))
    print(f"{name:26s} " + " | ".join(parts))
