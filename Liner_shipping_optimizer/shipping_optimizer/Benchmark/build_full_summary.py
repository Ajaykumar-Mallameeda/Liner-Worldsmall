#!/usr/bin/env python3
"""Cross-dataset summary of a seed benchmark (default: Benchmark/seed-50), existing schema plus the added metrics.

    python Benchmark/build_full_summary.py                       # Benchmark/seed-50 -> FULL_SUMMARY_50_SEEDS.{json,md}
    python Benchmark/build_full_summary.py --root Benchmark/seed-50 --reference Benchmark   # reference = earlier 20-seed run

Reads ``<root>/<folder>/<folder>_benchmark_summary.json`` (written by run_benchmark.py after every seed) and the stored
``seed_NN.json`` records; nothing is re-computed from the pipeline. ``--reference`` compares seeds present in both runs
(weekly profit) to show how reproducible a seed is between two executions.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
from run_benchmark import FOLDERS, HEADLINE  # noqa: E402

ORDER = ["baltic", "WAF", "worldsmall", "world500", "world1000"]
NEW_METRICS = [k for k in HEADLINE if k.startswith(("contribution", "teu_", "transit_time", "transshipment", "compute_time"))]
ORIGINAL_METRICS = [k for k in HEADLINE if k not in NEW_METRICS]

FIELD_DOC = [
    ("contribution_margin.contribution_margin_usd", "USD/week", "revenue - cargo-variable costs (handling + transshipment + per-TEU port variable); profit = contribution margin - fixed service cost (vessel + fuel + port calls)"),
    ("contribution_margin.contribution_margin_per_teu_usd", "USD/TEU", "contribution margin / served TEU"),
    ("contribution_margin.contribution_margin_pct_of_revenue", "%", "100 x contribution margin / revenue"),
    ("vessel_utilisation_teu.average", "0-1", "network carried TEU-legs / offered TEU-legs (capacity-weighted); also *_service_unweighted and *_vessel_weighted"),
    ("vessel_utilisation_teu.min / .max", "0-1", "lowest / highest service load factor (each vessel inherits its service's value); leg_min / leg_max over single legs"),
    ("transit_time_days.mean", "days", "TEU-weighted mean transit time of the routed flows (sailing + port stays + transfer dwell); mean_per_flow is unweighted"),
    ("transit_time_days.min / .max", "days", "shortest / longest transit time over the routed flows; p50, p90, mean_direct, mean_transshipped also stored"),
    ("transshipment.teu", "TEU/week", "TEU of flows that change service at least once"),
    ("transshipment.share_of_served_teu_pct", "%", "100 x transshipped TEU / served TEU"),
    ("transshipment.transfer_moves_teu", "TEU-moves/week", "TEU x number of transfers (a two-transfer container counts twice)"),
    ("compute_time_sec.pipeline_total", "s", "the pipeline call end to end (includes LLM calls and every stage)"),
    ("compute_time_sec.driver_wall", "s", "the driver's wall time around the whole test process (adds start-up and report writing)"),
    ("compute_time_sec.optimiser_plan_total", "s", "network plan stage only (paths, MILP, local search, flow re-optimisation, ledger)"),
    ("compute_time_sec.llm_call_latency_sum", "s", "summed latency of the LLM calls; components may overlap, so it can exceed the wall time"),
    ("llm_runtime.http_429 / fallback_uses", "count", "rate-limited LLM calls and rule-based fallbacks; the run continues on the fallback"),
]


def fmt(x, nd=2):
    if x is None:
        return "n/a"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    return f"{x:.{nd}f}" if abs(x) >= 0.01 or x == 0 else f"{x:.4g}"


def load_records(d: Path) -> list:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("seed_*.json"))]


def reproducibility(root_recs: list, ref_dir: Path) -> dict | None:
    ref = {r["seed"]: r for r in load_records(ref_dir)} if ref_dir.is_dir() else {}
    pairs = [(r["seed"], r.get("weekly_profit_usd"), ref[r["seed"]].get("weekly_profit_usd")) for r in root_recs
             if r.get("seed") in ref and r.get("weekly_profit_usd") is not None and ref[r["seed"]].get("weekly_profit_usd") is not None]
    if not pairs:
        return None
    diffs = [abs(a - b) for _, a, b in pairs]
    return {"seeds_compared": len(pairs), "identical_profit_to_1_cent": sum(1 for x in diffs if x < 0.01),
            "max_abs_profit_diff_usd": max(diffs), "mean_abs_profit_diff_usd": sum(diffs) / len(diffs),
            "reference_mean_profit_usd": sum(b for *_, b in pairs) / len(pairs),
            "this_run_mean_profit_usd_same_seeds": sum(a for _, a, _ in pairs) / len(pairs)}


def llm_regimes(recs: list) -> dict:
    """Split the runs by what the LLM stage actually did: 'llm_assisted' = at least one provider call succeeded,
    'full_fallback' = every call failed (e.g. Groq tokens-per-day limit) and the rule-based path decided alone.
    The seeds are executed in order, so a daily limit hit mid-benchmark turns later seeds into full_fallback."""
    def assisted(r):
        t = r.get("llm_runtime") or {}
        return (t.get("provider_attempts") or 0) - (t.get("provider_failures") or 0) > 0
    out = {}
    for name, sel in (("llm_assisted", [r for r in recs if r.get("has_pipeline_output") and assisted(r)]),
                      ("full_fallback", [r for r in recs if r.get("has_pipeline_output") and not assisted(r)])):
        def med(path):
            v = sorted(x for x in (r.get("compute_time_sec", {}).get(path) for r in sel) if x is not None)
            return v[len(v) // 2] if v else None
        pr = [r["weekly_profit_usd"] for r in sel if r.get("weekly_profit_usd") is not None]
        out[name] = {"runs": len(sel), "seeds": [r["seed"] for r in sel],
                     "mean_weekly_profit_usd": (sum(pr) / len(pr)) if pr else None,
                     "median_pipeline_total_sec": med("pipeline_total"),
                     "median_optimiser_plan_sec": med("optimiser_plan_total")}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=BENCH / "seed-50")
    ap.add_argument("--reference", type=Path, default=BENCH, help="folder of an earlier run (same layout) to compare seeds with")
    ap.add_argument("--tag", default="50_SEEDS")
    a = ap.parse_args(argv)
    root = a.root.resolve()
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "root": str(root),
           "schema_new_fields": [{"path": p, "unit": u, "definition": d} for p, u, d in FIELD_DOC], "datasets": {}}
    for folder in ORDER:
        sp = root / folder / f"{folder}_benchmark_summary.json"
        if not sp.is_file():
            out["datasets"][folder] = {"status": "no summary"}
            continue
        s = json.loads(sp.read_text(encoding="utf-8"))
        recs = load_records(root / folder)
        llm = [(r.get("llm_runtime") or {}) for r in recs]
        out["datasets"][folder] = {
            "dataset": s["dataset"], "runs": s["runs"], "headline": s["headline"],
            "llm_resilience": {"runs_with_http_429": sum(1 for x in llm if (x.get("http_429") or 0) > 0),
                               "http_429_total": sum(x.get("http_429") or 0 for x in llm),
                               "fallback_uses_total": sum(x.get("fallback_uses") or 0 for x in llm),
                               "runs_with_llm_failure_lines": sum(1 for p in s["per_seed"] if (p.get("llm_failed_call_lines") or 0) > 0)},
            "llm_regimes": llm_regimes(recs),
            "reproducibility_vs_reference": reproducibility(recs, a.reference.resolve() / folder),
            "metric_count_all_metrics": len(s["all_metrics"]),
        }
    (root / f"FULL_SUMMARY_{a.tag}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    md = [f"# Full {a.tag.replace('_', ' ').lower()} summary - C3 pipeline, tests/test_orchestrator.py",
          f"Generated {out['generated_utc']} from `{root.name}/<dataset>/seed_NN.json`. Sample statistics (n-1). "
          "Per-run detail: `<dataset>/seed_NN.json`, full artifacts: `<dataset>/runs/seed_NN/`.", "", "## Run status", "",
          "| dataset | runs | with output | exit 0 | ledger verified | failed/killed | LLM 429 (runs / calls) | distinct profit values |",
          "|---|---|---|---|---|---|---|---|"]
    for f in ORDER:
        d = out["datasets"][f]
        if "runs" not in d:
            md.append(f"| {f} | - | - | - | - | - | - | - |")
            continue
        r, l = d["runs"], d["llm_resilience"]
        md.append(f"| {f} | {r['n_runs']} | {r['n_with_pipeline_output']} | {r['n_exit_code_0']} | {r['n_ledger_verified']} | "
                  f"{len(r['failed_or_killed_runs'])} | {l['runs_with_http_429']} / {l['http_429_total']} | {r['n_distinct_profit_values']} |")
    md += ["", "## LLM availability during the runs", "",
           "Seeds run in order; when the provider's daily limit is reached the remaining seeds run on the rule-based fallback "
           "(decisions without LLM guidance, ~seconds instead of minutes). Compute time is therefore reported by regime; "
           "`optimiser_plan_sec` (the network optimiser alone) does not depend on the LLM.", "",
           "| dataset | LLM-assisted runs | full-fallback runs | mean profit assisted | mean profit fallback | median pipeline s (assisted / fallback) | median optimiser s (assisted / fallback) |",
           "|---|---|---|---|---|---|---|"]
    for f in ORDER:
        g = (out["datasets"][f].get("llm_regimes") or {})
        if not g:
            continue
        a_, b_ = g["llm_assisted"], g["full_fallback"]
        md.append(f"| {f} | {a_['runs']} | {b_['runs']} | {fmt(a_['mean_weekly_profit_usd'])} | {fmt(b_['mean_weekly_profit_usd'])} | "
                  f"{fmt(a_['median_pipeline_total_sec'])} / {fmt(b_['median_pipeline_total_sec'])} | "
                  f"{fmt(a_['median_optimiser_plan_sec'])} / {fmt(b_['median_optimiser_plan_sec'])} |")
    for title, names in (("Original metrics", ORIGINAL_METRICS), ("Added metrics", NEW_METRICS)):
        md += ["", f"## {title} - mean over seeds", "", "| metric | " + " | ".join(ORDER) + " |", "|---|" + "---|" * len(ORDER)]
        for n in names:
            md.append(f"| {n} | " + " | ".join(fmt(((out['datasets'][f].get('headline') or {}).get(n) or {}).get('mean')) for f in ORDER) + " |")
    md += ["", "## Per-dataset statistics (min / mean / median / max / std dev)", ""]
    for f in ORDER:
        d = out["datasets"][f]
        if "headline" not in d:
            continue
        md += [f"### {f} ({d['runs']['n_with_pipeline_output']} runs with output)", "",
               "| metric | min | mean | median | max | std dev | cv % |", "|---|---|---|---|---|---|---|"]
        for n in ORIGINAL_METRICS + NEW_METRICS:
            m = d["headline"].get(n)
            if m:
                md.append(f"| {n} | {fmt(m['min'])} | {fmt(m['mean'])} | {fmt(m['median'])} | {fmt(m['max'])} | "
                          f"{fmt(m['std_dev'])} | {fmt(m['cv_pct'])} |")
        rp = d.get("reproducibility_vs_reference")
        if rp:
            md += ["", f"Seeds {rp['seeds_compared']} shared with the earlier run: {rp['identical_profit_to_1_cent']} identical weekly profit "
                   f"(to 1 cent), max difference {fmt(rp['max_abs_profit_diff_usd'])} USD, mean {fmt(rp['mean_abs_profit_diff_usd'])} USD."]
        if d["runs"]["failed_or_killed_runs"]:
            md += ["", f"Failed or killed runs: {d['runs']['failed_or_killed_runs']}"]
        md.append("")
    md += ["## Added schema fields", "", "| path in seed_NN.json | unit | definition |", "|---|---|---|"]
    md += [f"| `{p}` | {u} | {d} |" for p, u, d in FIELD_DOC]
    (root / f"FULL_SUMMARY_{a.tag}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {root / f'FULL_SUMMARY_{a.tag}.json'} and .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
