import json, sys, glob
sys.path.insert(0, r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer")
from src.benchmark.paper_evaluator import load_worldsmall_ffe, evaluate, net_profit
P = r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer"
data = load_worldsmall_ffe(P + r"\data\raw\WorldSmall")
t6 = json.load(open(P + r"\reports\issue7_paper_mode\paper_table6_design.json"))
paper = [{"ports": s[:-1], "capacity": c, "vessels": n} for s, c, n in zip(t6["schedules"], t6["caps"], t6["vessels"])]
plans = {"paper_table6": paper}
for arm in ("I4_base", "I4_s3"):
    for seed in (0, 1, 2):
        sel = json.load(open(P + rf"\reports\issue4_coverage\int\outputs\{arm}_seed{seed}.json"))["runs"][-1]["selected"]
        plans[f"{arm}_seed{seed}"] = [{"ports": s["ports"], "class": s["class"], "frequency": s["f"]} for s in sel]
rows = []
for name, d in plans.items():
    for cb, vb in (("per_departure", "per_rotation"), ("per_vessel", "per_rotation")):
        r = evaluate(data, d, capacity_basis=cb, voyage_basis=vb)
        rows.append({"plan": name, "capacity_basis": cb, "voyage_basis": vb, "coverage_pct": round(100 * r["coverage"], 1),
                     "vessels_used": round(r["vessels_used"], 1), "net_profit_M_per_wk": round(net_profit(r) / 1e6, 2),
                     "revenue_M": round(r["revenue"] / 1e6, 1), "rejected_penalty_M": round(r["rejected_penalty"] / 1e6, 1)})
import pandas as pd
df = pd.DataFrame(rows)
print(df.to_string(index=False))
df.to_csv(P + r"\reports\issue7_paper_mode\paper_mode_plan_evaluation.csv", index=False)
