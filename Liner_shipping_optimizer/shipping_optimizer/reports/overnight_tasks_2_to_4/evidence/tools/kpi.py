import json, sys
for label, p in (a.split("=", 1) for a in sys.argv[1:]):
    o = json.load(open(p, encoding="utf-8"))
    s = o["summary_metrics"]
    regs = o.get("regional_results", [])
    n_sel = sum(len(r.get("selected_services", [])) for r in regs)
    print(f"{label:14s} profit={s['weekly_profit']:>16,.0f} 'revenue'={s['revenue']:>15,.0f} cost={s['total_cost']:>14,.0f} "
          f"fuel={s['fuel_cost']:>13,.0f} port={s['port_cost']:>11,.0f} oper={s['operating_cost']:>12,.0f} "
          f"svc={s['total_services']:>4} listed={n_sel:>4} sat={s['satisfied_demand']:>9,.0f} cov={s['coverage']:.1f}%")
