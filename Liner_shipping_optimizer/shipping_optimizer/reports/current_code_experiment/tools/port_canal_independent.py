"""Independent recomputation of the ledger's port_call_fixed (fixed port-call + per-FFE capacity charge + canal fees)
from raw WorldSmall files and each plan's rotations; also the canal-fee part alone (exposure).
Rule (LINERLIB reference code, primary_source_units.md): weekly cost = f x sum over the ports of the closed rotation of
(PortCallCostFixed + PortCallCostPerFFE x capacity_FFE) + f x canal fee, canal fee = sum over rotation legs of
(IsPanama x panamaFee + IsSuez x suezFee) of the class (blank Panama fee: class cannot pass).
usage: port_canal_independent.py <outputs_dir> <arms> <s0> <s1> <out.json>"""
import csv, json, sys
from pathlib import Path
RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "WorldSmall"
rd = lambda n: list(csv.DictReader(open(RAW / n, encoding="utf-8"), delimiter="\t"))
ports = {r["UNLocode"]: r for r in rd("ports.csv")}
fleet = {r["Vessel class"]: r for r in rd("fleet_data.csv")}
flag = {(r["fromUNLOCODe"], r["ToUNLOCODE"]): (int(r["IsPanama"]), int(r["IsSuez"])) for r in rd("dist_dense.csv")}
def fee(v): return None if v in ("", None) else float(v)
outd, arms, s0, s1 = Path(sys.argv[1]), sys.argv[2].split(","), int(sys.argv[3]), int(sys.argv[4])
res, worst = [], 0.0
for arm in arms:
    for seed in range(s0, s1 + 1):
        p = outd / "outputs" / f"{arm}_seed{seed}.json"
        if not p.exists(): continue
        x = (json.loads(p.read_text(encoding="utf-8")).get("runs") or [None])[-1]
        if not x or x.get("status") != "feasible": continue
        tot = canal = 0.0; n_canal = 0; unknown = []
        for s in x["selected"]:
            cls, f, pl = fleet[s["class"]], int(s["f"]), s["ports"]
            cap = float(cls["Capacity FFE"])
            tot_s = f * sum(float(ports[q]["PortCallCostFixed"]) + float(ports[q]["PortCallCostPerFFE"]) * cap for q in pl)
            legs = list(zip(pl, pl[1:] + pl[:1]))
            pan = sum(flag.get(l, (0, 0))[0] for l in legs); sue = sum(flag.get(l, (0, 0))[1] for l in legs)
            pf, sf = fee(cls["panamaFee"]), fee(cls["suezFee"])
            if pan and pf is None: unknown.append((s["id"], "panama"))
            if sue and sf is None: unknown.append((s["id"], "suez"))
            c = f * (pan * (pf or 0.0) + sue * (sf or 0.0))
            canal += c; n_canal += (c > 0); tot += tot_s + c
        led = x["ledger"]["port_call_fixed_cost"]
        worst = max(worst, abs(tot - led))
        res.append({"arm": arm, "seed": seed, "ledger_port_call_fixed": led, "recomputed": tot, "abs_diff": abs(tot - led),
                    "canal_fee_usd_wk": canal, "services_with_canal_fee": n_canal, "services": len(x["selected"]),
                    "canal_pct_of_profit": 100 * canal / x["ledger"]["profit"], "class_cannot_pass_flags": unknown})
out = {"plans": len(res), "max_abs_diff_usd": worst, "results": res}
Path(sys.argv[5]).write_text(json.dumps(out, indent=1), encoding="utf-8")
print("plans", len(res), "max |ledger - recomputed| USD/wk:", round(worst, 4))
import statistics as st
for a in arms:
    r = [q for q in res if q["arm"] == a]
    if r: print(a, "canal mean M %.2f  services w/ canal %.1f  pct of profit %.1f" % (st.mean(q["canal_fee_usd_wk"] for q in r) / 1e6, st.mean(q["services_with_canal_fee"] for q in r), st.mean(q["canal_pct_of_profit"] for q in r)))
