#!/usr/bin/env python3
"""Seed benchmark of the accepted C3 pipeline: every dataset is run once per seed with tests/test_orchestrator.py.

    python Benchmark/run_benchmark.py --datasets baltic                  # 20 seeds (0-19), then the summary
    python Benchmark/run_benchmark.py --datasets baltic WAF worldsmall   # datasets strictly one after the other
    python Benchmark/run_benchmark.py --datasets world500 --seeds 0 1 2  # a subset of seeds
    python Benchmark/run_benchmark.py --datasets baltic --summarize-only # rebuild the summary from stored seeds

Layout (one folder per dataset below ``Benchmark/``)::

    Benchmark/<folder>/seed_NN.json                one metrics record per run (collect_metrics.extract definitions)
    Benchmark/<folder>/runs/seed_NN/               the run's full artifacts (pipeline_output.json, run.log, ...)
    Benchmark/<folder>/<folder>_benchmark_summary.json   min / max / mean / median / std dev / variance of every metric

Runs are strictly sequential (the global MILP has a wall-clock budget; concurrent runs would change the result and
the runtimes). Nothing about the pipeline is configured here: the test applies the C3 flags itself, the driver only sets
``--seed`` and ``PYTHONHASHSEED=0`` (run_campaign.run_one). A seed whose ``seed_NN.json`` exists is skipped, so an
interrupted benchmark resumes where it stopped. Statistics are over the runs that produced a pipeline output; failed
runs are counted and listed, never hidden. Standard deviation / variance are the SAMPLE statistics (n - 1).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "multi_dataset"))

import collect_metrics  # noqa: E402
import run_campaign  # noqa: E402

# benchmark folder -> registry key (the spelling the registry / test_orchestrator.py use)
FOLDERS = {"baltic": "baltic", "WAF": "WAF", "worldsmall": "WorldSmall", "world500": "World-500", "world1000": "World-1000"}
DEFAULT_SEEDS = list(range(20))
DEFAULT_WALL_CAP_SEC = 10800          # safety net around one whole pipeline run; NOT the 120 s solver budget

# headline metric -> path in the flattened record (the first block of every summary)
HEADLINE = {
    "weekly_profit_usd": "weekly_profit_usd",
    "weekly_revenue_usd": "weekly_revenue_usd",
    "weekly_total_cost_usd": "weekly_total_cost_usd",
    "profit_margin_on_revenue": "profit_margin_on_revenue",
    "coverage_pct": "coverage_pct",
    "served_teu": "served_teu",
    "unserved_teu": "unserved_teu",
    "services_operated": "services_operated",
    "departures_per_week": "departures_per_week",
    "vessels_assigned": "vessels_assigned",
    "vessels_idle": "vessels_idle",
    "deployment_ratio (vessel utilisation)": "deployment_ratio",
    "productive_load_factor (capacity utilisation)": "productive_load_factor",
    "profit_per_assigned_vessel_usd": "profit_per_assigned_vessel_usd",
    "pipeline_runtime_sec": "optimization.timing_sec.pipeline_total",
    "driver_wall_sec": "wall_sec",
    "global_solver_integer_phase_sec": "optimization.timing_sec.global_solver_integer_phase",
    "gap_to_lp_bound_pct": "optimization.gap_to_bound_pct",
    # metrics added to the schema for the 50-seed benchmark (definitions are stored in each run's strategy report)
    "contribution_margin_usd": "contribution_margin.contribution_margin_usd",
    "contribution_margin_per_teu_usd": "contribution_margin.contribution_margin_per_teu_usd",
    "contribution_margin_pct_of_revenue": "contribution_margin.contribution_margin_pct_of_revenue",
    "teu_vessel_utilisation_average": "vessel_utilisation_teu.average",
    "teu_vessel_utilisation_min": "vessel_utilisation_teu.min",
    "teu_vessel_utilisation_max": "vessel_utilisation_teu.max",
    "transit_time_days_average (TEU-weighted)": "transit_time_days.mean",
    "transit_time_days_min": "transit_time_days.min",
    "transit_time_days_max": "transit_time_days.max",
    "teu_through_transshipment": "transshipment.teu",
    "teu_through_transshipment_share_pct": "transshipment.share_of_served_teu_pct",
    "transshipment_transfer_moves_teu": "transshipment.transfer_moves_teu",
    "compute_time_pipeline_sec": "compute_time_sec.pipeline_total",
    "compute_time_driver_wall_sec": "compute_time_sec.driver_wall",
    "compute_time_optimiser_plan_sec": "compute_time_sec.optimiser_plan_total",
    "compute_time_llm_latency_sum_sec": "compute_time_sec.llm_call_latency_sum",
}
# nested groups that are not scalar metrics (lists of regions / solver calls / flags)
SKIP_PREFIXES = ("dataset_run.", "optimization.global_milp_calls", "optimization.candidate_generation_per_region",
                 "scorecard.failed_assertions", "scorecard.traceback_tail", "not_exposed", "optimization.modelled_by_class")


def flatten(d, prefix="") -> dict:
    """Numeric (non-bool) leaves of a nested record, keyed by dotted path."""
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if any(key.startswith(p) for p in SKIP_PREFIXES):
            continue
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[key] = float(v)
    return out


def describe(values: list) -> dict:
    n = len(values)
    mean = statistics.fmean(values)
    var = statistics.variance(values) if n > 1 else 0.0
    sd = var ** 0.5
    return {"n": n, "min": min(values), "max": max(values), "mean": mean, "median": statistics.median(values),
            "std_dev": sd, "variance": var, "range": max(values) - min(values),
            "cv_pct": (100.0 * sd / abs(mean)) if mean else None}


def _llm_failures(run_dir: Path):
    """Number of ``llm_all_providers_failed`` lines of the run's log (LLM calls that fell back); None without a log."""
    try:
        return run_dir.joinpath("run.log").read_text(encoding="utf-8", errors="replace").count("llm_all_providers_failed")
    except OSError:
        return None


def summarize(folder: str, key: str, root: Path = BENCH) -> Path:
    d = root / folder
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("seed_*.json"))]
    usable = [r for r in recs if r.get("has_pipeline_output")]
    flat = [flatten(r) for r in usable]
    paths = sorted({p for f in flat for p in f})
    metrics = {p: describe([f[p] for f in flat if p in f]) for p in paths}
    headline = {name: metrics[p] for name, p in HEADLINE.items() if p in metrics}
    profits = [r.get("weekly_profit_usd") for r in usable if r.get("weekly_profit_usd") is not None]
    summary = {
        "benchmark": "C3 pipeline, tests/test_orchestrator.py, one run per seed",
        "dataset": key, "folder": folder, "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "statistics_note": "sample standard deviation and sample variance (n-1); cv_pct = 100*std_dev/|mean|; "
                           "statistics are over the runs that produced a pipeline output",
        "runs": {
            "seeds_found": [r.get("seed") for r in recs], "n_runs": len(recs), "n_with_pipeline_output": len(usable),
            "n_exit_code_0": sum(1 for r in recs if r.get("exit_code") == 0),
            "n_ledger_verified": sum(1 for r in usable if r.get("ledger_verified")),
            "failed_or_killed_runs": [{"seed": r.get("seed"), "exit_code": r.get("exit_code"),
                                    "killed_by_wall_cap": r.get("killed_by_wall_cap"),
                                    "assertions_failed": (r.get("scorecard") or {}).get("assertions_failed")}
                                   for r in recs if r.get("exit_code") != 0 or not r.get("has_pipeline_output")],
            "n_distinct_profit_values": len({round(p, 2) for p in profits}),
            "ledger_discrepancies_total": sum((r.get("scorecard") or {}).get("ledger_discrepancies") or 0 for r in recs),
        },
        "headline": headline,
        "all_metrics": metrics,
        "per_seed": [{"seed": r.get("seed"), "weekly_profit_usd": r.get("weekly_profit_usd"),
                      "coverage_pct": r.get("coverage_pct"), "services_operated": r.get("services_operated"),
                      "vessels_assigned": r.get("vessels_assigned"),
                      "contribution_margin_usd": (r.get("contribution_margin") or {}).get("contribution_margin_usd"),
                      "contribution_margin_per_teu_usd": (r.get("contribution_margin") or {}).get("contribution_margin_per_teu_usd"),
                      "teu_vessel_utilisation": {k: (r.get("vessel_utilisation_teu") or {}).get(k) for k in ("average", "min", "max")},
                      "transit_time_days": {k: (r.get("transit_time_days") or {}).get(k) for k in ("mean", "min", "max")},
                      "teu_through_transshipment": (r.get("transshipment") or {}).get("teu"),
                      "compute_time_sec": r.get("compute_time_sec"),
                      "llm_http_429": (r.get("llm_runtime") or {}).get("http_429"),
                      "pipeline_runtime_sec": ((r.get("optimization") or {}).get("timing_sec") or {}).get("pipeline_total"),
                      "exit_code": r.get("exit_code"), "llm_failed_call_lines": _llm_failures(d / "runs" / f"seed_{r.get('seed'):02d}")}
                     for r in recs],
    }
    out = d / f"{folder}_benchmark_summary.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return out


def run_dataset(folder: str, seeds: list, wall_cap: float | None, root: Path = BENCH) -> None:
    key = FOLDERS[folder]
    d = root / folder
    (d / "runs").mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        rec_path = d / f"seed_{seed:02d}.json"
        if rec_path.is_file():
            print(f"[{folder} seed {seed:02d}] skipped (seed_{seed:02d}.json exists)", flush=True)
            continue
        print(f"[{folder} seed {seed:02d}] running ...", flush=True)
        run_dir = d / "runs" / f"seed_{seed:02d}"
        drv = run_campaign.run_one(key, seed, d / "runs", wall_cap, {}, out_dir=run_dir)
        rec = collect_metrics.extract(run_dir)
        rec_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        print(f"[{folder} seed {seed:02d}] exit={drv['exit_code']} wall={drv['wall_sec']} s "
              f"profit={rec.get('weekly_profit_usd')} cov={rec.get('coverage_pct')} "
              f"services={rec.get('services_operated')} outcome={rec.get('outcome_class')}", flush=True)
        summarize(folder, key, root)      # running summary: always current after every seed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datasets", nargs="+", required=True, choices=sorted(FOLDERS), help="benchmark folder names, run in the order given")
    ap.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    ap.add_argument("--n-seeds", type=int, default=None, help="seeds 0..N-1 (overrides --seeds), e.g. 50")
    ap.add_argument("--out-root", type=Path, default=BENCH,
                    help="folder holding one sub-folder per dataset (default Benchmark/; the 50-seed run uses Benchmark/seed-50)")
    ap.add_argument("--wall-cap-sec", type=float, default=DEFAULT_WALL_CAP_SEC)
    ap.add_argument("--summarize-only", action="store_true")
    a = ap.parse_args(argv)
    seeds = list(range(a.n_seeds)) if a.n_seeds else a.seeds
    root = a.out_root.resolve()
    for folder in a.datasets:
        if not a.summarize_only:
            run_dataset(folder, seeds, a.wall_cap_sec, root)
        out = summarize(folder, FOLDERS[folder], root)
        print(f"[{folder}] summary -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
