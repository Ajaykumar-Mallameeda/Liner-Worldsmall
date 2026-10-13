import json, itertools, sys
sys.path.insert(0, r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer")
from src.benchmark.paper_evaluator import load_worldsmall_ffe, evaluate, net_profit
data = load_worldsmall_ffe(r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer\data\raw\WorldSmall")
d = json.load(open(r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer\reports\issue7_paper_mode\paper_table6_design.json"))
design = [{"ports": s[:-1], "capacity": c, "vessels": n} for s, c, n in zip(d["schedules"], d["caps"], d["vessels"])]
rows = []
for vb, pvb, cb in itertools.product(("per_rotation", "per_vessel"), ("capacity", "cargo"), ("none", "per_rotation", "per_vessel")):
    r = evaluate(data, design, voyage_basis=vb, port_variable_basis=pvb, canal_basis=cb)
    rows.append((vb, pvb, cb, net_profit(r) / 1e6, r))
r0 = rows[0][4]
print("coverage %.1f%%  vessels used %.2f  revenue %.1f M  rejected %.0f FFE penalty %.1f M handling %.1f M service %.1f M unused %.2f M" % (
    100 * r0["coverage"], r0["vessels_used"], r0["revenue"] / 1e6, r0["rejected_ffe"], r0["rejected_penalty"] / 1e6,
    r0["handling_and_transshipment"] / 1e6, r0["vessel_service_cost"] / 1e6, r0["unused_vessel_profit"] / 1e6))
print("fuel t/wk per_rotation %.0f ; per_vessel %.0f" % (r0["fuel_tonnes_per_week"], rows[6][4]["fuel_tonnes_per_week"]))
for vb, pvb, cb, p, r in rows:
    print(f"{vb:13s} port_var={pvb:8s} canal={cb:12s} net profit {p:8.2f} M/wk   voyage(no fuel) {r['voyage_cost_without_fuel']/1e6:7.2f} M  fuel_t {r['fuel_tonnes_per_week']:9.0f}")
json.dump([{"voyage_basis": a, "port_variable_basis": b, "canal_basis": c, "net_profit_M": p, "detail": r} for a, b, c, p, r in rows],
          open(r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer\reports\issue7_paper_mode\table6_evaluation.json", "w"), indent=1)
