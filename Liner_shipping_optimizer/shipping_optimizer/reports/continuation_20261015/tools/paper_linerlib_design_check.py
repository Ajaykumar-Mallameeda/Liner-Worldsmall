"""Diagnostic (NOT an acceptance target): evaluate the authors' LINERLIB WorldSmall solution under the paper-mode accounting.

The paper (Table 2) reports 32.28 M USD for the LINERLIB World Small solution after it decomposed multi-loop (butterfly) services
into simple services, relaxed the vessel limit to a soft one and re-routed the cargo with its own heuristic MCF.  This script
rebuilds that design from the authors' log (butterflies split into simple cycles; vessels from the paper's design-speed formula),
runs the existing paper-mode evaluator under each interpretation switch and prints the result next to the paper number.  A
variant that lands near it is evidence for that reading of the printed equations, nothing more: the paper's decomposition and
MCF tie-breaking are not specified, the profit horizon is not stated, and the paper's number is never used as a pass/fail target.

usage: python -I paper_linerlib_design_check.py <WorldSmall_Best_Base.log> <upstream data dir> <out.json>
"""
import itertools
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.benchmark.paper_evaluator import evaluate, load_worldsmall_ffe, net_profit  # noqa: E402

LOG, UP, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
PAPER_LINERLIB_M = 32.28

data = load_worldsmall_ffe(ROOT / "data" / "raw" / "WorldSmall")
text = LOG.read_text(encoding="utf8", errors="replace")
blocks = re.split(r"\nservice \d+ service id (\d+)\n", "\nservice 0 service id 0\n" + text.partition("service 0 service id 0")[2].lstrip("\n"))
walks = []
for i in range(1, len(blocks), 2):
    body = blocks[i + 1].split("\nID:")[0]
    cap = int(re.search(r"capacity (\d+)", body).group(1))
    pts = re.findall(r"^\d+\t(\w+)\t", body, flags=re.M)
    walks.append((cap, pts))


def simple_cycles(walk):
    """Split a closed walk (cyclic port sequence) into simple cycles at repeated ports."""
    stack, out = [], []
    for p in list(walk) + [walk[0]]:
        if p in stack:
            j = stack.index(p)
            cyc = stack[j:]
            if len(cyc) >= 2:
                out.append(cyc)
            stack = stack[:j + 1]
        else:
            stack.append(p)
    rest = stack[:-1] if len(stack) > 1 and stack[-1] == stack[0] else stack
    if len(rest) >= 2 and not out:
        out.append(rest)
    return out


design, n_butterfly = [], 0
for cap, pts in walks:
    cyc = simple_cycles(pts)
    if len(cyc) > 1:
        n_butterfly += 1
    for c in cyc:
        design.append({"ports": c, "capacity": float(cap)})
print(f"{len(walks)} logged services -> {len(design)} simple services ({n_butterfly} multi-loop services decomposed)")


def with_demand(path, fixed):
    d = pd.read_csv(path, sep="\t")
    dd = load_worldsmall_ffe(ROOT / "data" / "raw" / "WorldSmall")
    dd.demands = [{"o": r.Origin, "d": r.Destination, "ffe": float(r.FFEPerWeek), "rev": float(r.Revenue_1)} for r in d.itertuples()
                  if r.Origin != r.Destination]
    return dd


variants = {"fixed_sep_138247": with_demand(ROOT / "data" / "raw" / "WorldSmall" / "Demand_WorldSmall_Fixed_Sep.csv", True),
            "unfixed_upstream_128281": with_demand(UP / "Demand_WorldSmall.csv", False)}
rows = []
for dname, dd in variants.items():
    for vb, cb, cap_b, port_b in itertools.product(("per_rotation", "per_vessel"), ("per_rotation", "per_vessel"),
                                                  ("per_departure", "per_vessel"), ("capacity",)):
        try:
            r = evaluate(dd, design, voyage_basis=vb, canal_basis=cb, capacity_basis=cap_b, port_variable_basis=port_b)
        except KeyError as exc:
            rows.append({"demand": dname, "voyage": vb, "canal": cb, "capacity": cap_b, "error": f"KeyError {exc}"})
            continue
        p = net_profit(r, 600.0)
        rows.append({"demand": dname, "voyage": vb, "canal": cb, "capacity": cap_b, "profit_usd": p, "profit_M": p / 1e6,
                     "coverage": r["coverage"], "rejected_ffe": r["rejected_ffe"], "vessels_used": r["vessels_used"],
                     "revenue_M": r["revenue"] / 1e6, "handling_M": r["handling_and_transshipment"] / 1e6,
                     "penalty_M": r["rejected_penalty"] / 1e6, "fuel_t": r["fuel_tonnes_per_week"],
                     "voyage_M_without_fuel": r["voyage_cost_without_fuel"] / 1e6, "service_M": r["vessel_service_cost"] / 1e6,
                     "unused_M": r["unused_vessel_profit"] / 1e6, "canal_unknown_transits": r["canal_fee_unknown_transits"],
                     "ratio_to_paper": p / 1e6 / PAPER_LINERLIB_M})
OUT.write_text(json.dumps({"paper_table2_linerlib_M": PAPER_LINERLIB_M, "logged_services": len(walks), "simple_services": len(design),
                           "multi_loop_decomposed": n_butterfly, "rows": rows}, indent=1), encoding="utf-8")
for r in rows:
    if "error" in r:
        print(r)
    else:
        print(f"{r['demand']:26s} voyage={r['voyage']:13s} canal={r['canal']:13s} cap={r['capacity']:13s} profit={r['profit_M']:9.2f} M  "
              f"(x{r['ratio_to_paper']:.2f} of the paper's {PAPER_LINERLIB_M}) cov={r['coverage']:.3f}")
