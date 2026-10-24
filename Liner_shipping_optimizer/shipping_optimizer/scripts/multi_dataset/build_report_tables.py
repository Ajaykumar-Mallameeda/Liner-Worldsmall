#!/usr/bin/env python3
"""Turn ``runs/metrics.json`` into the comparison and scalability tables (markdown) used by the final report.

    python scripts/multi_dataset/build_report_tables.py [--metrics <metrics.json>] [--out <tables.md>]

Per dataset: runs, outcome classes, mean / min / max over the seeds that completed with a verified ledger.
Scalability: World-500 versus World-1000 growth factors (ports, ODs, distance records, candidates, model size, runtime,
profit) measured, never assumed. Everything is computed from the run records; nothing is typed in.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "reports" / "multi_dataset_20261016" / "runs" / "metrics.json"
ORDER = ["WorldSmall", "baltic", "WAF", "World-500", "World-1000"]


def get(r, path, default=None):
    cur = r
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def agg(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"n": len(vals), "mean": st.mean(vals), "min": min(vals), "max": max(vals),
            "sd": st.pstdev(vals) if len(vals) > 1 else 0.0}


def fmt(a, scale=1.0, nd=2, unit=""):
    if a is None:
        return "n/a"
    if a["n"] == 1:
        return f"{a['mean'] / scale:,.{nd}f}{unit}"
    return f"{a['mean'] / scale:,.{nd}f}{unit} ({a['min'] / scale:,.{nd}f}-{a['max'] / scale:,.{nd}f})"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metrics", type=Path, default=DEFAULT)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    recs = json.loads(a.metrics.read_text(encoding="utf-8"))
    by = {k: [r for r in recs if r["dataset"] == k] for k in ORDER}
    L = []

    L.append("## Run inventory\n")
    L.append("| dataset | runs | completed + ledger verified | failed / no output | killed by wall cap | independent-ledger discrepancies (sum) | assertions failed (sum) |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for k in ORDER:
        rs = by[k]
        if not rs:
            L.append(f"| {k} | 0 | - | - | - | - | - |")
            continue
        ok = [r for r in rs if r.get("outcome_class") == "completed"]
        L.append(f"| {k} | {len(rs)} | {len(ok)} | {sum(1 for r in rs if not r['has_pipeline_output'])} | "
                 f"{sum(1 for r in rs if r.get('killed_by_wall_cap'))} | "
                 f"{sum((r['scorecard'].get('ledger_discrepancies') or 0) for r in rs)} | "
                 f"{sum((r['scorecard'].get('assertions_failed') or 0) for r in rs)} |")

    L.append("\n## Economics (mean, min-max over verified runs; USD per week)\n")
    L.append("| dataset | n | profit (M) | revenue (M) | total cost (M) | margin % | coverage % | served TEU/wk | demand TEU/wk | services | departures/wk | prod. load factor |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for k in ORDER:
        ok = [r for r in by[k] if r.get("outcome_class") == "completed"]
        if not ok:
            continue
        g = lambda f: agg([r.get(f) for r in ok])
        L.append(f"| {k} | {len(ok)} | {fmt(g('weekly_profit_usd'), 1e6)} | {fmt(g('weekly_revenue_usd'), 1e6)} | "
                 f"{fmt(g('weekly_total_cost_usd'), 1e6)} | {fmt(agg([100 * r['profit_margin_on_revenue'] for r in ok]), 1, 1)} | "
                 f"{fmt(g('coverage_pct'), 1, 1)} | {fmt(g('served_teu'), 1, 0)} | {fmt(g('demand_total_teu'), 1, 0)} | "
                 f"{fmt(g('services_operated'), 1, 1)} | {fmt(g('departures_per_week'), 1, 1)} | {fmt(g('productive_load_factor'), 1, 3)} |")

    L.append("\n## Cost breakdown (mean, M USD per week)\n")
    L.append("| dataset | vessel | fuel | port call fixed (incl. canal) | handling | transshipment | port variable |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for k in ORDER:
        ok = [r for r in by[k] if r.get("outcome_class") == "completed"]
        if ok:
            c = lambda f: fmt(agg([r["cost_breakdown_usd"][f] for r in ok]), 1e6, 3)
            L.append(f"| {k} | {c('vessel_cost')} | {c('fuel_cost')} | {c('port_call_fixed_cost')} | {c('handling_cost')} | "
                     f"{c('transshipment_cost')} | {c('port_variable_cost')} |")

    L.append("\n## Fleet deployment\n")
    L.append("| dataset | vessels owned | assigned | idle | deployment ratio | profit / assigned vessel (k) | profit / owned vessel (k) |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for k in ORDER:
        ok = [r for r in by[k] if r.get("outcome_class") == "completed"]
        if ok:
            g = lambda f: agg([r.get(f) for r in ok])
            L.append(f"| {k} | {ok[0]['vessels_owned']} | {fmt(g('vessels_assigned'), 1, 1)} | {fmt(g('vessels_idle'), 1, 1)} | "
                     f"{fmt(g('deployment_ratio'), 1, 3)} | {fmt(g('profit_per_assigned_vessel_usd'), 1e3, 1)} | "
                     f"{fmt(g('profit_per_owned_vessel_usd'), 1e3, 1)} |")

    L.append("\n## Solver and runtime (seconds unless stated)\n")
    L.append("| dataset | n | termination of the global model | time limit reached | gap to LP bound % (capped model) | data load | model+paths | global solver (integer phase) | pipeline total | driver wall | peak RSS python (MB, sampled) | peak RSS sum (MB) | peak CBC (MB) |")
    L.append("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for k in ORDER:
        ok = [r for r in by[k] if r.get("has_pipeline_output")]
        if not ok:
            continue
        o = lambda f: agg([get(r, "optimization." + f) for r in ok])
        term = ", ".join(sorted({str(get(r, "optimization.termination")) for r in ok}))
        L.append(f"| {k} | {len(ok)} | {term} | {sum(1 for r in ok if get(r, 'optimization.time_limit_reached'))}/{len(ok)} | "
                 f"{fmt(o('gap_to_bound_pct'), 1, 1)} | {fmt(o('timing_sec.data_loading'), 1, 2)} | "
                 f"{fmt(o('timing_sec.global_model_and_path_build'), 1, 1)} | {fmt(o('timing_sec.global_solver_integer_phase'), 1, 1)} | "
                 f"{fmt(o('timing_sec.pipeline_total'), 1, 0)} | {fmt(agg([r['wall_sec'] for r in ok]), 1, 0)} | "
                 f"{fmt(agg([r.get('peak_working_set_mb_python_sampled') for r in ok if (r.get('peak_working_set_mb_python_sampled') or 0) > 50]), 1, 0)} | "
                 f"{fmt(agg([r.get('peak_working_set_mb_python_sum_sampled') for r in ok if (r.get('peak_working_set_mb_python_sum_sampled') or 0) > 50]), 1, 0)} | "
                 f"{fmt(agg([r.get('peak_working_set_mb_cbc_sampled') for r in ok if r.get('peak_working_set_mb_cbc_sampled')]), 1, 0)} |")

    L.append("\n## Model dimensions\n")
    L.append("| dataset | ports | OD records | directed distance pairs | candidates offered | paths built | paths dropped (time limit) | ODs without any path | variables (final global MILP) | constraints |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for k in ORDER:
        ok = [r for r in by[k] if r.get("has_pipeline_output")]
        if not ok:
            continue
        r = ok[0]
        o = r["optimization"]
        pm = o["path_model"]
        nv = agg([get(x, "optimization.n_variables_final_call") for x in ok])
        nc = agg([get(x, "optimization.n_constraints_final_call") for x in ok])
        L.append(f"| {k} | {o['ports']} | {o['od_records']} | {o['directed_distance_pairs']} | {fmt(agg([x['optimization']['candidates_offered'] for x in ok]), 1, 0)} | "
                 f"{fmt(agg([x['optimization']['path_model']['paths_built'] for x in ok]), 1, 0)} | "
                 f"{fmt(agg([x['optimization']['path_model']['paths_dropped_by_time_limit'] for x in ok]), 1, 0)} | "
                 f"{fmt(agg([x['optimization']['path_model']['od_without_path'] for x in ok]), 1, 0)} | {fmt(nv, 1, 0)} | {fmt(nc, 1, 0)} |")

    s5 = [r for r in by["World-500"] if r.get("has_pipeline_output")]
    s10 = [r for r in by["World-1000"] if r.get("has_pipeline_output")]
    if s5 and s10:
        L.append("\n## Scalability: World-500 -> World-1000 (measured growth factor = World-1000 / World-500, means over seeds)\n")
        L.append("| quantity | World-500 | World-1000 | factor |")
        L.append("|---|---:|---:|---:|")
        rows = [("ports", "optimization.ports"), ("OD records", "optimization.od_records"),
                ("directed distance records", "optimization.directed_distance_pairs"),
                ("candidate services offered", "optimization.candidates_offered"),
                ("paths built", "optimization.path_model.paths_built"),
                ("paths valid before cap", "optimization.path_model.paths_valid"),
                ("paths dropped by time limit", "optimization.path_model.paths_dropped_by_time_limit"),
                ("ODs without a path", "optimization.path_model.od_without_path"),
                ("MILP variables (final global solve)", "optimization.n_variables_final_call"),
                ("MILP constraints (final global solve)", "optimization.n_constraints_final_call"),
                ("data loading (s)", "optimization.timing_sec.data_loading"),
                ("model + path build (s)", "optimization.timing_sec.global_model_and_path_build"),
                ("global solver integer phase (s)", "optimization.timing_sec.global_solver_integer_phase"),
                ("pipeline total (s)", "optimization.timing_sec.pipeline_total"),
                ("weekly demand (TEU)", "demand_total_teu"), ("served TEU", "served_teu"),
                ("weekly profit (USD)", "weekly_profit_usd"), ("weekly revenue (USD)", "weekly_revenue_usd"),
                ("services operated", "services_operated"), ("vessels assigned", "vessels_assigned"),
                ("vessels owned", "vessels_owned"), ("coverage %", "coverage_pct")]
        for name, path in rows:
            a5, a10 = agg([get(r, path) for r in s5]), agg([get(r, path) for r in s10])
            if a5 and a10 and a5["mean"]:
                L.append(f"| {name} | {a5['mean']:,.1f} | {a10['mean']:,.1f} | {a10['mean'] / a5['mean']:.2f}x |")
        L.append("\nPorts grow 2.00x by construction; any other factor above is what was measured on these runs.")

    out = a.out or a.metrics.with_name("tables.md")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
