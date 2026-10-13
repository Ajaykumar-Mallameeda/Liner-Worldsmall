import json, sys, collections
r = json.load(open(sys.argv[1])); seed = r['seed']
n = r['network']
L = [f"### Seed {seed} - plan `{r['plan_file']}`", "",
     f"Network profit {n['profit_usd_wk']/1e6:.2f} M USD/wk, served {n['served_teu']:,.0f} TEU, {n['services']} services; "
     f"idle vessels by class: {n['vessels_idle']}.", "",
     "**Operated services - why they are operated** (marginal = network profit lost if the service is removed and cargo re-routed):", "",
     "| service | class | f/wk | vessels | role | load factor | stand-alone k USD/wk | network marginal k USD/wk | commercial | operational |",
     "|---|---|---:|---:|---|---:|---:|---:|---|---|"]
for o in sorted(r['operated'], key=lambda o: -o['network_marginal_profit_usd_wk']):
    L.append(f"| {o['service_id']} {'-'.join(o['ports'][:5])} | {o['vessel_class']} | {o['frequency_per_week']} | {o['vessels']} | {o['role']} | "
             f"{(o['load_factor_mean'] or 0):.2f} | {o['standalone_profit_usd_wk']/1e3:,.0f} | {o['network_marginal_profit_usd_wk']/1e3:,.0f} | "
             f"{o['commercial_status']} | {o['operational_status']} |")
L += ["", f"{r['alternatives_evaluated']} alternatives evaluated (of the pool, ranked by potential); {r['alternatives_with_positive_marginal']} have a positive marginal profit.", "",
      "**Executive opportunities (top 15 by network marginal profit; never an executable schedule unless FEASIBLE)**", "",
      "| service | class | f | vessels | marginal k USD/wk | +served TEU | operational | unmet condition | commercial | marginal under fuel +25 % / -25 % / capacity x0.5 (k) |",
      "|---|---|---:|---:|---:|---:|---|---|---|---|"]
for o in r['opportunities'][:15]:
    c = o['unmet_conditions'][0] if o['unmet_conditions'] else None
    cs = f"add {c['additional_vessels_required']} x {c['vessel_class']} (idle {c['idle_in_inventory']})" if c else "-"
    s = o['sensitivity_marginal_profit_usd_wk']
    L.append(f"| {o['service_id']} {'-'.join(o['ports'][:5])} | {o['vessel_class']} | {o['frequency_per_week']} | {o['vessels_required']} | "
             f"{o['network_marginal_profit_usd_wk']/1e3:,.0f} | {o['incremental_served_teu']:,.0f} | {o['operational_status']} | {cs} | {o['commercial_status']} | "
             f"{s['fuel_plus_25pct']/1e3:,.0f} / {s['fuel_minus_25pct']/1e3:,.0f} / {s['capacity_half']/1e3:,.0f} |")
print("\n".join(L))
