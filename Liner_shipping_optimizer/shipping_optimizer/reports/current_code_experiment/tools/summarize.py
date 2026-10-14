"""Aggregate per-seed CSV into per-arm means and paired statistics.  usage: summarize.py <per_seed.csv> <ref_arm> <out.md> [arm ...]"""
import csv, statistics as st, sys, collections
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
ref = sys.argv[2]; out = sys.argv[3]
arms = sys.argv[4:] or sorted({r["arm"] for r in rows})
by = collections.defaultdict(dict)
for r in rows:
    by[r["arm"]][int(r["seed"])] = r
def f(r, k):
    v = r.get(k)
    return float(v) if v not in (None, "") else None
def col(arm, k, ok_only=True):
    return [f(r, k) for r in by[arm].values() if (r["status"] == "feasible" or not ok_only) and f(r, k) is not None]
def m(x): return st.mean(x) if x else float("nan")
L = []
P = lambda s="": L.append(s)
P("| metric (mean over solved runs) | " + " | ".join(arms) + " |"); P("|---|" + "---:|" * len(arms))
def line(label, k, scale=1.0, fmt="{:.2f}"):
    P(f"| {label} | " + " | ".join(fmt.format(m(col(a, k)) / scale) for a in arms) + " |")
P("| runs / solved / invalid-plan / other | " + " | ".join(
    f"{len(by[a])} / {sum(r['status']=='feasible' for r in by[a].values())} / {sum(r['status']=='invalid_plan' for r in by[a].values())} / {sum(r['status'] not in ('feasible','invalid_plan') for r in by[a].values())}" for a in arms) + " |")
for label, k, sc, fm in [("revenue M USD/wk", "revenue_usd_wk", 1e6, "{:.2f}"), ("vessel cost M", "vessel_cost", 1e6, "{:.2f}"), ("fuel cost M", "fuel_cost", 1e6, "{:.2f}"),
        ("port-call fixed incl. canal+capacity charge M", "port_call_fixed", 1e6, "{:.2f}"), ("handling M", "handling", 1e6, "{:.2f}"), ("transshipment M", "transshipment", 1e6, "{:.2f}"),
        ("port variable M", "port_variable", 1e6, "{:.2f}"), ("total cost M", "total_cost", 1e6, "{:.2f}"), ("**profit M USD/wk**", "profit_usd_wk", 1e6, "{:.2f}"),
        ("margin %", "margin_pct", 1, "{:.1f}"), ("coverage %", "coverage_pct", 1, "{:.1f}"), ("served TEU/wk", "served_teu", 1, "{:,.0f}"),
        ("services", "services", 1, "{:.1f}"), ("departures/wk", "departures_per_week", 1, "{:.1f}"), ("vessels assigned (of owned)", "vessels_used", 1, "{:.1f}"),
        ("owned", "inventory", 1, "{:.0f}"), ("fleet vessel utilisation (assigned/owned)", "vessels_used", 1, None),
        ("service leg load factor (mean of services)", "load_factor_service", 1, "{:.3f}"), ("leg load factor (mean of legs)", "load_factor_leg", 1, "{:.3f}"),
        ("network leg load factor (carried/offered TEU-legs)", "load_factor_network", 1, "{:.3f}"),
        ("max p90 transit days", "transit_p90_max_d", 1, "{:.1f}"), ("stage wall s", "stage_wall_sec", 1, "{:.1f}"),
        ("capped-model gap to bound % (incumbent vs LP bound)", "gap_pct", 1, "{:.1f}"), ("ledger violations (sum)", "ledger_violations", 1, None), ("transit violations (sum)", "transit_violations", 1, None)]:
    if fm is None:
        if label.startswith("fleet"):
            P(f"| {label} | " + " | ".join("{:.3f}".format(m(col(a, "vessels_used")) / m(col(a, "inventory"))) for a in arms) + " |")
        else:
            P(f"| {label} | " + " | ".join("{:.0f}".format(sum(col(a, "ledger_violations" if label.startswith("ledger") else "transit_violations"))) for a in arms) + " |")
    else:
        line(label, sc and (label and {"revenue M USD/wk":"revenue_usd_wk"}.get(label, None) or None) or None, 1) if False else line(label, k, sc, fm)
P(); P("Vessels assigned / owned by class (mean):"); P()
cl = ["Feeder_450", "Feeder_800", "Panamax_1200", "Panamax_2400", "Post_panamax", "Super_panamax"]
P("| class | " + " | ".join(arms) + " |"); P("|---|" + "---:|" * len(arms))
for c in cl:
    P(f"| {c} | " + " | ".join(f"{m(col(a,'used_'+c)):.1f} / {m(col(a,'inv_'+c)):.0f}" for a in arms) + " |")
P(); P("Unserved demand by reason (mean % of total demand):"); P()
reasons = sorted({k for r in rows for k in r if k.startswith("unserved_") and k.endswith("_pct")})
P("| reason | " + " | ".join(arms) + " |"); P("|---|" + "---:|" * len(arms))
for k in reasons:
    P(f"| {k[9:-4]} | " + " | ".join(f"{m(col(a,k)):.2f}" for a in arms) + " |")
P(); P(f"Paired differences vs `{ref}` (same seed; positive = arm higher):"); P()
P("| arm | n pairs | profit mean M | median | sd | min (seed) | max (seed) | seeds higher | coverage pp mean | coverage higher |"); P("|---|---:|---:|---:|---:|---|---|---:|---:|---:|")
for a in arms:
    if a == ref: continue
    ds, cs = [], []
    for s, r in by[a].items():
        q = by[ref].get(s)
        if q and r["status"] == "feasible" and q["status"] == "feasible":
            ds.append((s, (f(r, "profit_usd_wk") - f(q, "profit_usd_wk")) / 1e6)); cs.append(f(r, "coverage_pct") - f(q, "coverage_pct"))
    if not ds: continue
    x = [v for _, v in ds]; mn = min(ds, key=lambda t: t[1]); mx = max(ds, key=lambda t: t[1])
    P(f"| {a} | {len(x)} | {st.mean(x):+.2f} | {st.median(x):+.2f} | {st.pstdev(x):.2f} | {mn[1]:+.2f} ({mn[0]}) | {mx[1]:+.2f} ({mx[0]}) | {sum(v>0 for v in x)}/{len(x)} | {st.mean(cs):+.2f} | {sum(v>0 for v in cs)}/{len(cs)} |")
open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
