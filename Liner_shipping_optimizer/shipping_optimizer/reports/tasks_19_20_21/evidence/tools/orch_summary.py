"""One line per orchestrator run: assertions, profit, margin, coverage, services, vessels, re-optimisation.
usage: python -I orch_summary.py "<glob>" """
import glob
import json
import os
import sys

for f in sorted(glob.glob(sys.argv[1])):
    name = os.path.basename(f).split(".")[0]
    d = json.load(open(f, encoding="utf-8"))
    nl = d["network_ledger"]
    sc = d.get("test_scorecard") or {}
    fr = (nl.get("optimality") or {}).get("flow_reoptimisation") or {}
    rp = fr.get("repair") or {}
    w = nl["weekly_usd"]
    sr = nl.get("strategy_report") or {}
    bs = sr.get("by_strategy") or {}
    mh = bs.get("multi_hop", {}).get("served_teu")
    print(f"{name:26s} {d['status']:9s} {sc.get('assertions_passed')}/{sc.get('assertions_total')} "
          f"profit {w['operating_profit'] / 1e6:6.2f} M margin {w['profit_margin_on_revenue'] * 100:5.1f} % "
          f"cov {nl['demand_teu_per_week']['coverage_pct']:5.2f} % svc {nl['services']['operated']:2d} "
          f"ves {sum(v['used'] for v in nl['fleet_by_class'].values()):3d} "
          f"maxT {nl['assumptions'].get('max_transfers_per_od')} milp {nl['optimality']['milp_status']:9s} "
          f"reopt {'Y' if fr.get('applied') else 'n'} {(fr.get('gain_usd') or 0) / 1e6:5.2f} M "
          f"repair {'Y' if rp.get('applied') else 'n'} viol {len(nl['violations'])} "
          f"mhTEU {0 if mh is None else round(mh)} iter {d.get('final_selected_iteration')}")
