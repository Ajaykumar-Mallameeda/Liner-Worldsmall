"""Read-only: weekly canal-fee exposure of recorded plans (fees are NOT in the model: blank = unknown, not zero)."""
import json, sys
import pandas as pd
R = r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer"
dist = pd.read_csv(R + r"\data\raw\WorldSmall\dist_dense.csv", sep="\t")
fl = pd.read_csv(R + r"\data\raw\WorldSmall\fleet_data.csv", sep="\t").set_index("Vessel class")
flag = {(r.fromUNLOCODe, r.ToUNLOCODE): (int(r.IsPanama), int(r.IsSuez)) for r in dist.itertuples()}
print("directed pairs using Panama:", sum(v[0] for v in flag.values()), "Suez:", sum(v[1] for v in flag.values()), "of", len(flag))
print(fl[["panamaFee", "suezFee"]].to_string())
out = []
for plan in sys.argv[1:]:
    d = json.load(open(plan)); r = d["runs"][-1]; sel = r["selected"]
    prof = r["ledger"]["profit"]
    known = unknown_p = unknown_s = 0.0
    n_p = n_s = 0
    rows = []
    for s in sel:
        ports = s["ports"]; f = s["f"]; cls = s["class"]
        legs = list(zip(ports, ports[1:] + ports[:1])) if len(ports) > 1 else []
        p_t = sum(flag.get(l, (0, 0))[0] for l in legs); s_t = sum(flag.get(l, (0, 0))[1] for l in legs)
        if not (p_t or s_t):
            continue
        pf = fl.loc[cls, "panamaFee"]; sf = fl.loc[cls, "suezFee"]
        c = 0.0
        if p_t:
            n_p += 1
            if pd.isna(pf): unknown_p += p_t * f
            else: c += p_t * f * pf
        if s_t:
            n_s += 1
            if pd.isna(sf): unknown_s += s_t * f
            else: c += s_t * f * sf
        known += c
        rows.append((s["id"], cls, f, p_t, s_t, c))
    out.append({"plan": plan.split("\\")[-1].split("/")[-1], "profit_M": round(prof / 1e6, 2), "services": len(sel),
                "services_using_panama": n_p, "services_using_suez": n_s, "known_fee_exposure_M_per_wk": round(known / 1e6, 3),
                "known_exposure_pct_of_profit": round(100 * known / prof, 2),
                "panama_transits_with_unknown_fee_per_wk": unknown_p, "suez_transits_with_unknown_fee_per_wk": unknown_s})
print(json.dumps(out, indent=1))
json.dump(out, open("canal_exposure.json", "w"), indent=1)
