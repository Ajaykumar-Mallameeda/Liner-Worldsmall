"""Read-only analysis of a pipeline_output.json produced by tests/test_orchestrator.py.

Usage: python -I analyze_output.py <pipeline_output.json>
Reports the economic identity, cost-component sums, and duplication symptoms.
"""
import json
import sys
from collections import Counter

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    out = json.load(fh)

sm = out["summary_metrics"]
print("== summary_metrics ==")
for k in ("weekly_profit", "annual_profit", "revenue", "operating_cost", "fuel_cost",
          "transship_cost", "port_cost", "total_cost", "cost", "total_services",
          "satisfied_demand", "unserved_demand", "coverage"):
    print(f"  {k:18s} {sm.get(k)}")

print("\n== regional_results ==")
tot = Counter()
for r in out["regional_results"]:
    print(f"  {r['region']:12s} svc={r['services_selected']:4d} profit={r['weekly_profit']:>16,.0f} "
          f"oper={r['operating_cost']:>14,.0f} fuel={r.get('fuel_cost',0):>14,.0f} "
          f"port={r['port_cost']:>14,.0f} trans={r['transship_cost']:>12,.0f} "
          f"total={r['total_cost']:>14,.0f} sat={r['satisfied_demand']:>10,.0f} "
          f"unserved={r['unserved_demand']:>10,.0f} demand={r['total_demand']:>10,.0f}")
    for k in ("weekly_profit", "operating_cost", "fuel_cost", "port_cost", "transship_cost",
              "total_cost", "satisfied_demand", "unserved_demand", "total_demand"):
        tot[k] += r.get(k, 0) or 0
print("  SUM:", {k: round(v) for k, v in tot.items()})

print("\n== identity checks (regional level) ==")
for r in out["regional_results"]:
    comp = r["operating_cost"] + r.get("fuel_cost", 0) + r["port_cost"] + r["transship_cost"]
    print(f"  {r['region']:12s} oper+fuel+port+trans={comp:>16,.0f}  total_cost={r['total_cost']:>16,.0f} "
          f"diff={comp - r['total_cost']:>10,.2f}   sat+unserved={r['satisfied_demand']+r['unserved_demand']:>10,.0f} "
          f"vs total_demand={r['total_demand']:>10,.0f}")

print("\n== service-level (selected_services) ==")
svcs = []
for r in out["regional_results"]:
    for s in r.get("selected_services", []):
        svcs.append((r["region"], s))
print("  n services:", len(svcs))
rev = sum(s.get("revenue", 0) for _, s in svcs)
vc = sum(s.get("vessel_cost", 0) for _, s in svcs)
fc = sum(s.get("fuel_cost", 0) for _, s in svcs)
pc = sum(s.get("port_cost", 0) for _, s in svcs)
cs = sum(s.get("cost", 0) for _, s in svcs)
wp = sum(s.get("weekly_profit", 0) for _, s in svcs)
print(f"  service revenue sum      = {rev:>16,.0f}")
print(f"  service vessel_cost sum  = {vc:>16,.0f}")
print(f"  service fuel_cost sum    = {fc:>16,.0f}")
print(f"  service port_cost sum    = {pc:>16,.0f}")
print(f"  service cost sum         = {cs:>16,.0f}")
print(f"  service weekly_profit    = {wp:>16,.0f}   (revenue - cost = {rev-cs:,.0f})")
print(f"  summary 'revenue' (profit+total_cost) = {sm.get('revenue'):,.0f}")
print(f"  summary total_cost - service cost sum  = {sm.get('total_cost') - cs:,.0f}")
cap = sum(s.get("capacity", 0) for _, s in svcs)
load = sum(s.get("load", 0) for _, s in svcs)
print(f"  sum(capacity) = {cap:,.0f}   sum(load) = {load:,.0f}   util = {load/cap*100 if cap else 0:.1f}%")
vc_by_class = Counter(s.get("vessel_class") for _, s in svcs)
print("  vessel_class counts:", dict(vc_by_class))
caps = Counter(s.get("capacity") for _, s in svcs)
print("  service capacity values (TEU) :", dict(sorted(caps.items(), key=lambda kv: -kv[1])))
print("  keys on a service:", sorted(svcs[0][1].keys()) if svcs else None)
