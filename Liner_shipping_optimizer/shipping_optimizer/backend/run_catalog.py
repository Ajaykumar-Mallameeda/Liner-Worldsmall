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

_SEED_FILE = re.compile(r"^seed_(\d{2,3})\.json$")

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
        rows.append(row)
    return rows


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
    return {"current": current, "benchmark": benchmark, "benchmark_root": BENCHMARK_ROOT.name}


@router.get("/api/runs/current/pipeline_output")
async def current_output(request: Request):
    return _conditional_file(request, CURRENT_OUTPUT)


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


@router.get("/api/benchmark/summary")
async def benchmark_summary(request: Request):
    return _conditional_file(request, FULL_SUMMARY)


@router.get("/api/benchmark/{dataset}/seeds")
async def benchmark_seeds(dataset: str):
    """Compact per-seed rows for distribution plots."""
    return {"dataset": dataset, "seeds": _seed_rows(_dataset_dir(dataset))}
