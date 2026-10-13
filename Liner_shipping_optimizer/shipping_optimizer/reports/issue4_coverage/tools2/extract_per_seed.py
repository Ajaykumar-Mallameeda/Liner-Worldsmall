"""Per-seed metrics table for a paired batch (Issue 2+).

usage: python extract_per_seed.py <outputs_dir> <out.csv> [<tag_prefix>]
Reads <outputs_dir>/<TAG>_seed<S>.json written by global_stage_experiment.py (production strategy).
Every field is read from the run's own ledger / solver / strategy report - nothing is estimated here
except `cost_per_served_teu` (= ledger total cost / served TEU) and the departures sum.
"""
import csv
import json
import re
import sys
from pathlib import Path

src = Path(sys.argv[1])
out = Path(sys.argv[2])
prefix = sys.argv[3] if len(sys.argv) > 3 else ""
CLASSES = ["Feeder_450", "Feeder_800", "Panamax_1200", "Panamax_2400", "Post_panamax", "Super_panamax"]


def g(d, *ks, default=None):
    for k in ks:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


rows = []
for p in sorted(src.glob(f"{prefix}*_seed*.json")):
    m = re.match(r"(.+)_seed(\d+)\.json$", p.name)
    if not m:
        continue
    arm, seed = m.group(1), int(m.group(2))
    d = json.loads(p.read_text(encoding="utf-8"))
    r = (d.get("runs") or [None])[-1]
    if not r:
        continue
    led = r.get("ledger") or {}
    sol = r.get("solver") or {}
    rec = led.get("reconciliation") or {}
    sr = r.get("strategy_report") or {}
    bs = sr.get("by_strategy") or {}
    ut = sr.get("utilisation") or {}
    un = sr.get("unserved_by_reason") or {}
    ls = rec.get("local_search") or {}
    fr = rec.get("flow_reoptimisation") or {}
    sel = r.get("selected") or []
    served = led.get("served_teu") or 0.0
    row = {
        "arm": arm, "seed": seed, "env": json.dumps(d.get("env") or {}, sort_keys=True),
        "solver": "CBC single thread" if not (d.get("env") or {}).get("NETWORK_MILP_BACKEND") else d["env"]["NETWORK_MILP_BACKEND"],
        "time_limit_sec": d.get("time_limit_sec"), "stage_wall_sec": r.get("wall_sec_total"),
        "status": r.get("status"), "solver_status": sol.get("solution_status"),
        "incumbent_usd_wk": sol.get("objective_usd_per_week"), "bound_usd_wk": sol.get("relaxation_bound"),
        "gap_pct": sol.get("gap_to_bound_pct"),
        "profit_usd_wk": led.get("profit"), "revenue_usd_wk": led.get("revenue"),
        "vessel_cost": led.get("vessel_cost"), "fuel_cost": led.get("fuel_cost"),
        "port_call_fixed": led.get("port_call_fixed_cost"), "handling": led.get("handling_cost"),
        "transshipment": led.get("transshipment_cost"), "port_variable": led.get("port_variable_cost"),
        "total_cost": led.get("total_cost"), "margin_pct": led.get("margin_pct"),
        "coverage_pct": led.get("coverage_pct"), "served_teu": served, "unserved_teu": led.get("unserved_teu"),
        "demand_teu": led.get("total_demand_teu"),
        "cost_per_served_teu": (led.get("total_cost") / served) if served else None,
        "services": led.get("services"), "departures_per_week": sum(int(s.get("f") or 0) for s in sel),
        "vessels_used": led.get("vessels"), "inventory": g(ut, "fleet", "inventory"),
        "idle_vessels": (g(ut, "fleet", "inventory") or 0) - (led.get("vessels") or 0),
        "load_factor_leg": g(ut, "leg", "load_factor_mean"), "load_factor_service": g(ut, "service", "load_factor_mean"),
        "load_factor_network": g(ut, "network", "load_factor"),
        "served_teu_per_vessel": g(ut, "network", "served_teu_per_vessel"),
        "profit_per_vessel": g(ut, "network", "profit_per_vessel"),
        "ledger_valid": led.get("valid"), "ledger_violations": len(led.get("violations") or []),
        "reconciled": rec.get("reconciled"), "regional_verified": g(r, "regional_reconciliation", "accounting_verified"),
        "ls_applied": ls.get("applied"), "ls_gain": ls.get("gain_usd"), "reopt_gain": fr.get("gain_usd"),
        "vub_applied": g(rec, "formulation", "vub_applied"),
        "transit_p90_max_d": max([v.get("transit_days_p90") or 0 for v in bs.values()] or [None]),
        "transit_mean_direct_d": g(bs, "direct", "transit_days_mean"),
        "min_slack_d": min([v.get("min_slack_to_limit_days") for v in bs.values()
                            if v.get("min_slack_to_limit_days") is not None] or [None]),
        "transit_violations": sum(v.get("transit_violations") or 0 for v in bs.values()),
    }
    for k, v in (r.get("flow_teu_by_n_transfers") or {}).items():
        row[f"teu_{k}_transfers"] = v
    for c in CLASSES:
        f = g(ut, "fleet", "by_class", c) or {}
        row[f"used_{c}"] = f.get("vessels_used")
        row[f"inv_{c}"] = f.get("inventory")
        row[f"svc_{c}"] = f.get("services_operated")
    for k, v in un.items():
        row[f"unserved_{k}_pct"] = v.get("share_of_total_demand_pct")
    rows.append(row)

cols = []
for r_ in rows:
    for k in r_:
        if k not in cols:
            cols.append(k)
with out.open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
print("rows", len(rows), "->", out)
