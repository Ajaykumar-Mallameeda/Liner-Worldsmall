"""Independent re-derivation of ledger facts from the raw WorldSmall files and the run artifacts (read-only).
Checks, per accepted plan: (1) vessel cost = sum(vessels_by_class x TC x 7) from fleet_data.csv; (2) vessels used per class <= owned
(fleet_WorldSmall.csv); (3) profit = revenue - itemised costs; (4) demand total = sum(FFEPerWeek) x 2 and coverage = served/demand;
(5) every leg load factor <= 1 + 1e-6 (CBC feasibility tolerance; largest observed overshoot 6.3e-9 = 3e-5 TEU) and every service fits its vessel-cycle (slot-time utilisation <= 1);
(6) reported ledger violations and transit violations are zero.   usage: independent_check.py <outputs_dir> <arms> <s0> <s1> <out.json>"""
import csv, json, math, sys
from pathlib import Path
RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "WorldSmall"
tc = {r["Vessel class"]: float(r["TC rate daily (fixed Cost)"]) for r in csv.DictReader(open(RAW / "fleet_data.csv", encoding="utf-8"), delimiter="\t")}
inv = {r["Vessel class"]: int(r["Quantity"]) for r in csv.DictReader(open(RAW / "fleet_WorldSmall.csv", encoding="utf-8"), delimiter="\t")}
dem = list(csv.DictReader(open(RAW / "Demand_WorldSmall_Fixed_Sep.csv", encoding="utf-8"), delimiter="\t"))
demand_teu = 2.0 * sum(float(r["FFEPerWeek"]) for r in dem)
outd, arms, s0, s1 = Path(sys.argv[1]), sys.argv[2].split(","), int(sys.argv[3]), int(sys.argv[4])
res, bad = [], 0
for arm in arms:
    for seed in range(s0, s1 + 1):
        p = outd / "outputs" / f"{arm}_seed{seed}.json"
        if not p.exists():
            res.append({"arm": arm, "seed": seed, "result": "missing_artifact"}); bad += 1; continue
        x = (json.loads(p.read_text(encoding="utf-8")).get("runs") or [None])[-1]
        if not x or x.get("status") not in ("feasible", "optimal"):
            res.append({"arm": arm, "seed": seed, "result": f"not_accepted:{(x or {}).get('status')}"}); bad += 1; continue
        L = x["ledger"]; sr = x["strategy_report"]
        vc = sum(n * tc[c] * 7.0 for c, n in L["vessels_by_class"].items())
        checks = {
            "vessel_cost_matches_fleet_file": abs(vc - L["vessel_cost"]) <= 1e-6 * max(1.0, vc),
            "vessels_within_inventory": all(n <= inv[c] for c, n in L["vessels_by_class"].items()),
            "profit_identity": abs(L["revenue"] - L["total_cost"] - L["profit"]) <= 1e-6 * max(1.0, L["revenue"]),
            "costs_sum_to_total": abs(sum(L[k] for k in ("vessel_cost", "fuel_cost", "port_call_fixed_cost", "handling_cost", "transshipment_cost", "port_variable_cost")) - L["total_cost"]) <= 1e-6 * max(1.0, L["total_cost"]),
            "demand_total_matches_file": abs(L["total_demand_teu"] - demand_teu) < 1e-6,
            "coverage_matches_served_over_demand": abs(100 * L["served_teu"] / demand_teu - L["coverage_pct"]) < 1e-9,
            "served_plus_unserved_is_demand": abs(L["served_teu"] + L["unserved_teu"] - demand_teu) < 1e-6,
            "leg_load_factor_le_1": all((s.get("max_leg_load_factor") or 0) <= 1 + 1e-6 for s in sr["services"]),
            "vessel_cycle_fits": all((s.get("slot_time_utilisation") or 0) <= 1 + 1e-6 for s in sr["services"]),
            "ledger_valid_no_violations": bool(L["valid"]) and len(L.get("violations") or []) == 0,
            "transit_violations_zero": sum(v.get("transit_violations") or 0 for v in (sr.get("by_strategy") or {}).values()) == 0,
        }
        ok = all(checks.values()); bad += (not ok)
        res.append({"arm": arm, "seed": seed, "result": "pass" if ok else "FAIL", "failed": [k for k, v in checks.items() if not v],
                    "vessel_cost_recomputed": vc, "vessel_cost_ledger": L["vessel_cost"]})
out = {"demand_teu_from_file": demand_teu, "plans_checked": len(res), "plans_not_passing": bad, "results": res}
Path(sys.argv[5]).write_text(json.dumps(out, indent=1), encoding="utf-8")
print("plans", len(res), "not passing", bad)
for r in res:
    if r["result"] != "pass": print(r)
