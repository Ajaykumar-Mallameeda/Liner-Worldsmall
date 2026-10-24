#!/usr/bin/env python3
"""Collect one flat metrics record per run directory (same definitions for every dataset).

    python scripts/multi_dataset/collect_metrics.py [--runs reports/multi_dataset_20261016/runs] [--out metrics.json]

Reads ``driver_record.json``, ``pipeline_output.json`` and ``run.log`` of each ``<runs>/<dataset>/seed<S>``.
Nothing is estimated: a quantity the pipeline does not expose is ``null`` (and listed in ``not_exposed``).

Definitions (identical for all datasets)
    profit / revenue / itemised costs   network_ledger.weekly_usd (USD per week)
    coverage                            served TEU / total demand TEU, network_ledger.demand_teu_per_week
    services, departures/week           operated services; sum of frequency_per_week of the plan
    productive load factor              carried TEU-legs / offered TEU-legs (strategy_report.utilisation.network)
    deployment ratio                    vessels used / vessels owned (all classes)
    profit per assigned / owned vessel  weekly profit / vessels used ; / vessels owned
    solver runtime                      stage_timing.milp_sec (integer phase of the global model)
    end-to-end runtime                  dataset_run.timing_sec.pipeline (the pipeline call) and the driver's wall time
    optimality gap                      gap of the capped model to its LP bound as reported by the pipeline; the final
                                        plan is NOT claimed optimal (optimality.final_plan.optimality_claim)
    independent-ledger discrepancies    FAILED assertions of section N of tests/test_orchestrator.py (it recomputes the
                                        plan from the raw files with code that shares nothing with src/network)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS = ROOT / "reports" / "multi_dataset_20261016" / "runs"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def parse_log(log: Path) -> dict:
    """Scorecard and the failed assertions per section, from the run's console log."""
    out = {"assertions_passed": None, "assertions_failed": None, "warnings": None, "failed_assertions": [],
           "ledger_discrepancies": None, "traceback_tail": None}
    if not log.is_file():
        return out
    lines = [ANSI.sub("", ln.rstrip("\n")) for ln in log.read_text(encoding="utf-8", errors="replace").splitlines()]
    section, failed, ledger_failed, seen_n = "", [], 0, False
    for i, ln in enumerate(lines):
        if re.match(r"^\s*[A-Z0-9]{1,3}\s\.\s[A-Z]", ln):                 # section header, e.g. "N . NETWORK LEDGER ..."
            section = ln.strip()
            seen_n = seen_n or section.startswith("N .")
        if re.match(r"^\s*-\s{2}\S", ln):                      # a failed assertion line: "-  label"
            failed.append({"section": section, "assertion": ln.strip()[3:].strip()})
            if section.startswith("N ."):
                ledger_failed += 1
        m = re.search(r"Passed\s*:\s*(\d+)/(\d+)", ln)
        if m:
            out["assertions_passed"] = int(m.group(1))
        m = re.search(r"Failed\s*:\s*(\d+)/(\d+)", ln)
        if m:
            out["assertions_failed"] = int(m.group(1))
        m = re.search(r"Warnings\s*:\s*(\d+)", ln)
        if m:
            out["warnings"] = int(m.group(1))
    out["failed_assertions"] = failed[:25]
    out["ledger_discrepancies"] = ledger_failed if seen_n else None
    if "Traceback" in "\n".join(lines[-40:]):
        out["traceback_tail"] = "\n".join(lines[-12:])
    return out


def extended_block(led: dict, out: dict, dr: dict, drv: dict, stage: dict) -> dict:
    """The metrics added to the results schema (run-level, same definitions for every dataset).

    contribution margin, TEU vessel utilisation, transit time and transshipment come from
    ``network_ledger.strategy_report.extended_metrics`` (definitions are stored with them); a run whose report is not
    available gets ``null`` blocks, never an estimate.  Compute time is measured: the pipeline call, the driver's wall
    time, the optimiser stages, and the summed latency of the LLM calls (components may overlap in time, so the sum is
    a load indicator and can exceed the wall time)."""
    ext = ((led.get("strategy_report") or {}).get("extended_metrics")) or {}
    cm, ut, tr, ts = (ext.get(k) or {} for k in ("contribution_margin", "vessel_utilisation_teu", "transit_time_days", "transshipment"))
    led_ = (out.get("llm_runtime_aggregate") or {})
    calls = (led_.get("actuation_ledger") or {})
    tel = led_.get("provider_telemetry") or {}
    timing = dr.get("timing_sec") or {}
    llm_sum = sum(float(c.get("total_latency_sec") or 0.0) for c in calls.values() if isinstance(c, dict)) if calls else None
    pipeline = timing.get("pipeline")
    plan_total = stage.get("plan_total_sec")
    return {
        "contribution_margin": cm or None,
        "vessel_utilisation_teu": ut or None,
        "transit_time_days": tr or None,
        "transshipment": ts or None,
        "compute_time_sec": {
            "pipeline_total": pipeline, "driver_wall": drv.get("wall_sec"),
            "optimiser_plan_total": plan_total, "global_solver_integer_phase": stage.get("milp_sec"),
            "model_and_path_build": stage.get("model_and_paths_sec"), "local_search": stage.get("local_search_sec"),
            "flow_reopt": stage.get("flow_reopt_sec"),
            "llm_call_latency_sum": llm_sum,
            "pipeline_excluding_optimiser_plan": (pipeline - plan_total) if pipeline is not None and plan_total is not None else None,
        },
        "llm_runtime": {
            "provider_attempts": tel.get("attempts"), "provider_failures": tel.get("failures"),
            "fallback_uses": tel.get("fallback_uses"), "http_429": (tel.get("error_type_counts") or {}).get("http_429", 0),
        },
    }


def extract(run: Path) -> dict:
    drv = load(run / "driver_record.json") or {}
    out = load(run / "pipeline_output.json")
    log = parse_log(run / "run.log")
    rec = {"dataset": drv.get("dataset") or run.parent.name, "seed": drv.get("seed"), "run_dir": str(run.relative_to(ROOT)).replace("\\", "/"),
           "exit_code": drv.get("exit_code"), "killed_by_wall_cap": drv.get("killed_by_wall_cap"), "wall_sec": drv.get("wall_sec"),
           "peak_working_set_mb_python_sampled": drv.get("peak_working_set_mb_python_sampled"),
           "peak_working_set_mb_python_sum_sampled": drv.get("peak_working_set_mb_python_sum_sampled"),
           "peak_working_set_mb_cbc_sampled": drv.get("peak_working_set_mb_cbc_sampled"),
           "has_pipeline_output": out is not None, "scorecard": log, "not_exposed": []}
    if out is None:
        rec["outcome_class"] = "killed_by_wall_cap" if rec["killed_by_wall_cap"] else ("failed_before_output" if rec["exit_code"] else "no_output")
        rec["failure_tail"] = log.get("traceback_tail")
        return rec
    led = out.get("network_ledger") or {}
    dr = (out.get("test_scorecard") or {}).get("dataset_run") or out.get("dataset_run") or {}      # older runs: top-level
    w, dem, svc = led.get("weekly_usd") or {}, led.get("demand_teu_per_week") or {}, led.get("services") or {}
    fleet = led.get("fleet_by_class") or {}
    used = sum(int(v.get("used", 0)) for v in fleet.values())
    owned = sum(int(v.get("available", 0)) for v in fleet.values())
    plan_services = (led.get("plan") or {}).get("services") or []
    util = ((led.get("strategy_report") or {}).get("utilisation") or {})
    opt = led.get("optimality") or {}
    capped = opt.get("capped_model") or {}
    stage = led.get("stage_timing") or ((led.get("reconciliation") or {}).get("stage_timing")) or {}
    recon = led.get("reconciliation") or {}
    stage = recon.get("stage_timing") or stage
    pm = led.get("path_model") or {}
    calls = dr.get("global_milp_calls") or []
    final_call = calls[-1] if calls else {}
    profit = w.get("operating_profit")
    rec.update({
        "result_status": out.get("status"), "ledger_verified": led.get("verified"), "milp_status": led.get("status"),
        "weekly_profit_usd": profit, "weekly_revenue_usd": w.get("revenue"), "weekly_total_cost_usd": w.get("total_operating_cost"),
        "cost_breakdown_usd": {k: w.get(k) for k in ("vessel_cost", "fuel_cost", "port_call_fixed_cost", "handling_cost",
                                                    "transshipment_cost", "port_variable_cost")},
        "profit_margin_on_revenue": w.get("profit_margin_on_revenue"),
        "demand_total_teu": dem.get("total"), "served_teu": dem.get("served"), "unserved_teu": dem.get("unserved"),
        "coverage_pct": dem.get("coverage_pct"),
        "services_operated": svc.get("operated"), "departures_per_week": sum(int(s.get("frequency_per_week", 0)) for s in plan_services),
        "throughput_teu_per_week": dem.get("served"),
        "productive_load_factor": (util.get("network") or {}).get("load_factor"),
        "load_factor_nm_weighted": (util.get("network") or {}).get("load_factor_nm_weighted"),
        "vessels_owned": owned, "vessels_assigned": used, "vessels_idle": owned - used,
        "fleet_by_class": {c: {"owned": int(v.get("available", 0)), "assigned": int(v.get("used", 0)),
                               "idle": int(v.get("available", 0)) - int(v.get("used", 0))} for c, v in fleet.items()},
        "deployment_ratio": (used / owned) if owned else None,
        "profit_per_assigned_vessel_usd": (profit / used) if used and profit is not None else None,
        "profit_per_owned_vessel_usd": (profit / owned) if owned and profit is not None else None,
        "ledger_violations": len(led.get("violations") or []), "ledger_reconciled": recon.get("reconciled"),
        **extended_block(led, out, dr, drv, stage),
        "optimization": {
            "ports": (dr.get("counts") or {}).get("ports"), "od_records": (dr.get("counts") or {}).get("demand_records"),
            "directed_distance_pairs": (dr.get("counts") or {}).get("directed_distance_pairs"),
            "candidates_offered": svc.get("candidates_offered"), "candidates_modelled": svc.get("candidates_modelled"),
            "candidates_rejected": svc.get("candidates_rejected"), "modelled_by_class": svc.get("modelled_by_class"),
            "candidate_generation_per_region": [{"region": r.get("region"), "generated": r.get("services_generated"),
                                                 "after_regional_filter": r.get("services_filtered"),
                                                 "selected": r.get("services_selected")} for r in out.get("regional_results") or []],
            "path_model": {k: pm.get(k) for k in ("od_total", "od_with_direct", "od_transfer_only", "od_without_path",
                                                  "od_without_path_time_limit", "od_without_path_no_connection",
                                                  "paths_built", "paths_valid", "paths_dropped_by_cap",
                                                  "paths_dropped_by_time_limit", "max_paths_per_od", "max_transfers",
                                                  "path_build_sec")},
            "global_milp_calls": calls,
            "n_variables_final_call": final_call.get("n_variables"), "n_constraints_final_call": final_call.get("n_constraints"),
            "solver_backend": opt.get("solver_backend"), "solver_version": (dr.get("solver") or {}).get("cbc"),
            "milp_status": opt.get("milp_status"), "solver_status_raw": opt.get("solver_status_raw"),
            "termination": opt.get("solve_conclusion"), "time_limit_reached": capped.get("time_limit_reached"),
            "proven_optimal": capped.get("proven_optimal"), "optimality_claim_final_plan": (opt.get("final_plan") or {}).get("optimality_claim"),
            "incumbent_capped_model_usd": capped.get("incumbent_profit_usd_per_week"),
            "lp_upper_bound_usd": opt.get("relaxation_upper_bound_usd_per_week"),
            "gap_to_bound_pct": capped.get("gap_pct_of_bound"),
            "final_plan_profit_usd": (opt.get("final_plan") or {}).get("profit_usd_per_week"),
            "timing_sec": {
                "data_loading": (dr.get("timing_sec") or {}).get("problem_load"),
                "global_model_and_path_build": stage.get("model_and_paths_sec"),
                "global_solver_integer_phase": stage.get("milp_sec"), "global_solver_budget": stage.get("milp_budget_sec"),
                "local_search": stage.get("local_search_sec"), "flow_reopt": stage.get("flow_reopt_sec"),
                "global_plan_total": stage.get("plan_total_sec"),
                "pipeline_total": (dr.get("timing_sec") or {}).get("pipeline"), "driver_wall": drv.get("wall_sec")},
        },
        "dataset_run": {k: dr.get(k) for k in ("problem_source", "json_schema_version", "json_build_id", "c3_flags", "seed",
                                                "solver", "outcome_policy", "outcome_notes")},
        "outcome_class": "completed" if (out.get("status") == "complete" and led.get("verified")) else "completed_unverified_accounting",
    })
    if rec["optimization"]["n_variables_final_call"] is None:
        rec["not_exposed"].append("n_variables / n_constraints (run predates the model-size recorder)")
    rec["not_exposed"] += ["candidate rejection counts by constraint of the service generator (the pipeline reports "
                           "generated/filtered/selected per region and the global model's own rejections)",
                           "memory of solver subprocess other than the sampled CBC working set"]
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    runs = sorted(p for p in a.runs.glob("*/seed*") if p.is_dir())
    recs = [extract(p) for p in runs]
    out = a.out or (a.runs / "metrics.json")
    out.write_text(json.dumps(recs, indent=2), encoding="utf-8")
    for r in recs:
        print(f"{r['dataset']:<11} seed {r['seed']}  exit={r['exit_code']} {r.get('outcome_class')}  "
              f"profit={r.get('weekly_profit_usd')} cov={r.get('coverage_pct')} svc={r.get('services_operated')} "
              f"veh={r.get('vessels_assigned')}/{r.get('vessels_owned')} wall={r.get('wall_sec')}")
    print(f"{len(recs)} runs -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
