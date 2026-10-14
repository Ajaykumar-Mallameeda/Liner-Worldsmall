"""Bounded D-07 evidence: how much vessel-time does the integer-weekly-frequency rule leave idle in the plans of a batch?
For a service with n vessels, f weekly departures and rotation time T days, the plan needs T*f vessel-days per week but pays
for 7*n.  slot_time_utilisation u = T*f/(7*n)  =>  idle vessel-days = 7*n*(1-u), cost = idle days x TC (USD/day).
This is an UPPER BOUND on what a perfect sub-weekly (fractional) schedule could save on the plan's own services; it is not
an achievable gain (cycles, port calls and transit constraints are not modelled here).
usage: subweekly_waste.py <outputs_dir> <arm> <seed_from> <seed_to> <fleet_data.csv> <out.json>"""
import csv, json, sys, statistics as st
from pathlib import Path

outd, arm, s0, s1 = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
tc = {r["Vessel class"]: float(r["TC rate daily (fixed Cost)"]) for r in csv.DictReader(open(sys.argv[5], encoding="utf-8"), delimiter="\t")}
res = []
for seed in range(s0, s1 + 1):
    p = outd / "outputs" / f"{arm}_seed{seed}.json"
    if not p.exists():
        continue
    x = (json.loads(p.read_text(encoding="utf-8")).get("runs") or [None])[-1]
    if not x or x.get("status") not in ("feasible", "optimal"):
        continue
    profit = x["ledger"]["profit"]
    idle_days = idle_cost = 0.0
    thin = 0
    for s in x["strategy_report"]["services"]:
        u, n = s.get("slot_time_utilisation"), s.get("vessels")
        if u is None or not n:
            continue
        d = 7.0 * n * (1.0 - u)
        idle_days += d
        idle_cost += d * tc[s["class"]]
        thin += (u < 0.6)
    res.append({"seed": seed, "profit": profit, "idle_vessel_days": idle_days, "idle_cost_usd_wk": idle_cost,
                "idle_cost_pct_of_profit": 100 * idle_cost / profit, "services_below_60pct_slot_utilisation": thin,
                "services": len(x["strategy_report"]["services"])})
summary = {"arm": arm, "n": len(res),
           "idle_cost_usd_wk_mean": st.mean(r["idle_cost_usd_wk"] for r in res) if res else None,
           "idle_cost_pct_of_profit_mean": st.mean(r["idle_cost_pct_of_profit"] for r in res) if res else None,
           "per_seed": res}
Path(sys.argv[6]).write_text(json.dumps(summary, indent=1), encoding="utf-8")
print({k: v for k, v in summary.items() if k != "per_seed"})
