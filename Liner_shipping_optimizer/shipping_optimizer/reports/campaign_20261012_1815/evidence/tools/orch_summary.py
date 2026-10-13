"""Summarise end-to-end orchestrator runs (pipeline_output.json + pytest log).

usage: python orch_summary.py <tag_prefix> [<tag_prefix> ...]   (reads evidence/runs/<prefix>*.pipeline_output.json)
"""
import json
import re
import statistics as st
import sys
from pathlib import Path

RUNS = Path(r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer\reports\campaign_20261012_1815\evidence\runs")


def summarise(prefix: str):
    rows = []
    for po in sorted(RUNS.glob(f"{prefix}*.pipeline_output.json")):
        name = po.name.replace(".pipeline_output.json", "")
        d = json.loads(po.read_text(encoding="utf-8"))
        nl = d.get("network_ledger", {})
        sr = nl.get("strategy_report", {})
        t = sr.get("totals", {})
        opt = nl.get("optimality", {})
        sm = d.get("summary_metrics", {})
        fr = opt.get("flow_reoptimisation") or {}
        ls = opt.get("local_search") or {}
        form = opt.get("formulation") or {}
        aug = nl.get("candidate_augmentation") or {}
        log = RUNS / f"{name}.log"
        passed = failed = None
        if log.exists():
            txt = log.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"Passed\s*:\s*(\d+)/(\d+)", txt)
            f = re.search(r"Failed\s*:\s*(\d+)/(\d+)", txt)
            passed = f"{m.group(1)}/{m.group(2)}" if m else None
            failed = f.group(1) if f else None
        iters = []
        for it in d.get("iteration_results", []):
            n = it.get("network_ledger", {}) or {}
            tt = (n.get("strategy_report") or {}).get("totals", {})
            iters.append((round(tt.get("operating_profit", 0) / 1e6, 2), round(tt.get("coverage_pct", 0), 1),
                          (n.get("optimality") or {}).get("milp_status")))
        by = sr.get("by_strategy", {})
        p90 = [v.get("transit_days_p90") for v in by.values() if v.get("transit_days_p90") is not None]
        slack = [v.get("min_slack_to_limit_days") for v in by.values() if v.get("min_slack_to_limit_days") is not None]
        rev = sm.get("revenue") or 0
        rows.append({
            "run": name, "status": d.get("status"), "assertions": passed, "failed": failed,
            "selected_iteration": d.get("final_selected_iteration"),
            "profit_M": (t.get("operating_profit") or 0) / 1e6,
            "margin_pct": 100 * (t.get("operating_profit") or 0) / rev if rev else None,
            "coverage_pct": t.get("coverage_pct"), "served_teu": t.get("served_teu"),
            "services": sm.get("total_services"), "vessels": (sr.get("utilisation", {}).get("fleet") or {}).get("vessels_used"),
            "load_factor": (sr.get("utilisation", {}).get("network") or {}).get("load_factor"),
            "ledger_verified": nl.get("verified"), "violations": len(nl.get("violations") or []),
            "milp_status": opt.get("milp_status"), "bound_M": (opt.get("relaxation_upper_bound_usd_per_week") or 0) / 1e6,
            "reopt_gain_M": (fr.get("gain_usd") or 0) / 1e6, "ls_applied": ls.get("applied"), "ls_gain_M": (ls.get("gain_usd") or 0) / 1e6,
            "vub": form.get("vub_applied"), "cv_added": aug.get("added"),
            "transit_p90_max": max(p90) if p90 else None, "min_slack": min(slack) if slack else None,
            "runtime_s": sm.get("total_runtime"), "iterations": iters,
            "vessels_by_class": {c: v.get("vessels_used") for c, v in (sr.get("utilisation", {}).get("fleet", {}).get("by_class") or {}).items()},
        })
    return rows


def main():
    for prefix in sys.argv[1:]:
        rows = summarise(prefix)
        print(f"\n### {prefix}\n")
        print("| run | assertions | status | iter | profit M | margin % | cov % | served | svc | ves | LF | ledger | viol | MILP | bound M | reopt M | LS M | p90 max d | min slack d | s |")
        print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---:|---:|")
        for r in rows:
            print(f"| {r['run']} | {r['assertions']} | {r['status']} | {r['selected_iteration']} | {r['profit_M']:.2f} | "
                  f"{(r['margin_pct'] or 0):.1f} | {(r['coverage_pct'] or 0):.1f} | {(r['served_teu'] or 0):,.0f} | {r['services']} | "
                  f"{r['vessels']} | {(r['load_factor'] or 0):.3f} | {r['ledger_verified']} | {r['violations']} | {r['milp_status']} | "
                  f"{r['bound_M']:.1f} | {r['reopt_gain_M']:.2f} | {r['ls_gain_M']:.2f} | {(r['transit_p90_max'] or 0):.1f} | "
                  f"{(r['min_slack'] or 0):.3f} | {(r['runtime_s'] or 0):.0f} |")
        for r in rows:
            print(f"  - {r['run']}: iterations (profit M, cov %, milp) {r['iterations']}; vub={r['vub']}; ls_applied={r['ls_applied']}; "
                  f"cv_added={r['cv_added']}; vessels {r['vessels_by_class']}")
        if rows:
            print(f"\n- profit M: mean {st.mean(r['profit_M'] for r in rows):.2f} (min {min(r['profit_M'] for r in rows):.2f}, "
                  f"max {max(r['profit_M'] for r in rows):.2f}); coverage % mean "
                  f"{st.mean((r['coverage_pct'] or 0) for r in rows):.1f}; assertions {[r['assertions'] for r in rows]}")


if __name__ == "__main__":
    main()
