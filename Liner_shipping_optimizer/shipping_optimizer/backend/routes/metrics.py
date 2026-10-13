"""
API routes for metrics and KPI data
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from datetime import datetime
import json
from pathlib import Path

router = APIRouter(prefix="/metrics", tags=["metrics"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PIPELINE_OUTPUT = PROJECT_ROOT / "pipeline_output.json"


def _load_real_metrics() -> Dict[str, Any]:
    """Read the canonical pipeline_output.json. Returns an empty dict on
    failure so callers can detect absence vs presence of real data."""
    if not PIPELINE_OUTPUT.exists():
        return {}
    try:
        with open(PIPELINE_OUTPUT, "r") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def _derive_metrics_from_pipeline() -> Dict[str, Any]:
    """PROJECT X: derive canonical summary metrics from pipeline_output.json
    so this endpoint never diverges from the single runtime truth.

    Canonical global coverage is summary_metrics.coverage
      (= global_demand_weighted_coverage, computed from
       total_satisfied_demand / true_global_demand × 100).
    Regional average coverage is reported separately and explicitly labeled.
    """
    payload = _load_real_metrics()
    summary = payload.get("summary_metrics", {}) or {}
    weekly_profit = float(summary.get("weekly_profit", 0) or 0)
    total_cost    = float(summary.get("total_cost", 0) or 0)
    total_services = int(summary.get("total_services", 0) or 0)
    unserved      = float(summary.get("unserved_demand", 0) or 0)
    # Canonical global coverage = total_satisfied / true_global_demand × 100
    coverage = float(summary.get("coverage", 0) or 0)
    margin = (
        weekly_profit / (weekly_profit + total_cost) * 100
        if (weekly_profit + total_cost) > 0 else 0
    )
    # Regional average coverage of the SELECTED iteration (distinct metric,
    # explicitly labeled — never substituted for global coverage).
    sel_iteration = payload.get("final_selected_iteration") or payload.get(
        "best_iteration"
    )
    selected_regional_avg = 0.0
    for card in (payload.get("iteration_selection", {}) or {}).get(
        "scorecards", []
    ) or []:
        if card.get("iteration") == sel_iteration:
            selected_regional_avg = float(
                card.get("average_regional_coverage", 0) or 0
            )
            break
    return {
        "weekly_profit":    weekly_profit,
        "annual_profit":    weekly_profit * 52,
        "total_cost":       total_cost,
        "total_services":   total_services,
        "coverage":         coverage,
        "average_regional_coverage": selected_regional_avg,
        "coverage_percentage": coverage,
        "profit_margin":    margin,
        "vessels_utilized": None,
        "total_teu_moved":  None,
        "unserved_demand":  unserved,
    }


@router.get("/summary")
async def get_summary_metrics():
    """Get summary KPI metrics. Always derived from pipeline_output.json."""
    return {
        "metrics": _derive_metrics_from_pipeline(),
        "last_updated": datetime.utcnow().isoformat(),
        "status": "success",
    }

@router.get("/profit-trends")
async def get_profit_trends():
    """Get historical profit trends"""
    # Mock data - in production, fetch from database
    return {
        "data": _derive_profit_trend(),
        "trend": "increasing"
    }


def _derive_profit_trend() -> List[Dict[str, Any]]:
    payload = _load_real_metrics()
    audit = payload.get("iteration_audit", []) or []
    series = []
    for i, entry in enumerate(audit):
        series.append({
            "week": f"iter-{entry.get('iteration', i)}",
            "profit": float(entry.get("profit", 0) or 0),
            "cost":   float((payload.get("summary_metrics", {}) or {}).get("total_cost", 0) or 0),
        })
    return series


def _derive_coverage_metrics() -> Dict[str, Any]:
    payload = _load_real_metrics()
    regional = payload.get("regional_results", []) or []
    regions_out = []
    for r in regional:
        regions_out.append({
            "region":        r.get("region", ""),
            "coverage":      float(r.get("coverage_percent", 0) or 0),
            "uncovered_teu": float(r.get("uncovered_teu",
                                          r.get("unserved_demand", 0)) or 0),
        })
    summary = payload.get("summary_metrics", {}) or {}
    return {
        "regions":        regions_out,
        "global_coverage": float(summary.get("coverage", 0) or 0),
    }


def _derive_service_stats() -> Dict[str, Any]:
    payload = _load_real_metrics()
    regional = payload.get("regional_results", []) or []
    services_by_region: Dict[str, int] = {}
    for r in regional:
        services_by_region[r.get("region", "?")] = int(
            r.get("services_selected", 0) or 0
        )
    total_services = int(
        (payload.get("summary_metrics", {}) or {}).get("total_services", 0) or 0
    )
    return {
        "total_services":   total_services,
        "active_services":  total_services,
        "services_by_region": services_by_region,
        "services_by_type":  {},
        "vessel_utilization": {"utilized": None, "available": None,
                                "utilization_rate": None},
    }


@router.get("/coverage-metrics")
async def get_coverage_metrics():
    """Get detailed coverage metrics by region. Always derived from
    pipeline_output.json. The two coverage metrics are explicit and labeled."""
    return _derive_coverage_metrics()


@router.get("/service-stats")
async def get_service_statistics():
    """Get service deployment statistics. Always derived from
    pipeline_output.json."""
    return _derive_service_stats()


@router.put("/update")
async def update_metrics(metrics: Dict[str, Any]):
    """Update metrics (internal use). No-op when only the canonical JSON
    exists; the runtime truth is pipeline_output.json."""
    return {
        "status": "ignored",
        "reason": "pipeline_output.json is the sole runtime truth; this endpoint is a no-op",
        "timestamp": datetime.utcnow().isoformat(),
    }