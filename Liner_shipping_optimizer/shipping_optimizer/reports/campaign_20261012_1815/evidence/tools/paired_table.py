"""Per-seed tables and paired comparisons of controlled global-stage batches.

usage: python paired_table.py <label> <tagA> [<tagB> ...] [--seeds 0-9] [--csv out.csv]
  Reads  <campaign>/evidence/outputs/<tag>_seed<S>.json  (run_batch.sh output).
  Prints, for each tag, the per-seed table and the aggregate; for every further tag the paired
  differences against the FIRST tag (profit, coverage, served TEU, services, vessels).
  A tag of the form  hist:<prefix>  reads the previous mission's  tasks_19_20_21/evidence/outputs/
  <prefix>_seed<S>_D_cbc120.json  (e.g. hist:M7 = the recorded default configuration).
"""
import csv
import json
import math
import statistics as st
import sys
from pathlib import Path

PROJ = Path(r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer")
OUT = PROJ / "reports" / "campaign_20261012_1815" / "evidence" / "outputs"
HIST = PROJ / "reports" / "tasks_19_20_21" / "evidence" / "outputs"


def load(tag: str, seed: int):
    if tag.startswith("hist:"):
        p = HIST / f"{tag[5:]}_seed{seed}_D_cbc120.json"
    else:
        p = OUT / f"{tag}_seed{seed}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    runs = d.get("runs") or []
    if not runs:
        return None
    r = runs[-1]
    s, l = r.get("solver") or {}, r.get("ledger") or {}
    rec = l.get("reconciliation") or {}
    sr = r.get("strategy_report") or {}
    util = (sr.get("utilisation") or {})
    by_strat = sr.get("by_strategy") or {}
    flows = {k: round(v.get("served_teu", 0)) for k, v in by_strat.items()} if by_strat else {}
    n_flows = {k: v.get("flows") for k, v in by_strat.items()} if by_strat else {}
    p90 = [v.get("transit_days_p90") for v in by_strat.values() if v.get("transit_days_p90") is not None]
    slack = [v.get("min_slack_to_limit_days") for v in by_strat.values() if v.get("min_slack_to_limit_days") is not None]
    fr = rec.get("flow_reoptimisation") or {}
    lsr = rec.get("local_search") or {}
    form = rec.get("formulation") or {}
    tim = rec.get("stage_timing") or {}
    cv = (r.get("candidate_augmentation") or {})
    unserved = {k: round(v.get("share_of_total_demand_pct", 0), 1) for k, v in (sr.get("unserved_by_reason") or {}).items()}
    vt = {}
    for v in (l.get("violations") or []):
        vt[str(v.get("type", "?"))] = vt.get(str(v.get("type", "?")), 0) + 1
    return {
        "seed": seed, "status": r.get("status"), "ok": r.get("ok"), "solution_status": s.get("solution_status"),
        "profit": l.get("profit"), "revenue": l.get("revenue"), "cost": l.get("total_cost"),
        "margin_pct": l.get("margin_pct"), "coverage_pct": l.get("coverage_pct"), "served_teu": l.get("served_teu"),
        "services": l.get("services"), "vessels": l.get("vessels"), "vessels_by_class": l.get("vessels_by_class"),
        "ledger_valid": l.get("valid"), "violations": len(l.get("violations") or []), "violation_types": vt,
        "reconciled": rec.get("reconciled"), "milp_objective": s.get("objective_usd_per_week"),
        "bound": s.get("relaxation_bound"), "gap_pct": s.get("gap_to_bound_pct"), "solver_runtime": s.get("runtime_sec"),
        "wall": r.get("wall_sec_total"), "vars": s.get("variables"), "cons": s.get("constraints"),
        "restricted_to": s.get("services_in_integer_problem"), "paths": s.get("paths"),
        "reopt_gain": fr.get("gain_usd"), "repair": (fr.get("repair") or {}).get("applied"),
        "ls_applied": lsr.get("applied"), "ls_gain": lsr.get("gain_usd"), "ls_moves": len(lsr.get("moves") or []),
        "ls_terminated_by": lsr.get("terminated_by"), "ls_sec": tim.get("local_search_sec"),
        "milp_budget": tim.get("milp_budget_sec"), "milp_sec": tim.get("milp_sec"),
        "vub_applied": form.get("vub_applied"), "vub_rows": form.get("vub_rows_integer_problem"),
        "load_factor": (util.get("network") or {}).get("load_factor"),
        "served_per_vessel": (util.get("network") or {}).get("served_teu_per_vessel"),
        "flows_teu_by_strategy": flows, "flows_by_strategy": n_flows,
        "transit_p90_max": max(p90) if p90 else None, "min_slack_days": min(slack) if slack else None,
        "unserved": unserved, "cv_added": cv.get("added"), "env": d.get("env"),
        "regional_status": (r.get("regional_reconciliation") or {}).get("accounting_status"),
        "pool_hash": (d.get("pool") or {}).get("unique_order_sha256", "")[:10], "path_hash": (r.get("path_pool_sha256") or "")[:10],
        "tree": d.get("tree"), "message": s.get("message") or r.get("message"),
    }


def agg(vals):
    v = [x for x in vals if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if not v:
        return "n/a"
    sd = st.pstdev(v) if len(v) > 1 else 0.0
    return f"mean {st.mean(v):,.3f} | median {st.median(v):,.3f} | min {min(v):,.3f} | max {max(v):,.3f} | sd {sd:,.3f} (n={len(v)})"


def table(tag, rows):
    print(f"\n### {tag}\n")
    print("| seed | status | profit M | margin % | cov % | served TEU | svc | ves | LF | bound M | gap % | solver s | ledger | viol | reconciled | reopt M | LS M | notes |")
    print("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|")
    for r in rows:
        if r is None:
            print("| (missing) |" + " |" * 17)
            continue
        f = lambda x, d=2, sc=1.0: ("" if x is None else f"{x * sc:,.{d}f}")
        notes = []
        if r["ls_applied"]:
            notes.append(f"LS {r['ls_moves']} moves")
        if r["repair"]:
            notes.append("repair")
        if r["cv_added"]:
            notes.append(f"+{r['cv_added']} cand")
        print(f"| {r['seed']} | {r['solution_status']} | {f(r['profit'], 2, 1e-6)} | {f(r['margin_pct'], 1)} | {f(r['coverage_pct'], 1)} "
              f"| {f(r['served_teu'], 0)} | {r['services']} | {r['vessels']} | {f(r['load_factor'], 3)} | {f(r['bound'], 1, 1e-6)} "
              f"| {f(r['gap_pct'], 1)} | {f(r['solver_runtime'], 0)} | {r['ledger_valid']} | {r['violations']} | {r['reconciled']} "
              f"| {f(r['reopt_gain'], 2, 1e-6)} | {f(r['ls_gain'], 2, 1e-6)} | {', '.join(notes)} |")
    ok = [r for r in rows if r]
    print("\n- profit M/wk:", agg([r["profit"] / 1e6 for r in ok if r["profit"] is not None]))
    print("- coverage %:", agg([r["coverage_pct"] for r in ok]))
    print("- served TEU:", agg([r["served_teu"] for r in ok]))
    print("- services:", agg([r["services"] for r in ok]), "| vessels:", agg([r["vessels"] for r in ok]))
    print("- margin %:", agg([r["margin_pct"] for r in ok]), "| load factor:", agg([r["load_factor"] for r in ok]))
    print("- statuses:", {s: sum(1 for r in ok if r["solution_status"] == s) for s in {r["solution_status"] for r in ok}},
          "| ledger valid:", sum(1 for r in ok if r["ledger_valid"]), "/", len(ok),
          "| violations total:", sum(r["violations"] for r in ok), "| reconciled:", sum(1 for r in ok if r["reconciled"]), "/", len(ok))
    print("- negative-profit plans:", sum(1 for r in ok if (r["profit"] or 0) < 0))


def paired(a_tag, a, b_tag, b):
    print(f"\n### paired: {b_tag} - {a_tag}\n")
    print("| seed | d profit M | d coverage pp | d served TEU | d services | d vessels | profit A M | profit B M |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|")
    dp, dc, ds = [], [], []
    for x, y in zip(a, b):
        if x is None or y is None or x["profit"] is None or y["profit"] is None:
            continue
        dp.append((y["profit"] - x["profit"]) / 1e6)
        dc.append(y["coverage_pct"] - x["coverage_pct"])
        ds.append(y["served_teu"] - x["served_teu"])
        print(f"| {x['seed']} | {dp[-1]:+.2f} | {dc[-1]:+.1f} | {ds[-1]:+,.0f} | {y['services'] - x['services']:+d} | "
              f"{y['vessels'] - x['vessels']:+d} | {x['profit'] / 1e6:.2f} | {y['profit'] / 1e6:.2f} |")
    if dp:
        print(f"\n- d profit M: {agg(dp)}; positive in {sum(1 for v in dp if v > 0)}/{len(dp)} seeds, "
              f"negative in {sum(1 for v in dp if v < 0)}")
        print(f"- d coverage pp: {agg(dc)}; improved in {sum(1 for v in dc if v > 0)}/{len(dc)}, "
              f"regressed in {sum(1 for v in dc if v < 0)}")
        print(f"- d served TEU: {agg(ds)}")
        if len(dp) > 1 and st.pstdev(dp) > 0:
            se = st.stdev(dp) / math.sqrt(len(dp))
            print(f"- paired t = {st.mean(dp) / se:.2f} (n={len(dp)}, se {se:.2f} M)")


def main():
    args = sys.argv[1:]
    seeds = list(range(10))
    csv_out = None
    if "--seeds" in args:
        i = args.index("--seeds")
        lo, hi = args[i + 1].split("-")
        seeds = list(range(int(lo), int(hi) + 1))
        del args[i:i + 2]
    if "--csv" in args:
        i = args.index("--csv")
        csv_out = args[i + 1]
        del args[i:i + 2]
    tags = args
    data = {t: [load(t, s) for s in seeds] for t in tags}
    for t in tags:
        table(t, data[t])
    for t in tags[1:]:
        paired(tags[0], data[tags[0]], t, data[t])
    if csv_out:
        with open(csv_out, "w", newline="", encoding="utf-8") as fh:
            keys = ["tag", "seed", "solution_status", "profit", "revenue", "cost", "margin_pct", "coverage_pct", "served_teu",
                    "services", "vessels", "load_factor", "bound", "gap_pct", "solver_runtime", "ledger_valid", "violations",
                    "reconciled", "reopt_gain", "ls_applied", "ls_gain", "vars", "cons", "restricted_to", "pool_hash", "path_hash"]
            w = csv.writer(fh)
            w.writerow(keys)
            for t in tags:
                for r in data[t]:
                    if r:
                        w.writerow([t] + [r.get(k) for k in keys[1:]])


if __name__ == "__main__":
    main()
