"""Recompute headline means from raw per-seed CSVs (read-only)."""
import csv, sys, statistics as st, collections
files = ["issue2_corrected_baseline/per_seed_issue2.csv","issue3_solver/per_seed_dev_repl.csv",
 "issue3_solver/per_seed_holdout.csv","issue4_coverage/per_seed_issue4.csv","issue8_final/per_seed_final.csv",
 "decision_phase/d05_final/per_seed_L1.csv","decision_phase/d05_final/per_seed_L2.csv","decision_phase/d06/per_seed_scenarios.csv"]
data={}
for f in files:
    rows=list(csv.DictReader(open(f)))
    print("==",f,len(rows),"rows; cols with status:",collections.Counter(r.get("status") for r in rows))
    arms=collections.defaultdict(dict)
    for r in rows:
        arms[r["arm"]][int(r["seed"])]=r
    data[f]=arms
    for a,d in arms.items():
        ok=[(s,r) for s,r in sorted(d.items()) if r["status"] in("feasible","optimal") and r["profit_usd_wk"]]
        p=[float(r["profit_usd_wk"])/1e6 for s,r in ok]
        c=[float(r["coverage_pct"]) for s,r in ok]
        allp=[float(r["profit_usd_wk"])/1e6 if (r["status"] in("feasible","optimal") and r["profit_usd_wk"]) else 0 for s,r in sorted(d.items())]
        worst=min(ok,key=lambda x:float(x[1]["profit_usd_wk"]))[0] if ok else None
        print(f"{a:12s} n={len(d)} solved={len(ok)} seeds={min(d)}-{max(d)} mean_solved={st.mean(p):.2f} median={st.median(p):.2f} sd={st.pstdev(p):.2f} min={min(p):.2f} max={max(p):.2f} mean_all0={st.mean(allp):.2f} cov_mean={st.mean(c):.1f} cov_max={max(c):.1f} neg={sum(1 for x in p if x<0)} worst_seed={worst}")
        ts={r["time_limit_sec"] for r in d.values()}; print("   time_limits",ts, "statuses", collections.Counter(r["status"] for r in d.values()))
import pickle
# paired
def paired(f,a,b):
    A=data[f][a];B=data[f][b]
    common=sorted(set(A)&set(B))
    ds=[(s,float(B[s]["profit_usd_wk"])/1e6-float(A[s]["profit_usd_wk"])/1e6) for s in common if A[s]["profit_usd_wk"] and B[s]["profit_usd_wk"] and A[s]["status"]=="feasible" and B[s]["status"]=="feasible"]
    d=[x for _,x in ds]
    print(f"paired {b}-{a} in {f}: n={len(d)} mean={st.mean(d):+.2f} median={st.median(d):+.2f} min={min(d):+.2f} max={max(d):+.2f} higher={sum(1 for x in d if x>0)}/{len(d)}")
paired("issue8_final/per_seed_final.csv","F_base","F_s3")
paired("issue2_corrected_baseline/per_seed_issue2.csv","I2_base","I2_e")
paired("issue2_corrected_baseline/per_seed_issue2.csv","I2_base","I2_vub")
paired("issue2_corrected_baseline/per_seed_issue2.csv","I2_base","I2_ls")
paired("issue3_solver/per_seed_holdout.csv","I3_base","I3_lsvub")
paired("issue3_solver/per_seed_dev_repl.csv","I3d_base","I3d_lsvub")
for f in ["decision_phase/d05_final/per_seed_L1.csv","decision_phase/d05_final/per_seed_L2.csv"]:
    ar=list(data[f]); print(ar)
