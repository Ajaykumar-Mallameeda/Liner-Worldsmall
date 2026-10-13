import json
from collections import Counter

runs = {
    "run1 baseline": "baseline_run1_pipeline_output.json",
    "run2 baseline": "baseline_orchestrator_run2.pipeline_output.json",
    "run3 task1":    "task1_orchestrator_run3.pipeline_output.json",
    "run4 task2":    "task2_orchestrator_run4.pipeline_output.json",
}
keys = ["weekly_profit", "revenue", "operating_cost", "fuel_cost", "port_cost", "transship_cost",
        "total_cost", "total_services", "satisfied_demand", "unserved_demand", "coverage"]
data = {n: json.load(open(f, encoding="utf-8")) for n, f in runs.items()}

print(f"{'metric':18s}" + "".join(f"{n:>18s}" for n in runs))
for k in keys:
    print(f"{k:18s}" + "".join(f"{data[n]['summary_metrics'].get(k, float('nan')):>18,.1f}" for n in runs))

print()
for n, d in data.items():
    sm = d["summary_metrics"]
    regs = d["regional_results"]
    svcs = [s for r in regs for s in r.get("selected_services", [])]
    sat_plus_uns = sum(r["satisfied_demand"] + r["unserved_demand"] for r in regs)
    dem = sum(r["total_demand"] for r in regs)
    cap = sum(s.get("capacity", 0) for s in svcs)
    load = sum(s.get("load", 0) for s in svcs)
    svc_rev = sum(s.get("revenue", 0) for s in svcs)
    svc_cost = sum(s.get("cost", 0) for s in svcs)
    print(f"{n:14s} regions={len(regs)} svcs={len(svcs):3d} "
          f"sat+unserved={sat_plus_uns:>9,.0f} vs demand={dem:>9,.0f} ({sat_plus_uns/dem*100:5.1f}%)  "
          f"service rev={svc_rev/1e6:7.1f}M cost={svc_cost/1e6:7.1f}M  load/cap={load/cap*100 if cap else 0:5.1f}%  "
          f"iter profits(M)={[round(e['profit']/1e6,1) for e in d['iteration_audit']]}")
