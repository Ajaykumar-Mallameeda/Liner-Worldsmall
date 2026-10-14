"""Row-level arithmetic identities on every per-seed CSV (read-only):
profit = revenue - total_cost ; total_cost = sum of itemised costs ; coverage = served/demand ; served+unserved = demand."""
import csv,glob
tot=bad=0; worst=0
for f in sorted(glob.glob("**/per_seed*.csv",recursive=True)):
    if f.startswith("final_campaign_audit"): continue
    n=b=0
    for r in csv.DictReader(open(f)):
        if r.get("status")!="feasible" or not r.get("profit_usd_wk"): continue
        try:
            rev=float(r["revenue_usd_wk"]); tc=float(r["total_cost"]); p=float(r["profit_usd_wk"])
            items=sum(float(r[k]) for k in ("vessel_cost","fuel_cost","port_call_fixed","handling","transshipment","port_variable"))
            cov=100*float(r["served_teu"])/float(r["demand_teu"])
            e=[abs(rev-tc-p),abs(items-tc),abs(cov-float(r["coverage_pct"]))*1e4,abs(float(r["served_teu"])+float(r["unserved_teu"])-float(r["demand_teu"]))]
        except (KeyError,ValueError) as ex:
            continue
        n+=1; w=max(e[0],e[1],e[2],e[3]); worst=max(worst,w)
        if w>1.0: b+=1; print("MISMATCH",f,r["arm"],r["seed"],e)
    tot+=n; bad+=b; print(f"{f}: rows checked {n}, mismatches {b}")
print("TOTAL rows",tot,"mismatches",bad,"worst abs error",worst)
