"""
Read-only catalog of optimizer runs for the dashboard.

Serves the current pipeline_output.json and the frozen 30-seed benchmark
(Benchmark/seed-30/<dataset>/...) without touching the optimizer. Every
file response carries ETag / Last-Modified and answers conditional requests
with 304, so the dashboard can poll cheaply.
"""

import json
import os
import re
from email.utils import formatdate, parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

REPO_ROOT = Path(__file__).resolve().parent.parent
CURRENT_OUTPUT = REPO_ROOT / "pipeline_output.json"
BENCHMARK_ROOT = Path(os.environ.get("BENCHMARK_ROOT", REPO_ROOT / "Benchmark" / "seed-30"))
FULL_SUMMARY = BENCHMARK_ROOT / "FULL_SUMMARY_30_SEEDS.json"
# Runs kept outside the frozen benchmark (one folder per run, each with pipeline_output.json and an optional
# meta.json {"label", "note"}): e.g. a run made after the 2026-10-24 output additions (GA history, leg times).
EXTRA_RUNS_ROOT = Path(os.environ.get("EXTRA_RUNS_ROOT", REPO_ROOT / "runs_extra"))

_SEED_FILE = re.compile(r"^seed_(\d{2,3})\.json$")
_RUN_ID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")

# Per-seed fields the Benchmarks tab plots (flat numbers only).
_SEED_FIELDS = (
    "weekly_profit_usd", "weekly_revenue_usd", "weekly_total_cost_usd", "profit_margin_on_revenue",
    "coverage_pct", "served_teu", "unserved_teu", "services_operated", "vessels_assigned",
    "deployment_ratio", "productive_load_factor", "wall_sec",
)

router = APIRouter()


def _datasets() -> Dict[str, Path]:
    """Dataset key -> folder, for every folder under the benchmark root that holds seed files."""
    if not BENCHMARK_ROOT.is_dir():
        return {}
    out = {}
    for d in sorted(BENCHMARK_ROOT.iterdir()):
        if d.is_dir() and any(_SEED_FILE.match(p.name) for p in d.iterdir()):
            out[d.name] = d
    return out


def _dataset_dir(dataset: str) -> Path:
    dirs = _datasets()
    if dataset not in dirs:
        raise HTTPException(status_code=404, detail=f"unknown dataset '{dataset}'")
    return dirs[dataset]


def _conditional_file(request: Request, path: Path, media_type: str = "application/json") -> Response:
    """FileResponse with a validator pair; 304 when the client already has this version."""
    if not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    st = path.stat()
    etag = f'W/"{st.st_mtime_ns:x}-{st.st_size:x}"'
    last_modified = formatdate(st.st_mtime, usegmt=True)
    headers = {"ETag": etag, "Last-Modified": last_modified, "Cache-Control": "no-cache"}

    inm = request.headers.get("if-none-match")
    if inm and etag in [t.strip() for t in inm.split(",")]:
        return Response(status_code=304, headers=headers)
    ims = request.headers.get("if-modified-since")
    if ims and not inm:
        try:
            if int(st.st_mtime) <= int(parsedate_to_datetime(ims).timestamp()):
                return Response(status_code=304, headers=headers)
        except (TypeError, ValueError):
            pass
    return FileResponse(str(path), media_type=media_type, headers=headers)


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _regime_by_seed(dataset_key: str) -> Dict[int, str]:
    """Seed -> 'llm_assisted' | 'full_fallback', from the summary's llm_regimes block."""
    summary = _read_json(FULL_SUMMARY) or {}
    regimes = ((summary.get("datasets") or {}).get(dataset_key) or {}).get("llm_regimes") or {}
    out = {}
    for regime, block in regimes.items():
        for s in (block or {}).get("seeds") or []:
            out[int(s)] = regime
    return out


def _sub(rec: Dict[str, Any], block: str, key: str):
    v = rec.get(block)
    return v.get(key) if isinstance(v, dict) else None


def _path(rec: Dict[str, Any], dotted: str):
    v: Any = rec
    for k in dotted.split("."):
        if not isinstance(v, dict):
            return None
        v = v.get(k)
    return v


# Extra per-seed figures for the Benchmarks tab's detail sections: output key -> dotted path in seed_NN.json
_DETAIL_FIELDS = {
    "demand_total_teu": "demand_total_teu",
    "departures_per_week": "departures_per_week",
    "vessels_owned": "vessels_owned",
    "vessels_idle": "vessels_idle",
    "profit_per_assigned_vessel_usd": "profit_per_assigned_vessel_usd",
    "cost_vessel_usd": "cost_breakdown_usd.vessel_cost",
    "cost_fuel_usd": "cost_breakdown_usd.fuel_cost",
    "cost_port_call_usd": "cost_breakdown_usd.port_call_fixed_cost",
    "cost_handling_usd": "cost_breakdown_usd.handling_cost",
    "cost_transshipment_usd": "cost_breakdown_usd.transshipment_cost",
    "cost_port_variable_usd": "cost_breakdown_usd.port_variable_cost",
    "contribution_margin_per_teu_usd": "contribution_margin.contribution_margin_per_teu_usd",
    "teu_utilisation_min": "vessel_utilisation_teu.min",
    "teu_utilisation_max": "vessel_utilisation_teu.max",
    "transit_days_p50": "transit_time_days.p50",
    "transit_days_p90": "transit_time_days.p90",
    "transit_days_direct": "transit_time_days.mean_direct",
    "transit_days_transshipped": "transit_time_days.mean_transshipped",
    "transship_feeder_teu": "transshipment.teu_by_type.feeder",
    "transship_hub_and_spoke_teu": "transshipment.teu_by_type.hub_and_spoke",
    "transship_multi_hop_teu": "transshipment.teu_by_type.multi_hop",
    "direct_teu": "transshipment.direct_teu",
    "t_model_and_paths_sec": "compute_time_sec.model_and_path_build",
    "t_milp_sec": "compute_time_sec.global_solver_integer_phase",
    "t_local_search_sec": "compute_time_sec.local_search",
    "t_flow_reopt_sec": "compute_time_sec.flow_reopt",
    "t_llm_latency_sec": "compute_time_sec.llm_call_latency_sum",
    "t_outside_plan_sec": "compute_time_sec.pipeline_excluding_optimiser_plan",
    "llm_attempts": "llm_runtime.provider_attempts",
    "llm_failures": "llm_runtime.provider_failures",
    "llm_fallback_uses": "llm_runtime.fallback_uses",
    "llm_http_429": "llm_runtime.http_429",
    "gap_to_bound_pct": "optimization.gap_to_bound_pct",
    "termination": "optimization.termination",
    "proven_optimal": "optimization.proven_optimal",
    "candidates_modelled": "optimization.candidates_modelled",
    "ports": "optimization.ports",
    "od_records": "optimization.od_records",
    "od_without_path": "optimization.path_model.od_without_path",
    "peak_mb_python": "peak_working_set_mb_python_sampled",
    "peak_mb_cbc": "peak_working_set_mb_cbc_sampled",
    "assertions_passed": "scorecard.assertions_passed",
    "assertions_failed": "scorecard.assertions_failed",
    "warnings": "scorecard.warnings",
}


def _seed_rows(ds_dir: Path) -> List[Dict[str, Any]]:
    regimes = _regime_by_seed(ds_dir.name)
    rows = []
    for p in sorted(ds_dir.iterdir()):
        m = _SEED_FILE.match(p.name)
        if not m:
            continue
        rec = _read_json(p) or {}
        seed = int(m.group(1))
        row = {k: rec.get(k) for k in _SEED_FIELDS}
        row.update({
            "seed": seed,
            "exit_code": rec.get("exit_code"),
            "ledger_verified": rec.get("ledger_verified"),
            "has_pipeline_output": bool(rec.get("has_pipeline_output")),
            "llm_regime": regimes.get(seed),
            "optimiser_plan_sec": _sub(rec, "compute_time_sec", "optimiser_plan_total"),
            "pipeline_sec": _sub(rec, "compute_time_sec", "pipeline_total"),
            "contribution_margin_usd": _sub(rec, "contribution_margin", "contribution_margin_usd"),
            "contribution_margin_pct": _sub(rec, "contribution_margin", "contribution_margin_pct_of_revenue"),
            "teu_utilisation_avg": _sub(rec, "vessel_utilisation_teu", "average"),
            "transit_days_mean": _sub(rec, "transit_time_days", "mean"),
            "transship_share_pct": _sub(rec, "transshipment", "share_of_served_teu_pct"),
        })
        row.update({k: _path(rec, p) for k, p in _DETAIL_FIELDS.items()})
        fleet = rec.get("fleet_by_class")
        row["fleet_by_class"] = ({c: {"owned": v.get("owned"), "assigned": v.get("assigned")}
                                  for c, v in fleet.items() if isinstance(v, dict)}
                                 if isinstance(fleet, dict) else None)
        failed = _sub(rec, "scorecard", "failed_assertions") or []
        row["failed_assertions"] = [f.get("assertion") for f in failed if isinstance(f, dict)][:5]
        rows.append(row)
    return rows


def _extra_runs() -> Dict[str, Path]:
    if not EXTRA_RUNS_ROOT.is_dir():
        return {}
    return {d.name: d for d in sorted(EXTRA_RUNS_ROOT.iterdir())
            if d.is_dir() and _RUN_ID.match(d.name) and (d / "pipeline_output.json").is_file()}


def _extra_run_dir(run_id: str) -> Path:
    runs = _extra_runs()
    if run_id not in runs:
        raise HTTPException(status_code=404, detail=f"unknown run '{run_id}'")
    return runs[run_id]


def _extra_run_entry(run_id: str, d: Path) -> Dict[str, Any]:
    meta = _read_json(d / "meta.json") or {}
    st = (d / "pipeline_output.json").stat()
    return {"id": run_id, "label": meta.get("label") or run_id, "note": meta.get("note"),
            "dataset": meta.get("dataset"), "features": meta.get("features") or [],
            "modified": formatdate(st.st_mtime, usegmt=True), "bytes": st.st_size}


@router.get("/api/runs")
async def list_runs():
    """The current run plus every frozen benchmark run that has a pipeline_output.json."""
    current = None
    if CURRENT_OUTPUT.is_file():
        st = CURRENT_OUTPUT.stat()
        current = {
            "id": "current",
            "modified": formatdate(st.st_mtime, usegmt=True),
            "bytes": st.st_size,
        }
    benchmark = []
    for key, d in _datasets().items():
        seeds = []
        for row in _seed_rows(d):
            out_file = d / "runs" / f"seed_{row['seed']:02d}" / "pipeline_output.json"
            seeds.append({
                "seed": row["seed"],
                "weekly_profit_usd": row["weekly_profit_usd"],
                "coverage_pct": row["coverage_pct"],
                "exit_code": row["exit_code"],
                "has_pipeline_output": out_file.is_file(),
            })
        label = None
        first = next((p for p in sorted(d.iterdir()) if _SEED_FILE.match(p.name)), None)
        if first is not None:
            label = (_read_json(first) or {}).get("dataset")
        benchmark.append({"key": key, "dataset": label or key, "seeds": seeds})
    extra = [_extra_run_entry(k, d) for k, d in _extra_runs().items()]
    return {"current": current, "benchmark": benchmark, "benchmark_root": BENCHMARK_ROOT.name, "extra": extra}


@router.get("/api/runs/current/pipeline_output")
async def current_output(request: Request):
    return _conditional_file(request, CURRENT_OUTPUT)


@router.get("/api/runs-extra/{run_id}/pipeline_output")
async def extra_run_output(run_id: str, request: Request):
    return _conditional_file(request, _extra_run_dir(run_id) / "pipeline_output.json")


@router.get("/api/runs/{dataset}/{seed}/pipeline_output")
async def run_output(dataset: str, seed: int, request: Request):
    if not 0 <= seed <= 999:
        raise HTTPException(status_code=404, detail="seed out of range")
    path = _dataset_dir(dataset) / "runs" / f"seed_{seed:02d}" / "pipeline_output.json"
    return _conditional_file(request, path)


@router.get("/api/runs/{dataset}/{seed}/record")
async def run_record(dataset: str, seed: int, request: Request):
    if not 0 <= seed <= 999:
        raise HTTPException(status_code=404, detail="seed out of range")
    return _conditional_file(request, _dataset_dir(dataset) / f"seed_{seed:02d}.json")


_demand_cache: Dict[str, Any] = {}


@router.get("/api/datasets/{dataset}/demand")
async def dataset_demand(dataset: str):
    """Weekly demand per lane and the port tariffs of a dataset, from the canonical problem file the engine
    loads (data/datasets/<dataset>_json.json): ``demand`` = [[origin, destination, weekly TEU], ...] for every
    lane with positive demand. Compact on purpose: the full World-1000 file is ~32 MB."""
    from src.data.dataset_registry import resolve_dataset
    try:
        path = resolve_dataset(dataset).json_path
    except Exception as exc:                       # noqa: BLE001 - unknown key -> 404, not 500
        raise HTTPException(status_code=404, detail=f"unknown dataset '{dataset}': {exc}")
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"problem file not found for '{dataset}'")
    key = f"{path}@{path.stat().st_mtime_ns}"
    if key not in _demand_cache:
        obj = _read_json(path) or {}
        _demand_cache.clear()
        _demand_cache[key] = {
            "dataset": obj.get("dataset") or dataset,
            "source": f"data/datasets/{path.name}",
            "demand": [[d["origin"], d["destination"], d["weekly_teu"]] for d in obj.get("demands") or []
                       if isinstance(d.get("weekly_teu"), (int, float)) and d["weekly_teu"] > 0],
            "ports": {p["id"]: {k: p.get(k) for k in ("name", "handling_cost", "port_call_cost",
                                                     "transshipment_cost", "draft")}
                      for p in obj.get("ports") or []},
        }
    return _demand_cache[key]


@router.get("/api/benchmark/summary")
async def benchmark_summary(request: Request):
    return _conditional_file(request, FULL_SUMMARY)


@router.get("/api/benchmark/{dataset}/seeds")
async def benchmark_seeds(dataset: str):
    """Compact per-seed rows for distribution plots."""
    return {"dataset": dataset, "seeds": _seed_rows(_dataset_dir(dataset))}
