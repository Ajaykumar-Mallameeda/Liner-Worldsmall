"""Strategy shares, utilisation and unserved reasons averaged over the seeds of one batch/variant.
usage: python -I strategy_table.py <out.md> <batch:variant> [<batch:variant> ...]   (e.g. M5:B0 M5:F1)"""
import glob
import json
import os
import statistics
import sys

out = sys.argv[1]
STRATS = ("direct", "feeder", "hub_and_spoke", "multi_hop")
L = []
for spec in sys.argv[2:]:
    batch, var = spec.split(":")
    docs = []
    for f in sorted(glob.glob(f"outputs/{batch}_seed*_{var}_*.json")):
        d = json.load(open(f, encoding="utf-8"))
        sr = d["runs"][0].get("strategy_report")
        if sr and sr.get("available"):
            docs.append(sr)
    if not docs:
        continue
    n = len(docs)

    def avg(fn):
        vals = [fn(s) for s in docs]
        vals = [v for v in vals if v is not None]
        return statistics.mean(vals) if vals else float("nan")
    L.append(f"### {batch} · {var} (n = {n} seeds)")
    L.append("")
    L.append("| strategy | flows | served TEU | share of served | coverage contribution % | revenue M | port charges M | "
             "allocated service cost M | profit contribution M | transfers / TEU | transit mean d | transit p90 d | "
             "min slack to limit d | transit violations |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for g in STRATS:
        L.append(f"| {g} | {avg(lambda s: s['by_strategy'][g]['flows']):.1f} | "
                 f"{avg(lambda s: s['by_strategy'][g]['served_teu']):,.0f} | "
                 f"{100 * avg(lambda s: s['by_strategy'][g]['share_of_served_teu']):.1f} % | "
                 f"{avg(lambda s: s['by_strategy'][g]['coverage_contribution_pct']):.2f} | "
                 f"{avg(lambda s: s['by_strategy'][g]['revenue']) / 1e6:.2f} | "
                 f"{avg(lambda s: s['by_strategy'][g]['port_charges']) / 1e6:.2f} | "
                 f"{avg(lambda s: s['by_strategy'][g]['allocated_service_cost']) / 1e6:.2f} | "
                 f"{avg(lambda s: s['by_strategy'][g]['profit_contribution']) / 1e6:.2f} | "
                 f"{avg(lambda s: s['by_strategy'][g]['transfers_per_teu']):.2f} | "
                 f"{avg(lambda s: s['by_strategy'][g]['transit_days_mean']):.1f} | "
                 f"{avg(lambda s: s['by_strategy'][g]['transit_days_p90']):.1f} | "
                 f"{avg(lambda s: s['by_strategy'][g]['min_slack_to_limit_days']):.1f} | "
                 f"{sum(s['by_strategy'][g]['transit_violations'] for s in docs)} |")
    L.append("")
    u = lambda s: s["utilisation"]                                                  # noqa: E731
    L.append(f"Utilisation (means): network load factor {avg(lambda s: u(s)['network']['load_factor']):.3f}, "
             f"nm-weighted {avg(lambda s: u(s)['network']['load_factor_nm_weighted']):.3f}; legs ≥ 95 % full "
             f"{avg(lambda s: u(s)['leg']['legs_at_or_above_95pct']):.1f} of {avg(lambda s: u(s)['leg']['legs']):.0f}; "
             f"legs < 30 % {avg(lambda s: u(s)['leg']['legs_below_30pct']):.1f}; vessels used "
             f"{avg(lambda s: u(s)['fleet']['vessels_used']):.0f} of {avg(lambda s: u(s)['fleet']['inventory']):.0f}; "
             f"served TEU per vessel {avg(lambda s: u(s)['network']['served_teu_per_vessel']):,.0f}; idle capacity cost "
             f"{avg(lambda s: s['totals']['idle_capacity_cost']) / 1e6:.1f} M/wk of "
             f"{avg(lambda s: s['totals']['service_cost']) / 1e6:.1f} M/wk service cost.")
    L.append("")
    reasons = {}
    for s in docs:
        for k, v in s["unserved_by_reason"].items():
            reasons.setdefault(k, []).append(v["share_of_total_demand_pct"])
    L.append("Unserved demand by principal reason (mean % of total demand): " + "; ".join(
        f"{k} {sum(v) / n:.2f} %" for k, v in sorted(reasons.items(), key=lambda kv: -sum(kv[1]))))
    L.append("")
open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
