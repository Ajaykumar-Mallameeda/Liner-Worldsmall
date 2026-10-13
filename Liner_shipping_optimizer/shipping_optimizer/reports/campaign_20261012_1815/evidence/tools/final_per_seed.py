"""(raw_milp_incumbent_est = plan profit minus the local-search, re-routing and idle-prune gains: an estimate of the solver's own incumbent)

Per-seed acceptance CSV for the final report: every plan of the Phase 5 batches with the fields of gates 9.1 - 9.4.

usage: python -I final_per_seed.py <out.csv>
Batches: D5 (seeds 0-9, tree T8), H5 (10-19, T8), C9 (10-19, T9), C9b (10-19, T9).
"""
import csv
import json
import sys
from pathlib import Path

OUT = Path(r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer\reports\campaign_20261012_1815\evidence\outputs")
out = Path(sys.argv[1])
BATCHES = [("D5", range(0, 10), ("base", "ls", "e", "fin")), ("H5", range(10, 20), ("base", "ls", "e", "fin")),
           ("C9", range(10, 20), ("base", "ls", "fin", "lv")), ("C9b", range(10, 20), ("base", "ls", "c1ls", "fin"))]
cols = ["batch", "arm", "seed", "tree", "env", "solver_backend", "cbc_threads", "time_budget_sec", "stage_wall_sec", "solution_status",
        "objective_after_post_milp_usd_wk", "raw_milp_incumbent_est_usd_wk", "plan_profit_usd_wk", "best_bound_usd_wk", "gap_to_bound_pct", "post_milp_change", "ls_applied", "ls_gain_usd",
        "reopt_gain_usd", "idle_pruned", "ledger_valid", "violations", "reconciled", "regional_verified", "margin_pct", "coverage_pct",
        "served_teu", "demand_teu", "services", "vessels", "vessels_by_class", "services_by_class", "load_factor_leg_mean", "load_factor_service_mean",
        "transit_mean_d_max_strategy", "transit_p90_d_max_strategy", "min_slack_to_limit_d", "transit_violations", "teu_0_transfers",
        "teu_1_transfer", "teu_2_transfers", "multi_hop_flows"]
rows = []
for batch, seeds, arms in BATCHES:
    for arm in arms:
        for s in seeds:
            p = OUT / f"{batch}_{arm}_seed{s}.json"
            if not p.exists():
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            r = (d.get("runs") or [None])[-1]
            if not r:
                continue
            led = r.get("ledger") or {}
            rec = led.get("reconciliation") or {}
            sol = r.get("solver") or {}
            sr = r.get("strategy_report") or {}
            bs = sr.get("by_strategy") or {}
            util = sr.get("utilisation") or {}
            ls = rec.get("local_search") or {}
            fr = rec.get("flow_reoptimisation") or {}
            idle = (ls.get("idle_pruned") or {}).get("dropped") or []
            ft = r.get("flow_teu_by_n_transfers") or {}
            rr = r.get("regional_reconciliation") or {}
            rows.append({
                "batch": batch, "arm": arm, "seed": s, "tree": Path(d.get("tree", "")).name, "env": json.dumps(d.get("env") or {}, sort_keys=True),
                "solver_backend": "CBC (PuLP PULP_CBC_CMD, single thread)", "cbc_threads": d.get("cbc_threads"), "time_budget_sec": d.get("time_limit_sec"),
                "stage_wall_sec": r.get("wall_sec_total"), "solution_status": r.get("status"),
                "objective_after_post_milp_usd_wk": sol.get("objective_usd_per_week"),
                "raw_milp_incumbent_est_usd_wk": (led.get("profit") or 0.0) - (ls.get("gain_usd") or 0.0) - (fr.get("gain_usd") or 0.0)
                                                  - sum(x.get("weekly_fixed_cost_usd", 0.0) for x in idle),
                "plan_profit_usd_wk": led.get("profit"),
                "best_bound_usd_wk": sol.get("relaxation_bound"), "gap_to_bound_pct": sol.get("gap_to_bound_pct"),
                "post_milp_change": bool(ls.get("applied") or fr.get("applied") or idle), "ls_applied": ls.get("applied"),
                "ls_gain_usd": ls.get("gain_usd"), "reopt_gain_usd": fr.get("gain_usd"), "idle_pruned": len(idle),
                "ledger_valid": led.get("valid"), "violations": len(led.get("violations") or []), "reconciled": rec.get("reconciled"),
                "regional_verified": rr.get("accounting_verified"), "margin_pct": led.get("margin_pct"), "coverage_pct": led.get("coverage_pct"),
                "served_teu": led.get("served_teu"), "demand_teu": led.get("total_demand_teu"), "services": led.get("services"),
                "vessels": led.get("vessels"), "vessels_by_class": json.dumps(led.get("vessels_by_class") or {}, sort_keys=True),
                "services_by_class": json.dumps(led.get("services_by_class") or {}, sort_keys=True),
                "load_factor_leg_mean": (util.get("leg") or {}).get("load_factor_mean"),
                "load_factor_service_mean": (util.get("service") or {}).get("load_factor_mean"),
                "transit_mean_d_max_strategy": max([v.get("transit_days_mean") or 0 for v in bs.values()] or [None]),
                "transit_p90_d_max_strategy": max([v.get("transit_days_p90") or 0 for v in bs.values()] or [None]),
                "min_slack_to_limit_d": min([v.get("min_slack_to_limit_days") for v in bs.values() if v.get("min_slack_to_limit_days") is not None] or [None]),
                "transit_violations": sum(v.get("transit_violations") or 0 for v in bs.values()),
                "teu_0_transfers": ft.get("0"), "teu_1_transfer": ft.get("1"), "teu_2_transfers": ft.get("2"),
                "multi_hop_flows": (bs.get("multi_hop") or {}).get("flows")})
with out.open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
print("rows", len(rows), "->", out)
