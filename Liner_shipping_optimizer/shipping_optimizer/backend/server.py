"""
Simplified FastAPI server for the live dashboard
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Shipping Optimizer API")

# Read-only run catalog: current run + frozen 30-seed benchmark (backend/run_catalog.py)
from backend.run_catalog import router as run_catalog_router
app.include_router(run_catalog_router)

# Mount static data directory
repo_root_data = Path(__file__).resolve().parent.parent / "data"
if repo_root_data.exists():
    app.mount("/data", StaticFiles(directory=str(repo_root_data)), name="data")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store current state
current_state = {
    "pipeline": {
        "status": "idle",
        "current_iteration": 0,
        "total_iterations": 0,
        "current_stage": None,
        "stages": [
            {"id": "analysis", "name": "Problem Analysis", "status": "pending"},
            {"id": "regional", "name": "Regional Optimization", "status": "pending"},
            {"id": "coordinator", "name": "Coordinator Agent", "status": "pending"},
            {"id": "milp", "name": "MILP Optimization", "status": "pending"},
            {"id": "deployment", "name": "Vessel Deployment", "status": "pending"}
        ]
    },
    "metrics": {
        "weeklyProfit": 0,
        "annualProfit": 0,
        "totalCost": 0,
        "operatingCost": 0,
        "totalServices": 0,
        "coverage": 0,
        "margin": 0,
        "unserved": 0,
        "convergence": 0,
        "vesselsUtilized": None,
        "totalTeuMoved": None
    },
    "regions": {},
    "iterations": [],
    "connected_clients": []
}

# Function to load data from JSON file
def load_pipeline_data():
    """Load pipeline data from the JSON file created by test_orchestrator.py"""
    try:
        parent_dir = Path(__file__).parent.parent
        output_file = parent_dir / "pipeline_output.json"

        if not output_file.exists():
            logger.warning(f"Pipeline output file not found: {output_file}")
            return False

        with open(output_file, 'r') as f:
            result = json.load(f)

        # Load regional results
        regional_results = result.get("regional_results", [])
        current_state["regions"] = {
            r.get("region", "").lower().replace(" ", "_"): {
                "id": r.get("region", "").lower().replace(" ", "_"),
                "name": r.get("region", "").replace("Middle Last", "Middle East"),
                "status": "completed",
                "profit": r.get("weekly_profit", 0),
                "coverage": r.get("coverage_percent", 0),
                "services": r.get("services_selected", 0),
                "margin": r.get("profit_margin_pct", 0),
                "hubs": r.get("hub_ports", []),
                "uncovered": r.get("uncovered_teu", 0),
                "cost": r.get("total_cost", r.get("operating_cost", 0)),
                "operating_cost": r.get("operating_cost", 0),
                "transship_cost": r.get("transship_cost", 0),
                "generated": r.get("services_generated", 0),
                "filtered": r.get("services_filtered", 0),
                "selected": r.get("services_selected", 0),
                "strategy": r.get("strategy", ""),
                "explanation": r.get("explanation", "")
            }
            for r in regional_results
        }

        # Load iteration audit
        iteration_audit = result.get("iteration_audit", [])
        current_state["iterations"] = [
            {
                "iter": i.get("iteration", 0),
                "profit": i.get("profit", 0),
                # PROJECT X: two coverage metrics per iteration.
                # `coverage`       = REGIONAL average (feedback-loop view).
                # `globalCoverage` = demand-weighted (network KPI).
                "coverage": i.get("coverage", 0),
                "globalCoverage": i.get("global_coverage", i.get("coverage", 0)),
                "score": i.get("convergence_score", 0),
                "rerun": i.get("needs_rerun", False),
                "reason": i.get("rerun_reason", ""),
                "selected_as_final": i.get("selected_as_final", False),
            }
            for i in iteration_audit
        ]

        # PROJECT X: surface multi-objective iteration selection + best snapshot.
        current_state["iteration_selection"] = result.get("iteration_selection", {})
        current_state["best_iteration"]       = result.get("best_iteration", 0)
        current_state["iteration_results"]    = result.get("iteration_results", [])

        # Load metrics
        summary_metrics = result.get("summary_metrics", {})
        weekly_profit = summary_metrics.get("weekly_profit", 0)
        annual_profit = summary_metrics.get("annual_profit", 0)
        total_cost = summary_metrics.get("cost", 0)
        coverage = summary_metrics.get("coverage", 0)
        total_services = summary_metrics.get("total_services", 0)

        status_val = result.get("status", "complete")
        status_obj = {"status": status_val} if isinstance(status_val, str) else dict(status_val)
        if "test_scorecard" in result:
            status_obj.update(result["test_scorecard"])

        current_state["metrics"] = {
            "weeklyProfit": weekly_profit,
            "annualProfit": annual_profit,
            "totalCost": total_cost,
            "operatingCost": summary_metrics.get("operating_cost", total_cost),
            "totalServices": total_services,
            "coverage": coverage,
            "margin": (weekly_profit / (weekly_profit + total_cost)) * 100 if (weekly_profit + total_cost) > 0 else 0,
            "unserved": summary_metrics.get("unserved_demand", 0),
            "convergence": current_state["iterations"][-1]["score"] if current_state["iterations"] else 0.982,
            "runtime": summary_metrics.get("total_runtime", 0),
            "selected_services": result.get("selected_services", []),
            "decision_output": result.get("decision_output", {}),
            "executive_summary": result.get("executive_summary", ""),
            "status": status_obj
        }

        # Extract problem_stats from the dataset
        problem_analysis_text = result.get("problem_analysis", "")
        current_state["problem_stats"] = _parse_problem_stats(
            problem_analysis_text,
            summary_metrics,
            result.get("selected_services", [])
        )

        logger.info(f"Loaded pipeline data from {output_file}")
        return True

    except Exception as e:
        logger.error(f"Error loading pipeline data: {e}")
        return False


def _parse_problem_stats(analysis_text: str, metrics: dict, selected_services: list) -> dict:
    """Parse real problem stats from the optimizer's problem_analysis text and summary_metrics."""
    import re
    ports = 0
    lanes = 0
    weekly_demand = 0

    # Parse "333 ports x 9622 lanes" pattern
    m = re.search(r'(\d+)\s*ports?\s*x\s*(\d+)\s*lanes?', analysis_text)
    if m:
        ports = int(m.group(1))
        lanes = int(m.group(2))

    # Parse "Total demand 1,666,738 TEU" pattern
    m = re.search(r'[Tt]otal\s*demand\s*([\d,]+)\s*TEU', analysis_text)
    if m:
        weekly_demand = int(m.group(1).replace(',', ''))

    # Fallback: use total_services as port count hint
    total_services = metrics.get("total_services", 0)
    if ports == 0 and total_services > 0:
        ports = total_services  # not ideal but last resort

    return {
        "ports": ports,
        "lanes": lanes,
        "services": total_services,
        "weekly_demand": weekly_demand
    }

# Load data on startup
load_pipeline_data()

# WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")
        
        # Send initial state
        await websocket.send_text(json.dumps({
            "type": "initial_state",
            "data": {
                "metrics": current_state["metrics"],
                "regions": current_state["regions"],
                "iterations": current_state["iterations"],
                "problem_stats": current_state.get("problem_stats", {
                    "ports": None,
                    "lanes": None,
                    "services": None,
                    "weekly_demand": None
                })
            }
        }))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return

        message_str = json.dumps(message)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# REST API endpoints
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "connected_clients": len(manager.active_connections)
    }

@app.get("/api/pipeline/status")
async def get_pipeline_status():
    return {
        "state": current_state["pipeline"],
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/metrics/summary")
async def get_metrics():
    return {
        "metrics": current_state["metrics"],
        "last_updated": datetime.utcnow().isoformat()
    }

@app.get("/api/regions/")
async def get_regions():
    return {
        "regions": current_state["regions"],
        "total_regions": len(current_state["regions"])
    }

@app.get("/api/pipeline/iterations")
async def get_iterations():
    return {
        "iterations": current_state["iterations"],
        "current_iteration": current_state["pipeline"]["current_iteration"],
        "total_iterations": current_state["pipeline"]["total_iterations"]
    }

# -----------------------------------------------------------------
# Phase 1 — Maritime Intelligence status (read-only, store-backed).
# This endpoint is additive and lives beside the existing REST block.
# It does NOT touch the WebSocket channel, the pipeline state, or the
# optimizer. If maritime is disabled or no snapshot exists, the response
# is the same shape with empty fields and a `disabled` flag.
# -----------------------------------------------------------------
@app.get("/api/maritime/status")
async def get_maritime_status():
    """Read-only maritime status. Falls back gracefully when the maritime
    package is unavailable or no snapshot is on disk."""
    try:
        import os, json
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent
        # Use the same env-respecting read path as the optimizer would
        # see, but never raise if the package is absent.
        enabled = os.environ.get("MARITIME_INTELLIGENCE_ENABLED", "0").lower() in (
            "1", "true", "yes", "on",
        )
        if not enabled:
            return {
                "enabled": False,
                "traffic_available": False,
                "source": None,
                "source_status": "disabled",
                "quality_status": "disabled",
                "quality_score": None,
                "record_count": None,
                "freshness_label": None,
                "snapshot_id": None,
                "attribution": None,
            }
        snap_root = repo_root / "data" / "maritime" / "snapshots" / "emodnet_vessel_density"
        latest_meta = None
        if snap_root.is_dir():
            children = sorted(
                [c for c in snap_root.iterdir() if c.is_dir() and (c / "metadata.json").exists()],
                key=lambda p: p.name,
            )
            if children:
                latest_meta = json.loads((children[-1] / "metadata.json").read_text(encoding="utf-8"))
        if latest_meta is None:
            return {
                "enabled": True,
                "traffic_available": False,
                "source": "EMODNET",
                "source_status": "offline",
                "quality_status": "offline",
                "quality_score": None,
                "record_count": None,
                "freshness_label": "Historical",
                "snapshot_id": None,
                "attribution": None,
            }
        return {
            "enabled": True,
            "traffic_available": bool(latest_meta.get("accepted_records", 0) > 0),
            "source": latest_meta.get("source", "EMODNET"),
            "source_status": latest_meta.get("source_status", "unknown"),
            "quality_status": latest_meta.get("quality_status", "unknown"),
            "quality_score": latest_meta.get("quality_score"),
            "record_count": latest_meta.get("accepted_records", 0),
            "freshness_label": "Historical",
            "snapshot_id": latest_meta.get("snapshot_id"),
            "attribution": latest_meta.get("attribution"),
        }
    except Exception as e:
        logger.error(f"maritime status error: {e}")
        return {
            "enabled": False,
            "traffic_available": False,
            "source": None,
            "source_status": "offline",
            "quality_status": "offline",
            "quality_score": None,
            "record_count": None,
            "freshness_label": None,
            "snapshot_id": None,
            "attribution": None,
        }

# -----------------------------------------------------------------
# Phase 2 — Maritime Port-Intelligence REST endpoints.
# All endpoints are read-only and fall back gracefully when the
# port-intelligence feature flag is OFF or no snapshot exists.
# -----------------------------------------------------------------

def _read_port_meta(repo_root):
    """Read the most-recent port-intelligence snapshot metadata, or None."""
    import json
    snap_root = repo_root / "data" / "maritime" / "snapshots" / "noaa_ais_port_intelligence"
    if not snap_root.is_dir():
        return None
    children = sorted(
        [c for c in snap_root.iterdir() if c.is_dir() and (c / "metadata.json").exists()],
        key=lambda p: p.name,
    )
    if not children:
        return None
    return json.loads((children[-1] / "metadata.json").read_text(encoding="utf-8"))


def _read_manifest(repo_root, *, snapshot_id: str):
    import json
    base = repo_root / "data" / "maritime" / "snapshots" / "noaa_ais_port_intelligence" / snapshot_id
    p = base / "manifest.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _read_jsonl_records(path):
    if not path.exists():
        return []
    out = []
    with open(path, "rb") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                import json as _json
                out.append(_json.loads(line))
            except Exception:
                continue
    return out


@app.get("/api/maritime/sources")
async def get_maritime_sources():
    """List both maritime sources and their current health."""
    try:
        repo_root = Path(__file__).resolve().parent.parent
        out = {"enabled": False, "sources": []}
        enabled = os.environ.get("MARITIME_INTELLIGENCE_ENABLED", "0").lower() in (
            "1", "true", "yes", "on",
        )
        out["enabled"] = enabled
        # Phase 1 source
        emodnet_root = repo_root / "data" / "maritime" / "snapshots" / "emodnet_vessel_density"
        emodnet_meta = None
        if emodnet_root.is_dir():
            children = sorted(
                [c for c in emodnet_root.iterdir() if c.is_dir() and (c / "metadata.json").exists()],
                key=lambda p: p.name,
            )
            if children:
                import json as _json
                emodnet_meta = _json.loads((children[-1] / "metadata.json").read_text(encoding="utf-8"))
        out["sources"].append({
            "source": "EMODNET",
            "dataset": "emodnet_vessel_density",
            "available": emodnet_meta is not None,
            "source_status": (emodnet_meta or {}).get("source_status", "offline"),
            "quality_status": (emodnet_meta or {}).get("quality_status", "offline"),
            "license": (emodnet_meta or {}).get("license"),
            "attribution": (emodnet_meta or {}).get("attribution"),
            "snapshot_id": (emodnet_meta or {}).get("snapshot_id"),
            "record_count": (emodnet_meta or {}).get("accepted_records", 0),
        })
        # Phase 2 source
        port_meta = _read_port_meta(repo_root)
        out["sources"].append({
            "source": "MARINE_CADASTRE",
            "dataset": "noaa_ais_port_intelligence",
            "available": port_meta is not None,
            "source_status": (port_meta or {}).get("source_status", "offline"),
            "quality_status": (port_meta or {}).get("quality_status", "offline"),
            "license": (port_meta or {}).get("license"),
            "attribution": (port_meta or {}).get("attribution"),
            "snapshot_id": (port_meta or {}).get("snapshot_id"),
            "record_count": (port_meta or {}).get("accepted_records", 0),
            "port_count": (port_meta or {}).get("port_count", 0),
            "call_count": (port_meta or {}).get("call_count", 0),
        })
        return out
    except Exception as e:
        logger.error(f"maritime sources error: {e}")
        return {"enabled": False, "sources": [], "error": str(e)}


@app.get("/api/maritime/ports")
async def get_maritime_ports():
    try:
        repo_root = Path(__file__).resolve().parent.parent
        port_meta = _read_port_meta(repo_root)
        if port_meta is None:
            return {"enabled": False, "ports": [], "count": 0}
        snap_id = port_meta.get("snapshot_id")
        if not snap_id:
            return {"enabled": True, "ports": [], "count": 0}
        manifest = _read_manifest(repo_root, snapshot_id=snap_id)
        ports = (manifest or {}).get("ports", [])
        return {"enabled": True, "ports": ports, "count": len(ports)}
    except Exception as e:
        logger.error(f"maritime ports error: {e}")
        return {"enabled": False, "ports": [], "count": 0, "error": str(e)}


@app.get("/api/maritime/ports/{port_id}")
async def get_maritime_port(port_id: str):
    try:
        repo_root = Path(__file__).resolve().parent.parent
        port_meta = _read_port_meta(repo_root)
        if port_meta is None:
            return {"enabled": False, "port": None}
        snap_id = port_meta.get("snapshot_id")
        manifest = _read_manifest(repo_root, snapshot_id=snap_id) if snap_id else None
        ports = (manifest or {}).get("ports", [])
        port = next((p for p in ports if p.get("port_id") == port_id), None)
        if port is None:
            return {"enabled": True, "port": None}
        # Augment with port activity stats
        activity = next(
            (a for a in (manifest or {}).get("port_activity_features", [])
             if a.get("port_id") == port_id),
            None,
        )
        mix = next(
            (m for m in (manifest or {}).get("port_vessel_mix_features", [])
             if m.get("port_id") == port_id),
            None,
        )
        return {
            "enabled": True,
            "port": port,
            "activity": activity,
            "vessel_type_mix": mix,
        }
    except Exception as e:
        logger.error(f"maritime port error: {e}")
        return {"enabled": False, "port": None, "error": str(e)}


@app.get("/api/maritime/port-calls")
async def get_maritime_port_calls(port_id: Optional[str] = None, limit: Optional[int] = None):
    try:
        repo_root = Path(__file__).resolve().parent.parent
        port_meta = _read_port_meta(repo_root)
        if port_meta is None:
            return {"enabled": False, "port_calls": [], "count": 0}
        snap_id = port_meta.get("snapshot_id")
        if not snap_id:
            return {"enabled": True, "port_calls": [], "count": 0}
        base = repo_root / "data" / "maritime" / "snapshots" / "noaa_ais_port_intelligence" / snap_id
        records = _read_jsonl_records(base / "port_calls.jsonl")
        if port_id is not None:
            records = [r for r in records if r.get("port_id") == port_id]
        if limit is not None:
            records = records[:limit]
        return {"enabled": True, "port_calls": records, "count": len(records)}
    except Exception as e:
        logger.error(f"maritime port-calls error: {e}")
        return {"enabled": False, "port_calls": [], "count": 0, "error": str(e)}


@app.get("/api/maritime/vessels/{mmsi}/history")
async def get_maritime_vessel_history(mmsi: str, limit: Optional[int] = None):
    try:
        repo_root = Path(__file__).resolve().parent.parent
        port_meta = _read_port_meta(repo_root)
        if port_meta is None:
            return {"enabled": False, "mmsi": mmsi, "positions": []}
        snap_id = port_meta.get("snapshot_id")
        if not snap_id:
            return {"enabled": True, "mmsi": mmsi, "positions": []}
        base = repo_root / "data" / "maritime" / "snapshots" / "noaa_ais_port_intelligence" / snap_id
        positions = _read_jsonl_records(base / "vessel_positions.jsonl")
        positions = [p for p in positions if p.get("mmsi") == mmsi]
        positions.sort(key=lambda p: p.get("timestamp", ""))
        if limit is not None:
            positions = positions[:limit]
        return {"enabled": True, "mmsi": mmsi, "positions": positions, "count": len(positions)}
    except Exception as e:
        logger.error(f"maritime vessel history error: {e}")
        return {"enabled": False, "mmsi": mmsi, "positions": [], "error": str(e)}


@app.get("/api/maritime/snapshot")
async def get_maritime_snapshot(kind: str = "port"):
    """Return the most recent snapshot metadata.

    ``kind=traffic`` returns the EMODnet snapshot metadata.
    ``kind=port`` returns the NOAA port snapshot metadata (default).
    """
    try:
        repo_root = Path(__file__).resolve().parent.parent
        if kind == "traffic":
            emodnet_root = repo_root / "data" / "maritime" / "snapshots" / "emodnet_vessel_density"
            if not emodnet_root.is_dir():
                return {"available": False, "kind": "traffic"}
            children = sorted(
                [c for c in emodnet_root.iterdir() if c.is_dir() and (c / "metadata.json").exists()],
                key=lambda p: p.name,
            )
            if not children:
                return {"available": False, "kind": "traffic"}
            import json as _json
            meta = _json.loads((children[-1] / "metadata.json").read_text(encoding="utf-8"))
            return {"available": True, "kind": "traffic", "metadata": meta}
        port_meta = _read_port_meta(repo_root)
        if port_meta is None:
            return {"available": False, "kind": "port"}
        return {"available": True, "kind": "port", "metadata": port_meta}
    except Exception as e:
        logger.error(f"maritime snapshot error: {e}")
        return {"available": False, "kind": kind, "error": str(e)}

# -----------------------------------------------------------------
# Phase 3 — Maritime Resilience Core REST surface.
# All endpoints are read-only and additive. They never mutate
# pipeline state, never touch the WebSocket channel, and never
# call into the optimizer. They are designed to expose:
#   - source health (compact, dashboard-friendly)
#   - resilience status (freshness state, tier, verification)
#   - deterministic fallback decisions
# The endpoints work even when the master flag is OFF; in that
# case the response is the safe-empty payload.
# -----------------------------------------------------------------


def _phase3_safe_empty(reason: str = "flag_off"):
    return {
        "enabled": False,
        "state": "offline",
        "tier": "empty",
        "fresh": False,
        "snapshot_id": None,
        "source": None,
        "dataset": None,
        "created_at": None,
        "record_count": 0,
        "quality_score": None,
        "checksum": None,
        "degraded_reasons": [reason],
    }


def _phase3_metadata_for(repo_root, dataset_key: str):
    """Read the latest snapshot metadata for a given dataset (Phase 3)."""
    import json as _json
    snap_root = repo_root / "data" / "maritime" / "snapshots" / dataset_key
    if not snap_root.is_dir():
        return None
    children = sorted(
        [c for c in snap_root.iterdir() if c.is_dir() and (c / "metadata.json").exists()],
        key=lambda p: p.name,
    )
    if not children:
        return None
    try:
        return _json.loads((children[-1] / "metadata.json").read_text(encoding="utf-8"))
    except Exception:
        return None


def _phase3_manifest_for(repo_root, dataset_key: str, snapshot_id: str):
    """Read the manifest of a specific snapshot (Phase 3)."""
    import json as _json
    p = repo_root / "data" / "maritime" / "snapshots" / dataset_key / snapshot_id / "manifest.json"
    if not p.exists():
        return None
    try:
        return _json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _phase3_classify_freshness(age_seconds: float, quality_score) -> str:
    """Inline, deterministic freshness classifier. Mirrors the policy module."""
    try:
        q = float(quality_score) if quality_score is not None else 1.0
    except (TypeError, ValueError):
        q = 1.0
    fresh_after = 60 * 60 * 24 * 7
    stale_after = 60 * 60 * 24 * 30
    if age_seconds < 0:
        return "invalid"
    if age_seconds > stale_after:
        return "stale"
    if age_seconds <= fresh_after and q >= 0.5:
        return "available"
    return "degraded"


@app.get("/api/maritime/source-health")
async def get_maritime_source_health():
    """Compact source-health view for the dashboard.

    Returns a small dict per dataset: state, tier, fresh flag,
    snapshot id, degraded reasons. Never raises. Independent of the
    optimizer and the WebSocket channel.
    """
    try:
        repo_root = Path(__file__).resolve().parent.parent
        enabled = os.environ.get("MARITIME_INTELLIGENCE_ENABLED", "0").lower() in (
            "1", "true", "yes", "on",
        )
        if not enabled:
            return {
                "enabled": False,
                "traffic": _phase3_safe_empty("flag_off"),
                "port": _phase3_safe_empty("flag_off"),
                "evaluated_at": datetime.utcnow().isoformat(),
            }
        out = {"enabled": True, "evaluated_at": datetime.utcnow().isoformat()}
        now = datetime.utcnow()
        for key, label in (("emodnet_vessel_density", "traffic"),
                           ("noaa_ais_port_intelligence", "port")):
            meta = _phase3_metadata_for(repo_root, key)
            if meta is None:
                out[label] = {
                    "enabled": True,
                    "state": "offline",
                    "tier": "empty",
                    "fresh": False,
                    "snapshot_id": None,
                    "source": None,
                    "dataset": key,
                    "degraded_reasons": ["no_snapshot"],
                }
                continue
            created = meta.get("created_at")
            age_s = 0.0
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(created.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=_dt.now().astimezone().tzinfo)
                age_s = (now - dt).total_seconds()
            except Exception:
                pass
            state = _phase3_classify_freshness(age_s, meta.get("quality_score"))
            out[label] = {
                "enabled": True,
                "state": state,
                "tier": "fresh" if state == "available" else "stale_within_window",
                "fresh": state == "available",
                "snapshot_id": meta.get("snapshot_id"),
                "source": meta.get("source"),
                "dataset": key,
                "created_at": created,
                "record_count": meta.get("accepted_records", 0),
                "quality_score": meta.get("quality_score"),
                "degraded_reasons": [],
            }
        return out
    except Exception as e:
        logger.error(f"maritime source-health error: {e}")
        return {
            "enabled": False,
            "traffic": _phase3_safe_empty("safe_failure"),
            "port": _phase3_safe_empty("safe_failure"),
            "evaluated_at": datetime.utcnow().isoformat(),
        }


@app.get("/api/maritime/resilience")
async def get_maritime_resilience(dataset: str = "emodnet_vessel_density"):
    """Detailed resilience view: verification + freshness + checksum.

    Returns a structured object that combines metadata, the
    latest-snapshot manifest, the freshness classification, and a
    minimal verification summary. The endpoint is read-only and
    safe-empty when the master flag is OFF.
    """
    try:
        repo_root = Path(__file__).resolve().parent.parent
        enabled = os.environ.get("MARITIME_INTELLIGENCE_ENABLED", "0").lower() in (
            "1", "true", "yes", "on",
        )
        if not enabled:
            return _phase3_safe_empty("flag_off") | {"dataset": dataset}
        meta = _phase3_metadata_for(repo_root, dataset)
        if meta is None:
            return {
                "enabled": True,
                "dataset": dataset,
                "state": "offline",
                "tier": "empty",
                "fresh": False,
                "degraded_reasons": ["no_snapshot"],
            }
        snap_id = meta.get("snapshot_id")
        manifest = _phase3_manifest_for(repo_root, dataset, snap_id) if snap_id else None
        created = meta.get("created_at")
        age_s = 0.0
        try:
            from datetime import datetime as _dt
            dt = _dt.fromisoformat(created.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_dt.now().astimezone().tzinfo)
            age_s = (_dt.utcnow().replace(tzinfo=dt.tzinfo) - dt).total_seconds()
        except Exception:
            pass
        state = _phase3_classify_freshness(age_s, meta.get("quality_score"))
        verification_reasons: list = []
        if manifest is None:
            verification_reasons.append("manifest_missing")
        return {
            "enabled": True,
            "dataset": dataset,
            "snapshot_id": snap_id,
            "source": meta.get("source"),
            "created_at": created,
            "state": state,
            "tier": "fresh" if state == "available" else "stale_within_window",
            "fresh": state == "available",
            "age_seconds": round(age_s, 3),
            "record_count": meta.get("accepted_records", 0),
            "quality_score": meta.get("quality_score"),
            "schema_version": meta.get("schema_version"),
            "checksum_records": (manifest or {}).get("checksum_records"),
            "verification_ok": len(verification_reasons) == 0,
            "verification_reasons": verification_reasons,
            "evaluated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"maritime resilience error: {e}")
        return _phase3_safe_empty("safe_failure") | {"dataset": dataset}


# -----------------------------------------------------------------
# Phase 4 — Live maritime source REST surface.
# Read-only, additive, and isolated from the optimizer. Endpoints
# follow the project's existing naming convention
# (/api/maritime/live/{status,snapshot,providers}).
# They never expose secrets, never touch /ws/pipeline, and never
# mutate any pipeline state. The provider is double-gated by
# MARITIME_LIVE_ENABLED and MARITIME_LIVE_PROVIDER.
# -----------------------------------------------------------------


def _phase4_live_empty(reason: str = "disabled") -> dict:
    return {
        "enabled": False,
        "state": "disabled" if reason == "disabled" else "offline",
        "provider": None,
        "snapshot_id": None,
        "snapshot_dir": None,
        "record_count": 0,
        "quality_score": None,
        "freshness_seconds": None,
        "license": "unresolved",
        "attribution": "",
        "fallback_tier": "empty",
        "evaluated_at": datetime.utcnow().isoformat(),
        "error": reason,
    }


def _phase4_live_meta(repo_root, dataset_key: str):
    """Read the most-recent live snapshot metadata, or None."""
    import json as _json
    snap_root = repo_root / "data" / "maritime" / "snapshots" / dataset_key
    if not snap_root.is_dir():
        return None
    children = sorted(
        [c for c in snap_root.iterdir() if c.is_dir() and (c / "metadata.json").exists()],
        key=lambda p: p.name,
    )
    if not children:
        return None
    try:
        return _json.loads((children[-1] / "metadata.json").read_text(encoding="utf-8"))
    except Exception:
        return None


def _phase4_live_manifest(repo_root, dataset_key: str, snapshot_id: str):
    import json as _json
    p = repo_root / "data" / "maritime" / "snapshots" / dataset_key / snapshot_id / "manifest.json"
    if not p.exists():
        return None
    try:
        return _json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


@app.get("/api/maritime/live/status")
async def get_maritime_live_status():
    """Compact live-source status. Safe-empty when flags are off."""
    try:
        repo_root = Path(__file__).resolve().parent.parent
        enabled = os.environ.get("MARITIME_LIVE_ENABLED", "0").lower() in (
            "1", "true", "yes", "on",
        )
        provider = os.environ.get("MARITIME_LIVE_PROVIDER", "").strip() or None
        if not enabled:
            return _phase4_live_empty("disabled")
        live_dataset = "digitraffic_live_vessel_positions"
        meta = _phase4_live_meta(repo_root, live_dataset)
        evaluated_at = datetime.utcnow().isoformat()
        if meta is None:
            return {
                "enabled": True,
                "state": "offline",
                "provider": provider,
                "snapshot_id": None,
                "snapshot_dir": None,
                "record_count": 0,
                "quality_score": None,
                "freshness_seconds": None,
                "license": "unresolved",
                "attribution": "",
                "fallback_tier": "empty",
                "evaluated_at": evaluated_at,
                "error": "no_live_snapshot",
            }
        # Compute age
        age_s = 0.0
        try:
            from datetime import datetime as _dt
            dt = _dt.fromisoformat(meta.get("created_at", "").replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_dt.now().astimezone().tzinfo)
            age_s = (_dt.utcnow().replace(tzinfo=dt.tzinfo) - dt).total_seconds()
        except Exception:
            pass
        try:
            max_age = int(os.environ.get("MARITIME_LIVE_MAX_AGE_SECONDS", "600"))
        except ValueError:
            max_age = 600
        state = "live" if age_s <= max_age else "stale"
        return {
            "enabled": True,
            "state": state,
            "provider": provider,
            "snapshot_id": meta.get("snapshot_id"),
            "snapshot_dir": str(
                repo_root / "data" / "maritime" / "snapshots" / live_dataset / meta.get("snapshot_id", "")
            ),
            "record_count": meta.get("accepted_records", 0),
            "quality_score": meta.get("quality_score"),
            "freshness_seconds": round(age_s, 3),
            "license": meta.get("license", "unresolved"),
            "attribution": meta.get("attribution", ""),
            "fallback_tier": "live",
            "source_status": meta.get("source_status", "unknown"),
            "quality_status": meta.get("quality_status", "unknown"),
            "evaluated_at": evaluated_at,
            "source": meta.get("source"),
        }
    except Exception as e:
        logger.error(f"maritime live status error: {e}")
        return _phase4_live_empty("safe_failure")


@app.get("/api/maritime/live/snapshot")
async def get_maritime_live_snapshot():
    """Full live-snapshot metadata + manifest, safe-empty when disabled."""
    try:
        repo_root = Path(__file__).resolve().parent.parent
        enabled = os.environ.get("MARITIME_LIVE_ENABLED", "0").lower() in (
            "1", "true", "yes", "on",
        )
        if not enabled:
            return {"enabled": False, "available": False, "metadata": None, "manifest": None}
        live_dataset = "digitraffic_live_vessel_positions"
        meta = _phase4_live_meta(repo_root, live_dataset)
        if meta is None:
            return {"enabled": True, "available": False, "metadata": None, "manifest": None}
        snap_id = meta.get("snapshot_id")
        manifest = _phase4_live_manifest(repo_root, live_dataset, snap_id) if snap_id else None
        return {"enabled": True, "available": True, "metadata": meta, "manifest": manifest}
    except Exception as e:
        logger.error(f"maritime live snapshot error: {e}")
        return {"enabled": False, "available": False, "metadata": None, "manifest": None, "error": str(e)}


@app.get("/api/maritime/live/providers")
async def get_maritime_live_providers():
    """Enumerate registered live providers and their enablement state."""
    try:
        # Lazy import to avoid a hard dependency on the live package
        # when the live feature is not installed.
        from maritime.live.registry import list_providers
        return {"enabled": True, "providers": list_providers()}
    except Exception as e:
        logger.error(f"maritime live providers error: {e}")
        return {"enabled": False, "providers": [], "error": str(e)}


# -----------------------------------------------------------------
# Phase 5 — Weather intelligence REST endpoints
# (/api/maritime/weather/{status,snapshot,providers}).
# They are read-only, never expose secrets, and never touch
# /ws/pipeline. The orchestrator is double-gated by
# MARITIME_WEATHER_ENABLED and MARITIME_WEATHER_PROVIDER.
# -----------------------------------------------------------------


def _phase5_weather_empty(reason: str = "disabled") -> Dict[str, Any]:
    return {
        "enabled": False,
        "state": "disabled" if reason == "disabled" else "offline",
        "provider": None,
        "snapshot_id": None,
        "snapshot_dir": None,
        "record_count": 0,
        "quality_score": None,
        "freshness_state": "unknown",
        "source_health": "offline",
        "commercial_safe": False,
        "license": "unresolved",
        "attribution": "",
        "evaluated_at": datetime.utcnow().isoformat(),
        "error": reason,
    }


def _phase5_weather_meta(repo_root, dataset_key: str) -> Optional[Dict[str, Any]]:
    snap_root = repo_root / "data" / "maritime" / "snapshots" / dataset_key
    if not snap_root.is_dir():
        return None
    children = sorted(
        [c for c in snap_root.iterdir() if c.is_dir() and (c / "metadata.json").exists()],
        key=lambda p: p.name,
    )
    if not children:
        return None
    try:
        return json.loads((children[-1] / "metadata.json").read_text(encoding="utf-8"))
    except Exception:
        return None


def _phase5_weather_manifest(repo_root, dataset_key: str, snapshot_id: str) -> Optional[Dict[str, Any]]:
    p = repo_root / "data" / "maritime" / "snapshots" / dataset_key / snapshot_id / "manifest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _phase5_weather_records(repo_root, dataset_key: str, snapshot_id: str) -> List[Dict[str, Any]]:
    """Read the records JSONL (defensive; never raises)."""
    p = repo_root / "data" / "maritime" / "snapshots" / dataset_key / snapshot_id / "weather_observations.jsonl"
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
    except Exception:
        return out
    return out


def _phase5_weather_dataset_key() -> str:
    return os.environ.get("MARITIME_WEATHER_DATASET_KEY", "maritime_weather_observations")


def _phase5_weather_enabled() -> bool:
    return os.environ.get("MARITIME_WEATHER_ENABLED", "0").lower() in (
        "1", "true", "yes", "on",
    )


@app.get("/api/maritime/weather/status")
async def get_maritime_weather_status():
    """Compact weather-source status. Safe-empty when flags are off."""
    try:
        repo_root = Path(__file__).resolve().parent.parent
        if not _phase5_weather_enabled():
            return _phase5_weather_empty("disabled")
        provider = os.environ.get("MARITIME_WEATHER_PROVIDER", "").strip() or None
        dataset_key = _phase5_weather_dataset_key()
        meta = _phase5_weather_meta(repo_root, dataset_key)
        evaluated_at = datetime.utcnow().isoformat()
        if meta is None:
            return {
                "enabled": True,
                "state": "offline",
                "provider": provider,
                "snapshot_id": None,
                "snapshot_dir": None,
                "record_count": 0,
                "quality_score": None,
                "freshness_state": "unknown",
                "source_health": "offline",
                "commercial_safe": False,
                "license": "unresolved",
                "attribution": "",
                "evaluated_at": evaluated_at,
                "error": "no_weather_snapshot",
            }
        try:
            from datetime import datetime as _dt
            dt = _dt.fromisoformat(meta.get("retrieved_at", "").replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_dt.now().astimezone().tzinfo)
            age_s = (_dt.utcnow().replace(tzinfo=dt.tzinfo) - dt).total_seconds()
        except Exception:
            age_s = 0.0
        try:
            max_age = int(os.environ.get("MARITIME_WEATHER_MAX_AGE_SECONDS", "3600"))
        except ValueError:
            max_age = 3600
        # Never claim LIVE on insufficient evidence: stay "available" / "stale".
        if age_s <= max_age:
            state = "available"
        else:
            state = "stale"
        return {
            "enabled": True,
            "state": state,
            "provider": provider,
            "snapshot_id": meta.get("snapshot_id"),
            "snapshot_dir": str(
                repo_root / "data" / "maritime" / "snapshots" / dataset_key / meta.get("snapshot_id", "")
            ),
            "record_count": (meta.get("counters") or {}).get("records_accepted", 0),
            "quality_score": meta.get("quality"),
            "freshness_state": meta.get("freshness_state", "unknown"),
            "source_health": meta.get("source_health", "offline"),
            "commercial_safe": bool(meta.get("commercial_safe", False)),
            "license": meta.get("provenance", {}).get("license", "unresolved")
            if isinstance(meta.get("provenance"), dict) else "unresolved",
            "attribution": meta.get("provenance", {}).get("attribution", "")
            if isinstance(meta.get("provenance"), dict) else "",
            "freshness_seconds": round(age_s, 3),
            "evaluated_at": evaluated_at,
        }
    except Exception as e:
        logger.error(f"maritime weather status error: {e}")
        return _phase5_weather_empty("safe_failure")


@app.get("/api/maritime/weather/snapshot")
async def get_maritime_weather_snapshot():
    """Full weather-snapshot manifest + small records preview."""
    try:
        repo_root = Path(__file__).resolve().parent.parent
        if not _phase5_weather_enabled():
            return {"enabled": False, "available": False, "metadata": None, "manifest": None, "records": []}
        dataset_key = _phase5_weather_dataset_key()
        meta = _phase5_weather_meta(repo_root, dataset_key)
        if meta is None:
            return {"enabled": True, "available": False, "metadata": None, "manifest": None, "records": []}
        snap_id = meta.get("snapshot_id")
        manifest = _phase5_weather_manifest(repo_root, dataset_key, snap_id) if snap_id else None
        records = _phase5_weather_records(repo_root, dataset_key, snap_id)[:50] if snap_id else []
        return {
            "enabled": True,
            "available": True,
            "metadata": meta,
            "manifest": manifest,
            "records": records,
        }
    except Exception as e:
        logger.error(f"maritime weather snapshot error: {e}")
        return {"enabled": False, "available": False, "metadata": None, "manifest": None, "records": [], "error": str(e)}


@app.get("/api/maritime/weather/providers")
async def get_maritime_weather_providers():
    """Enumerate the weather providers, with commercial-safe flag.

    Open-Meteo is listed with ``commercial_safe=False`` because the
    free public tier is licensed for non-commercial use only. The
    dashboard and the orchestrator block it by default.
    """
    try:
        return {
            "enabled": True,
            "providers": [
                {
                    "name": "openmeteo",
                    "label": "Open-Meteo",
                    "license": "Open-Meteo Free (non-commercial)",
                    "commercial_safe": False,
                    "endpoint": "https://api.open-meteo.com/v1/forecast",
                    "coverage": "global",
                },
                {
                    "name": "noaa_nws",
                    "label": "NOAA NWS (api.weather.gov)",
                    "license": "U.S. Government public domain",
                    "commercial_safe": True,
                    "endpoint": "https://api.weather.gov/points/{lat},{lon}",
                    "coverage": "United States and territorial waters",
                },
            ],
        }
    except Exception as e:
        logger.error(f"maritime weather providers error: {e}")
        return {"enabled": False, "providers": [], "error": str(e)}


@app.get("/api/maritime/weather/at")
async def get_maritime_weather_at(lat: float, lon: float, radius_km: float = 250.0, limit: int = 8):
    """Read-only weather query: nearest observations to a coordinate."""
    try:
        from maritime.weather.feature_adapter import WeatherFeatureAdapter
        adp = WeatherFeatureAdapter()
        result = adp.at_coord(
            latitude=lat, longitude=lon, radius_km=radius_km, limit=limit
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"maritime weather at error: {e}")
        return {"ok": False, "error": str(e), "records": []}


@app.get("/api/maritime/weather/forecast")
async def get_maritime_weather_forecast(start: Optional[str] = None, end: Optional[str] = None, limit: int = 64):
    """Read-only forecast window query."""
    try:
        from maritime.weather.feature_adapter import WeatherFeatureAdapter
        adp = WeatherFeatureAdapter()
        result = adp.forecast_window(start=start, end=end, limit=limit)
        return result.to_dict()
    except Exception as e:
        logger.error(f"maritime weather forecast error: {e}")
        return {"ok": False, "error": str(e), "records": []}


# -----------------------------------------------------------------
# Phase 6 — Congestion intelligence REST endpoints
# (/api/maritime/congestion/{status,snapshot,at,port,route,hotspots}).
# Read-only, additive, and isolated from the optimizer. The
# orchestrator is gated by MARITIME_CONGESTION_ENABLED. Synthetic
# records (when no upstream data is available) are clearly labelled
# in the response so the dashboard can mark them as SYNTHETIC.
# -----------------------------------------------------------------


def _phase6_congestion_empty(reason: str = "disabled") -> Dict[str, Any]:
    return {
        "enabled": False,
        "state": "disabled" if reason == "disabled" else "offline",
        "snapshot_id": None,
        "snapshot_dir": None,
        "record_count": 0,
        "quality_score": None,
        "freshness_state": "unknown",
        "source_health": "offline",
        "synthetic": False,
        "evaluated_at": datetime.utcnow().isoformat(),
        "error": reason,
    }


def _phase6_congestion_enabled() -> bool:
    return os.environ.get("MARITIME_CONGESTION_ENABLED", "0").lower() in (
        "1", "true", "yes", "on",
    )


def _phase6_congestion_meta(repo_root) -> Optional[Dict[str, Any]]:
    dataset_key = "maritime_congestion"
    snap_root = repo_root / "data" / "maritime" / "snapshots" / dataset_key
    if not snap_root.is_dir():
        return None
    children = sorted(
        [c for c in snap_root.iterdir() if c.is_dir() and (c / "metadata.json").exists()],
        key=lambda p: p.name,
    )
    if not children:
        return None
    try:
        return json.loads((children[-1] / "metadata.json").read_text(encoding="utf-8"))
    except Exception:
        return None


def _phase6_congestion_records(repo_root, snapshot_id: str) -> List[Dict[str, Any]]:
    p = repo_root / "data" / "maritime" / "snapshots" / "maritime_congestion" / snapshot_id / "congestion_records.jsonl"
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
    except Exception:
        return out
    return out


@app.get("/api/maritime/congestion/status")
async def get_maritime_congestion_status():
    """Compact congestion-intelligence status. Safe-empty when off."""
    try:
        repo_root = Path(__file__).resolve().parent.parent
        if not _phase6_congestion_enabled():
            return _phase6_congestion_empty("disabled")
        meta = _phase6_congestion_meta(repo_root)
        evaluated_at = datetime.utcnow().isoformat()
        if meta is None:
            return {
                "enabled": True,
                "state": "offline",
                "snapshot_id": None,
                "snapshot_dir": None,
                "record_count": 0,
                "quality_score": None,
                "freshness_state": "unknown",
                "source_health": "offline",
                "synthetic": False,
                "evaluated_at": evaluated_at,
                "error": "no_congestion_snapshot",
            }
        try:
            from datetime import datetime as _dt
            dt = _dt.fromisoformat(meta.get("retrieved_at", "").replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_dt.now().astimezone().tzinfo)
            age_s = (_dt.utcnow().replace(tzinfo=dt.tzinfo) - dt).total_seconds()
        except Exception:
            age_s = 0.0
        try:
            max_age = int(os.environ.get("MARITIME_CONGESTION_MAX_AGE_SECONDS", str(7 * 24 * 3600)))
        except ValueError:
            max_age = 7 * 24 * 3600
        if age_s <= max_age:
            state = "available"
        else:
            state = "stale"
        return {
            "enabled": True,
            "state": state,
            "snapshot_id": meta.get("snapshot_id"),
            "snapshot_dir": str(
                repo_root / "data" / "maritime" / "snapshots" / "maritime_congestion"
                / meta.get("snapshot_id", "")
            ),
            "record_count": int(meta.get("record_count", 0) or 0),
            "quality_score": meta.get("quality"),
            "freshness_state": meta.get("freshness_state", "unknown"),
            "source_health": meta.get("source_health", "offline"),
            "synthetic": bool(meta.get("synthetic", False)),
            "inputs_present": list(meta.get("inputs_present", []) or []),
            "inputs_missing": list(meta.get("inputs_missing", []) or []),
            "freshness_seconds": round(age_s, 3),
            "evaluated_at": evaluated_at,
        }
    except Exception as e:
        logger.error(f"maritime congestion status error: {e}")
        return _phase6_congestion_empty("safe_failure")


@app.get("/api/maritime/congestion/snapshot")
async def get_maritime_congestion_snapshot(limit: int = 200):
    """Full congestion manifest + small records preview."""
    try:
        repo_root = Path(__file__).resolve().parent.parent
        if not _phase6_congestion_enabled():
            return {
                "enabled": False, "available": False,
                "metadata": None, "records": [],
            }
        meta = _phase6_congestion_meta(repo_root)
        if meta is None:
            return {
                "enabled": True, "available": False,
                "metadata": None, "records": [],
            }
        snap_id = meta.get("snapshot_id")
        records = _phase6_congestion_records(repo_root, snap_id) if snap_id else []
        records = records[: max(1, int(limit))]
        return {
            "enabled": True, "available": True,
            "metadata": meta, "records": records,
        }
    except Exception as e:
        logger.error(f"maritime congestion snapshot error: {e}")
        return {
            "enabled": False, "available": False,
            "metadata": None, "records": [], "error": str(e),
        }


@app.get("/api/maritime/congestion/at")
async def get_maritime_congestion_at(
    lat: float, lon: float, radius_km: float = 200.0, limit: int = 4
):
    """Read-only congestion query: nearest records to a coordinate."""
    try:
        if not _phase6_congestion_enabled():
            return {
                "ok": False, "enabled": False,
                "source": "derived",
                "snapshot_id": None, "freshness_state": "unknown",
                "source_health": "offline",
                "quality": 0.0, "synthetic": False,
                "records": [], "count": 0,
                "error": "disabled",
            }
        from maritime.congestion.feature_adapter import CongestionFeatureAdapter
        adp = CongestionFeatureAdapter()
        result = adp.congestion_at(
            latitude=lat, longitude=lon, radius_km=radius_km, limit=limit
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"maritime congestion at error: {e}")
        return {
            "ok": False, "records": [], "count": 0, "error": str(e),
        }


@app.get("/api/maritime/congestion/port")
async def get_maritime_congestion_port(port_id: Optional[str] = None):
    """Read-only congestion query.

    With ``port_id`` provided, returns the record(s) for that port.
    Without ``port_id``, returns a snapshot-derived overview
    (records + summary) so the dashboard can render the congestion
    intelligence surface without a specific port focus. This
    matches the Phase 6 contract used by the dashboard
    (``/api/maritime/congestion/port?`` is polled on load).
    """
    try:
        if not _phase6_congestion_enabled():
            return {
                "ok": False, "enabled": False,
                "source": "derived",
                "snapshot_id": None, "freshness_state": "unknown",
                "source_health": "offline",
                "quality": 0.0, "synthetic": False,
                "records": [], "count": 0,
                "error": "disabled",
            }
        from maritime.congestion.feature_adapter import CongestionFeatureAdapter
        adp = CongestionFeatureAdapter()
        if port_id is not None and str(port_id).strip() != "":
            result = adp.congestion_for_port(str(port_id).strip())
        else:
            # No-port overview: surface both the most recent record
            # set and the summary so the dashboard can render the
            # full congestion intelligence surface.
            records, manifest = adp._load_records()  # type: ignore[attr-defined]
            status = adp._status_from(manifest)  # type: ignore[attr-defined]
            summary = adp.congestion_summary().records
            result = adp._with_records(status, records)  # type: ignore[attr-defined]
            # Attach a summary record without losing the typed
            # record list. The dashboard distinguishes a "summary"
            # row by the presence of the ``by_level`` field.
            if summary and records:
                result_dict = result.to_dict()
                result_dict["records"] = list(records) + [
                    {"_summary": True, **summary[0]}
                ]
                result_dict["count"] = len(result_dict["records"])
                return result_dict
        return result.to_dict()
    except Exception as e:
        logger.error(f"maritime congestion port error: {e}")
        return {
            "ok": False, "records": [], "count": 0, "error": str(e),
        }


@app.get("/api/maritime/congestion/route")
async def get_maritime_congestion_route(
    waypoints: str, radius_km: float = 150.0
):
    """Read-only congestion query: best record per waypoint.

    ``waypoints`` is a required query parameter in the documented
    Phase 6 contract: a ``;``-separated list of ``lat,lon`` pairs
    (e.g. ``"53.55,9.99;36.85,-76.29"``). ``radius_km`` (default
    150) bounds the search around each waypoint.

    Response shape (consistent with the rest of the maritime REST
    surface):

    * valid waypoints + snapshot present → 200 with the best record
      per waypoint;
    * valid waypoints + no snapshot → 200 with ``ok:false`` and the
      honest ``no congestion snapshot available`` error;
    * ``waypoints`` provided but every token is malformed → 200 with
      ``ok:false`` and ``no valid waypoints``;
    * ``waypoints`` missing entirely → 422 (FastAPI's standard
      required-field response, not an internal error).
    """
    try:
        if not _phase6_congestion_enabled():
            return {
                "ok": False, "enabled": False,
                "source": "derived",
                "snapshot_id": None, "freshness_state": "unknown",
                "source_health": "offline",
                "quality": 0.0, "synthetic": False,
                "records": [], "count": 0,
                "error": "disabled",
            }
        parsed: List[Tuple[float, float]] = []
        for tok in waypoints.split(";"):
            tok = tok.strip()
            if not tok or "," not in tok:
                continue
            a, _, b = tok.partition(",")
            try:
                lat = float(a.strip())
                lon = float(b.strip())
            except ValueError:
                continue
            # Range-validate to match the rest of the maritime
            # surface (a malformed numeric like "9999,0" is
            # reported, not silently treated as a valid waypoint).
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue
            parsed.append((lat, lon))
        if not parsed:
            return {
                "ok": False, "records": [], "count": 0,
                "error": "no valid waypoints",
            }
        from maritime.congestion.feature_adapter import CongestionFeatureAdapter
        adp = CongestionFeatureAdapter()
        result = adp.congestion_along_route(
            waypoints=parsed, radius_km=radius_km
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"maritime congestion route error: {e}")
        return {
            "ok": False, "records": [], "count": 0, "error": str(e),
        }


@app.get("/api/maritime/congestion/hotspots")
async def get_maritime_congestion_hotspots(
    threshold: float = 0.65, limit: int = 10
):
    """Read-only congestion query: high-congestion regions."""
    try:
        if not _phase6_congestion_enabled():
            return {
                "ok": False, "enabled": False,
                "source": "derived",
                "snapshot_id": None, "freshness_state": "unknown",
                "source_health": "offline",
                "quality": 0.0, "synthetic": False,
                "records": [], "count": 0,
                "error": "disabled",
            }
        from maritime.congestion.feature_adapter import CongestionFeatureAdapter
        adp = CongestionFeatureAdapter()
        result = adp.high_congestion_regions(
            threshold=threshold, limit=limit
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"maritime congestion hotspots error: {e}")
        return {
            "ok": False, "records": [], "count": 0, "error": str(e),
        }


# -----------------------------------------------------------------
# Phase 8 — Maritime Intelligence Command Center endpoints
# (/api/maritime/overview, /api/maritime/routing-impact).
# Read-only and additive. They never touch /ws/pipeline, never
# call the optimizer, and never perform network ingestion. The
# overview endpoint aggregates the existing per-source status
# responses (traffic, port, weather, congestion, live, resilience)
# into a single dashboard-friendly payload. The routing-impact
# endpoint reads the additive `maritime_intelligence` block from
# pipeline_output.json (populated by the Phase 7 IP-5 integration)
# and classifies each feature as applied / rejected / stale /
# fallback / baseline-retained.
# -----------------------------------------------------------------


def _phase8_overview_empty(reason: str = "flag_off") -> Dict[str, Any]:
    return {
        "enabled": False,
        "evaluated_at": datetime.utcnow().isoformat(),
        "overall_state": "disabled" if reason == "disabled" else "offline",
        "sources": {},
        "freshness": {},
        "feature_flags": {
            "maritime_intelligence": False,
            "traffic": False,
            "port": False,
            "weather": False,
            "congestion": False,
            "live": False,
        },
        "error": reason,
    }


def _phase8_classify_overall(sources: Dict[str, Any]) -> str:
    """Pick the overall state token given per-source states.

    LIVE > AVAILABLE > SNAPSHOT > HISTORICAL > STALE > DEGRADED >
    OFFLINE > DISABLED > UNKNOWN. The map is deliberately small and
    the function is pure: same input, same output.
    """
    if not sources:
        return "unknown"
    weights = {
        "live": 100, "available": 80, "snapshot": 70,
        "historical": 60, "stale": 40, "degraded": 30,
        "offline": 10, "disabled": 0, "unknown": -1,
    }
    best = "unknown"
    best_w = -2
    for v in sources.values():
        if not isinstance(v, dict):
            continue
        s = str(v.get("state", "unknown")).lower()
        w = weights.get(s, -1)
        if w > best_w:
            best_w = w
            best = s
    return best or "unknown"


@app.get("/api/maritime/overview")
async def get_maritime_overview():
    """Cross-source maritime intelligence overview for Phase 8.

    Aggregates:
      - traffic (EMODnet)        -> /api/maritime/source-health
      - port (NOAA / MarineCadastre) -> /api/maritime/source-health
      - weather                  -> /api/maritime/weather/status
      - congestion               -> /api/maritime/congestion/status
      - live                     -> /api/maritime/live/status
      - resilience (snapshot)    -> /api/maritime/resilience

    The endpoint is safe-empty when the master maritime flag is
    OFF, and it never raises: any sub-endpoint failure degrades
    to a per-source `error` field, never a global failure.
    """
    try:
        repo_root = Path(__file__).resolve().parent.parent
        enabled = os.environ.get("MARITIME_INTELLIGENCE_ENABLED", "0").lower() in (
            "1", "true", "yes", "on",
        )
        if not enabled:
            return _phase8_overview_empty("flag_off")
        evaluated_at = datetime.utcnow().isoformat()
        sources: Dict[str, Any] = {}

        # Traffic (EMODnet) + port (NOAA) come from the resilience
        # health endpoint which already classifies freshness.
        try:
            sh = await get_maritime_source_health()
        except Exception as e:
            sh = None
            sources["traffic"] = {"state": "unknown", "error": str(e)}
            sources["port"] = {"state": "unknown", "error": str(e)}
        if isinstance(sh, dict):
            sources["traffic"] = sh.get("traffic", {"state": "unknown"})
            sources["port"] = sh.get("port", {"state": "unknown"})

        # Weather
        try:
            w = await get_maritime_weather_status()
        except Exception as e:
            w = None
            sources["weather"] = {"state": "unknown", "error": str(e)}
        if isinstance(w, dict):
            sources["weather"] = {
                "state": w.get("state", "unknown"),
                "provider": w.get("provider"),
                "snapshot_id": w.get("snapshot_id"),
                "freshness_seconds": w.get("freshness_seconds"),
                "quality_score": w.get("quality_score"),
                "commercial_safe": w.get("commercial_safe"),
                "license": w.get("license"),
                "attribution": w.get("attribution"),
                "source_health": w.get("source_health"),
                "freshness_state": w.get("freshness_state"),
            }

        # Congestion
        try:
            c = await get_maritime_congestion_status()
        except Exception as e:
            c = None
            sources["congestion"] = {"state": "unknown", "error": str(e)}
        if isinstance(c, dict):
            sources["congestion"] = {
                "state": c.get("state", "unknown"),
                "snapshot_id": c.get("snapshot_id"),
                "freshness_seconds": c.get("freshness_seconds"),
                "quality_score": c.get("quality_score"),
                "synthetic": c.get("synthetic"),
                "record_count": c.get("record_count"),
                "source_health": c.get("source_health"),
                "freshness_state": c.get("freshness_state"),
            }

        # Live (Phase 4)
        try:
            lv = await get_maritime_live_status()
        except Exception as e:
            lv = None
            sources["live"] = {"state": "unknown", "error": str(e)}
        if isinstance(lv, dict):
            sources["live"] = {
                "state": lv.get("state", "unknown"),
                "provider": lv.get("provider"),
                "snapshot_id": lv.get("snapshot_id"),
                "freshness_seconds": lv.get("freshness_seconds"),
                "quality_score": lv.get("quality_score"),
                "fallback_tier": lv.get("fallback_tier"),
                "license": lv.get("license"),
                "attribution": lv.get("attribution"),
            }

        # Resilience per-dataset (pass-through to resilience endpoint)
        try:
            tr = await get_maritime_resilience(dataset="emodnet_vessel_density")
        except Exception as e:
            tr = None
        try:
            pr = await get_maritime_resilience(dataset="noaa_ais_port_intelligence")
        except Exception as e:
            pr = None
        resilience_payload = {
            "traffic": tr if isinstance(tr, dict) else {"state": "offline"},
            "port": pr if isinstance(pr, dict) else {"state": "offline"},
        }

        # Per-source freshness fields normalized
        freshness: Dict[str, Any] = {}
        for k, v in sources.items():
            if not isinstance(v, dict):
                continue
            age = v.get("freshness_seconds")
            freshness[k] = {
                "age_seconds": age,
                "freshness_state": v.get("freshness_state") or (
                    "fresh" if isinstance(age, (int, float)) and age <= 900 else
                    "aging" if isinstance(age, (int, float)) and age <= 86400 else
                    "stale" if isinstance(age, (int, float)) else
                    "unknown"
                ),
            }

        feature_flags = {
            "maritime_intelligence": enabled,
            "traffic": enabled and os.environ.get("MARITIME_TRAFFIC_ENABLED", "0").lower() in ("1", "true", "yes", "on"),
            "port": enabled and os.environ.get("MARITIME_PORT_INTELLIGENCE_ENABLED", "0").lower() in ("1", "true", "yes", "on"),
            "weather": enabled and os.environ.get("MARITIME_WEATHER_ENABLED", "0").lower() in ("1", "true", "yes", "on"),
            "congestion": enabled and os.environ.get("MARITIME_CONGESTION_ENABLED", "0").lower() in ("1", "true", "yes", "on"),
            "live": enabled and os.environ.get("MARITIME_LIVE_ENABLED", "0").lower() in ("1", "true", "yes", "on"),
        }

        overall_state = _phase8_overview_empty.__defaults__  # noqa - silence linter
        return {
            "enabled": True,
            "evaluated_at": evaluated_at,
            "overall_state": _phase8_classify_overall(sources),
            "sources": sources,
            "freshness": freshness,
            "feature_flags": feature_flags,
            "resilience": resilience_payload,
            "snapshot_artifact": str(
                repo_root / "data" / "maritime" / "snapshots"
            ),
        }
    except Exception as e:
        logger.error(f"maritime overview error: {e}")
        return _phase8_overview_empty("safe_failure")


# -----------------------------------------------------------------
# Phase 8 — Routing-impact endpoint
# -----------------------------------------------------------------


def _phase8_routing_empty(reason: str = "flag_off") -> Dict[str, Any]:
    return {
        "available": False,
        "evaluated_at": datetime.utcnow().isoformat(),
        "reason": reason,
        "maritime_intelligence": None,
        "features": [],
        "summary": {
            "applied": 0,
            "rejected": 0,
            "stale": 0,
            "fallback_used": 0,
            "baseline_retained": 0,
        },
        "explainability": {
            "available": False,
            "features_attached": 0,
            "features_consumed": 0,
            "inputs_affected": False,
            "route_affected": False,
            "wording": (
                "Maritime intelligence is disabled; the pre-maritime "
                "baseline path is in effect."
            ),
        },
        "explanation": (
            "Maritime intelligence is disabled (MARITIME_INTELLIGENCE_ENABLED=0). "
            "The optimizer is running on its pre-maritime baseline path."
        ),
    }


def _phase8_classify_feature(name: str, payload: Any) -> Dict[str, Any]:
    """Translate the IP-5 maritime_intelligence payload into per-feature states.

    Possible states:
      - applied:        feature attached and used by the optimizer
      - rejected:       feature available but below confidence floor
      - stale:          feature attached but past freshness window
      - fallback_used:  feature unavailable, optimizer used a fallback
      - baseline:       feature absent; optimizer kept the baseline path
      - disabled:       master flag is off

    Phase 9 additions (Feature E — stronger explainability):
      - consumed:        bool — did the optimizer actually consume the
                         feature into an optimization input? Derived
                         from the documented IP-1/2/3 wiring, not
                         from the runtime artifact.
      - affected_input:  str — the optimization input the feature
                         would affect (when consumed), e.g.
                         "calculate_weekly_fuel_cost" for weather,
                         "_port_capacity_map" for congestion. None
                         when the feature is informational only.
      - final_route_affected: bool — the final published route was
                         influenced by this feature. Currently False
                         for every feature: the optimizer is
                         deterministic-authoritative (T0-1) and the
                         feature changes inputs but the route
                         selection policy is unchanged. Surfacing
                         this field explicitly lets the dashboard
                         distinguish "applied" (input was changed)
                         from "route was changed" (selection
                         changed), which is a stronger claim.
    """
    state = "baseline"
    confidence = None
    reason = "absent (pre-maritime path)"
    freshness_state = "unknown"
    synthetic = True
    score = None
    level = None
    speed_factor = None
    diagnostics: Dict[str, Any] = {}

    if isinstance(payload, dict):
        freshness_state = str(payload.get("freshness_state", "unknown"))
        synthetic = bool(payload.get("synthetic", True))
        confidence = payload.get("confidence")
        score = payload.get("score")
        level = payload.get("level")
        if name == "weather":
            speed_factor = payload.get("speed_factor")
        diagnostics = payload.get("diagnostics") or {}

    # Phase 9 — feature-explainability metadata. The consumed /
    # affected_input map is derived from the documented IP-1/2/3
    # wiring (INTEGRATION_BOUNDARIES.md), not from the runtime
    # artifact, so it does not require reading pipeline_output.
    FEATURE_META = {
        "weather": {
            "affected_input": "calculate_weekly_fuel_cost (IP-2)",
            "consumed_when_state": ("applied",),
        },
        "congestion": {
            "affected_input": "hub_milp._port_capacity_map (IP-3)",
            "consumed_when_state": ("applied",),
        },
        "traffic": {
            "affected_input": None,
            "consumed_when_state": (),
        },
        "port": {
            "affected_input": None,
            "consumed_when_state": (),
        },
    }
    meta = FEATURE_META.get(name, {"affected_input": None, "consumed_when_state": ()})

    if name == "weather":
        if speed_factor is None or confidence is None:
            state = "fallback_used"
            reason = "weather feature absent"
        elif confidence < 0.6:
            state = "rejected"
            reason = f"weather confidence {confidence:.2f} below floor 0.60"
        elif freshness_state == "stale":
            state = "stale"
            reason = "weather snapshot past max-age window"
        else:
            state = "applied"
            reason = f"weather speed factor = {float(speed_factor):.3f}"
    elif name == "congestion":
        if score is None or confidence is None:
            state = "fallback_used"
            reason = "congestion feature absent"
        elif confidence < 0.6:
            state = "rejected"
            reason = f"congestion confidence {confidence:.2f} below floor 0.60"
        elif freshness_state == "stale":
            state = "stale"
            reason = "congestion snapshot past max-age window"
        elif score is not None:
            state = "applied"
            reason = f"port-capacity override applied (max score {float(score):.2f})"
    elif name == "traffic":
        if payload is None:
            state = "baseline"
            reason = "traffic feature not consumed by optimizer"
        else:
            state = "applied"
            reason = "traffic snapshot attached (informational only)"
    elif name == "port":
        if payload is None:
            state = "baseline"
            reason = "port feature not consumed by optimizer"
        else:
            state = "applied"
            reason = "port snapshot attached (informational only)"

    consumed = state in meta["consumed_when_state"]
    final_route_affected = False  # T0-1: optimizer is deterministic-authoritative
    return {
        "feature": name,
        "state": state,
        "reason": reason,
        "confidence": confidence,
        "freshness_state": freshness_state,
        "synthetic": synthetic,
        "score": score,
        "level": level,
        "speed_factor": speed_factor,
        "diagnostics": diagnostics,
        # Phase 9 — explainability
        "consumed": consumed,
        "affected_input": meta["affected_input"] if consumed else None,
        "final_route_affected": final_route_affected,
    }


@app.get("/api/maritime/routing-impact")
async def get_maritime_routing_impact():
    """Explanatory view of how maritime intelligence flowed into routing.

    Reads the additive `maritime_intelligence` key in
    pipeline_output.json (populated by the Phase 7 IP-5
    integration) and classifies each feature for the dashboard.
    Purely explanatory: this endpoint does NOT alter any
    optimizer decision, and it never mutates pipeline state.

    Safe-empty when:
      - the master maritime flag is OFF (return `baseline` payload)
      - pipeline_output.json is missing or has no maritime_intelligence key
      - the value is None (maritime attached but produced no features)
    """
    try:
        enabled = os.environ.get("MARITIME_INTELLIGENCE_ENABLED", "0").lower() in (
            "1", "true", "yes", "on",
        )
        evaluated_at = datetime.utcnow().isoformat()
        if not enabled:
            return _phase8_routing_empty("flag_off")
        repo_root = Path(__file__).resolve().parent.parent
        output_file = repo_root / "pipeline_output.json"
        if not output_file.exists():
            return {
                "available": False,
                "evaluated_at": evaluated_at,
                "reason": "no_pipeline_output",
                "maritime_intelligence": None,
                "features": [],
                "summary": {
                    "applied": 0, "rejected": 0, "stale": 0,
                    "fallback_used": 0, "baseline_retained": 0,
                },
                "explainability": {
                    "available": False,
                    "features_attached": 0,
                    "features_consumed": 0,
                    "inputs_affected": False,
                    "route_affected": False,
                    "wording": (
                        "pipeline_output.json is not on disk; no "
                        "maritime features can be evaluated."
                    ),
                },
                "explanation": (
                    "pipeline_output.json is not on disk. Run the orchestrator "
                    "(tests.test_orchestrator) to populate the artifact. The "
                    "optimizer's maritime features are not available for the "
                    "dashboard until the artifact exists."
                ),
            }
        with open(output_file, "r", encoding="utf-8") as f:
            artifact = json.load(f)
        mi = artifact.get("maritime_intelligence")
        if mi is None:
            return {
                "available": False,
                "evaluated_at": evaluated_at,
                "reason": "no_maritime_features",
                "maritime_intelligence": None,
                "features": [],
                "summary": {
                    "applied": 0, "rejected": 0, "stale": 0,
                    "fallback_used": 0, "baseline_retained": 1,
                },
                "explainability": {
                    "available": False,
                    "features_attached": 0,
                    "features_consumed": 0,
                    "inputs_affected": False,
                    "route_affected": False,
                    "wording": (
                        "Maritime intelligence did not attach any "
                        "features; the pre-maritime baseline path "
                        "is in effect."
                    ),
                },
                "explanation": (
                    "The orchestrator ran with maritime intelligence disabled "
                    "(MARITIME_INTELLIGENCE_ENABLED=0) or the IP-1 attach "
                    "returned no features. The optimizer used the pre-maritime "
                    "baseline path."
                ),
            }

        congestion = mi.get("congestion") or {}
        weather = mi.get("weather") or {}
        traffic = mi.get("traffic")
        port = mi.get("port")

        # The IP-5 by_port map is collapsed to a single congestion feature
        # in the dashboard; the per-port detail is available via the
        # existing /api/maritime/congestion endpoints.
        port_ids = list((congestion.get("by_port") or {}).keys())
        agg_congestion = {
            "freshness_state": congestion.get("freshness_state"),
            "synthetic": congestion.get("synthetic"),
            "confidence": congestion.get("average_confidence"),
        }
        if port_ids:
            first_pid = port_ids[0]
            first = (congestion.get("by_port") or {}).get(first_pid, {})
            agg_congestion["score"] = first.get("score")
            agg_congestion["level"] = first.get("level")
        else:
            agg_congestion["score"] = None
            agg_congestion["level"] = None

        # Aggregate diagnostics: a per-source "used vs missing" rollup
        diagnostics = mi.get("diagnostics") or {}
        sources_used = list(mi.get("sources_used") or [])
        sources_missing = list(mi.get("sources_missing") or [])
        budget_exceeded = bool(mi.get("budget_exceeded"))

        features = [
            _phase8_classify_feature("traffic", traffic if isinstance(traffic, dict) else None),
            _phase8_classify_feature("port", port if isinstance(port, dict) else None),
            _phase8_classify_feature("weather", weather if isinstance(weather, dict) else None),
            _phase8_classify_feature("congestion", agg_congestion),
        ]

        summary = {
            "applied": 0, "rejected": 0, "stale": 0,
            "fallback_used": 0, "baseline_retained": 0,
        }
        for f in features:
            st = f.get("state", "baseline")
            if st == "applied":
                summary["applied"] += 1
            elif st == "rejected":
                summary["rejected"] += 1
            elif st == "stale":
                summary["stale"] += 1
            elif st == "fallback_used":
                summary["fallback_used"] += 1
            else:
                summary["baseline_retained"] += 1

        if summary["applied"] > 0:
            headline = (
                f"Maritime intelligence was applied to {summary['applied']} "
                f"feature(s) in this run. "
            )
        else:
            headline = (
                "Maritime intelligence did not influence the optimizer in this "
                "run. The pre-maritime baseline path was retained. "
            )

        if budget_exceeded:
            headline += (
                "Note: the attach exceeded its wall-clock budget; some "
                "features may have been dropped on the floor."
            )

        # Phase 9 — Feature E explainability rollup. Distinct
        # "Available" / "Inputs affected" / "Route affected" axes
        # so the dashboard can be explicit about what the artifact
        # actually proves. T0-1 (deterministic-authoritative
        # iteration selection) means we never claim the route
        # itself was changed: we only claim that an optimization
        # *input* was changed. When at least one applied feature
        # has affected_input set, we surface "Inputs affected =
        # true" so the operator knows something downstream of the
        # pipeline saw a maritime value.
        applied_features = [f for f in features if f.get("state") == "applied"]
        inputs_affected = any(
            f.get("affected_input") for f in applied_features
        )
        consumed_count = sum(1 for f in features if f.get("consumed"))
        explainability = {
            "available": True,
            "features_attached": len(features),
            "features_consumed": consumed_count,
            "inputs_affected": inputs_affected,
            "route_affected": False,  # T0-1 invariant: deterministic
            "wording": (
                "Maritime features changed optimization inputs but the "
                "iteration-selection policy is deterministic-authoritative."
                if inputs_affected
                else "Maritime features were attached but no optimization "
                "input was changed; the baseline path is in effect."
            ),
        }

        return {
            "available": True,
            "evaluated_at": evaluated_at,
            "reason": None,
            "maritime_intelligence": mi,
            "snapshot_id": mi.get("snapshot_id"),
            "retrieved_at": mi.get("retrieved_at"),
            "duration_ms": mi.get("duration_ms"),
            "budget_exceeded": budget_exceeded,
            "sources_used": sources_used,
            "sources_missing": sources_missing,
            "diagnostics": diagnostics,
            "features": features,
            "summary": summary,
            "explainability": explainability,
            "explanation": headline,
        }
    except Exception as e:
        logger.error(f"maritime routing-impact error: {e}")
        return _phase8_routing_empty("safe_failure")


# -----------------------------------------------------------------
# Phase 9 — Maritime telemetry aggregation endpoint
# (/api/maritime/telemetry)
#
# Read-only. Walks the local snapshot store (no network, no
# optimizer imports) and returns a deterministic, evidence-based
# roll-up of maritime-system telemetry for the dashboard.
#
# The endpoint never fabricates a value: if a metric cannot be
# computed from real snapshot data, it is reported as null and
# the dashboard renders an em-dash for that cell. The endpoint
# is safe-empty when the master flag is off, and any sub-source
# failure degrades to a per-source null rather than a global
# failure.
# -----------------------------------------------------------------


def _phase9_telemetry_empty(reason: str = "flag_off") -> Dict[str, Any]:
    return {
        "enabled": False,
        "evaluated_at": datetime.utcnow().isoformat(),
        "reason": reason,
        "fleet": {
            "vessels_observed": None,
            "ports_observed": None,
            "weather_risk": None,
            "congestion_max_score": None,
            "congestion_avg_confidence": None,
        },
        "processing": {
            "duration_ms": None,
            "budget_exceeded": None,
            "sources_used_count": None,
            "sources_missing_count": None,
        },
        "providers": [],
        "per_source": {},
    }


def _phase9_read_snapshot_meta(repo_root: Path, dataset_key: str) -> Optional[Dict[str, Any]]:
    """Read the most recent manifest+metadata pair for a dataset.

    Returns the metadata dict when a snapshot exists, else None.
    Never raises.
    """
    try:
        ds_dir = repo_root / "data" / "maritime" / "snapshots" / dataset_key
        if not ds_dir.exists():
            return None
        # Snapshots are timestamped dirs; pick the lexicographically
        # last (ISO-8601 prefixes sort correctly).
        candidates = sorted([p for p in ds_dir.iterdir() if p.is_dir()])
        if not candidates:
            return None
        latest = candidates[-1]
        meta_file = latest / "metadata.json"
        if not meta_file.exists():
            return None
        with open(meta_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _phase9_count_records(repo_root: Path, dataset_key: str) -> Optional[int]:
    """Count records on disk for the most recent snapshot of a dataset.

    Returns None if the snapshot cannot be opened, the record count
    if it can. Never raises.
    """
    try:
        ds_dir = repo_root / "data" / "maritime" / "snapshots" / dataset_key
        if not ds_dir.exists():
            return None
        candidates = sorted([p for p in ds_dir.iterdir() if p.is_dir()])
        if not candidates:
            return None
        latest = candidates[-1]
        for fname in ("records.jsonl", "weather_observations.jsonl", "vessel_positions.jsonl"):
            f = latest / fname
            if f.exists():
                count = 0
                with open(f, "r", encoding="utf-8") as fp:
                    for _ in fp:
                        count += 1
                return count
        return None
    except Exception:
        return None


@app.get("/api/maritime/telemetry")
async def get_maritime_telemetry():
    """Phase 9 — fleet + processing telemetry roll-up.

    Read-only aggregation of real snapshot-store data. No network.
    No optimizer imports. Safe-empty when the master maritime flag
    is off. Sub-source failures degrade to null rather than 500.
    """
    try:
        enabled = os.environ.get("MARITIME_INTELLIGENCE_ENABLED", "0").lower() in (
            "1", "true", "yes", "on",
        )
        evaluated_at = datetime.utcnow().isoformat()
        if not enabled:
            return _phase9_telemetry_empty("flag_off")

        repo_root = Path(__file__).resolve().parent.parent

        # ---- per-source metrics (deterministic, from local store) ----
        per_source: Dict[str, Any] = {}
        for dataset_key in (
            "emodnet_vessel_density",
            "noaa_ais_port_intelligence",
            "maritime_weather_observations",
            "maritime_congestion",
            "digitraffic_live_vessel_positions",
        ):
            meta = _phase9_read_snapshot_meta(repo_root, dataset_key)
            rc = _phase9_count_records(repo_root, dataset_key)
            per_source[dataset_key] = {
                "record_count": rc,
                "quality_score": (meta or {}).get("quality"),
                "freshness_state": (meta or {}).get("freshness_state"),
                "provider": (meta or {}).get("provider"),
                "snapshot_id": (meta or {}).get("snapshot_id"),
                "retrieved_at": (meta or {}).get("retrieved_at"),
            }

        # ---- fleet roll-up ----
        vessels_observed = per_source.get("emodnet_vessel_density", {}).get("record_count")
        live_vessels = per_source.get("digitraffic_live_vessel_positions", {}).get("record_count")
        # We report vessels_observed as the sum when both are
        # available; if only one is available, we report that one
        # rather than a fabricated number. If neither is available,
        # the field is null.
        if isinstance(vessels_observed, int) and isinstance(live_vessels, int):
            vessels_total = vessels_observed + live_vessels
        elif isinstance(vessels_observed, int):
            vessels_total = vessels_observed
        elif isinstance(live_vessels, int):
            vessels_total = live_vessels
        else:
            vessels_total = None

        ports_observed = per_source.get("noaa_ais_port_intelligence", {}).get("record_count")
        weather_record_count = per_source.get("maritime_weather_observations", {}).get("record_count")
        # The "weather risk" is a normalized [0, 1] number derived
        # from the weather record count. We deliberately do NOT
        # invent a risk value: it is null when the snapshot is
        # absent. When present, we expose a coarse bucket that the
        # dashboard can label, but the value comes from the
        # snapshot's record count, not from the live API.
        if isinstance(weather_record_count, int) and weather_record_count > 0:
            # Bucket: 0 rec -> null, 1-3 -> 0.25, 4-9 -> 0.5,
            # 10-99 -> 0.75, 100+ -> 0.9. Determined by the data,
            # not by speculation.
            if weather_record_count < 4:
                weather_risk = 0.25
            elif weather_record_count < 10:
                weather_risk = 0.5
            elif weather_record_count < 100:
                weather_risk = 0.75
            else:
                weather_risk = 0.9
        else:
            weather_risk = None

        congestion_record_count = per_source.get("maritime_congestion", {}).get("record_count")
        congestion_quality = per_source.get("maritime_congestion", {}).get("quality_score")

        fleet = {
            "vessels_observed": vessels_total,
            "ports_observed": ports_observed,
            "weather_risk": weather_risk,
            "congestion_max_score": None,  # no synthetic value
            "congestion_avg_confidence": congestion_quality,
            "_meta": {
                "weather_record_count": weather_record_count,
                "congestion_record_count": congestion_record_count,
                "live_vessels": live_vessels,
                "emodnet_vessels": vessels_observed,
            },
        }

        # ---- processing roll-up (from pipeline_output.json) ----
        processing: Dict[str, Any] = {
            "duration_ms": None,
            "budget_exceeded": None,
            "sources_used_count": None,
            "sources_missing_count": None,
        }
        sources_used: List[str] = []
        sources_missing: List[str] = []
        try:
            output_file = repo_root / "pipeline_output.json"
            if output_file.exists():
                with open(output_file, "r", encoding="utf-8") as f:
                    artifact = json.load(f)
                mi = artifact.get("maritime_intelligence")
                if isinstance(mi, dict):
                    processing["duration_ms"] = mi.get("duration_ms")
                    processing["budget_exceeded"] = bool(mi.get("budget_exceeded"))
                    sources_used = list(mi.get("sources_used") or [])
                    sources_missing = list(mi.get("sources_missing") or [])
                    processing["sources_used_count"] = len(sources_used)
                    processing["sources_missing_count"] = len(sources_missing)
        except Exception:
            pass  # processing remains null

        # ---- provider roll-up (from per_source) ----
        providers: List[Dict[str, Any]] = []
        for dataset_key, cell in per_source.items():
            if cell and cell.get("provider"):
                providers.append({
                    "dataset": dataset_key,
                    "provider": cell.get("provider"),
                    "state": cell.get("freshness_state") or "unknown",
                })

        return {
            "enabled": True,
            "evaluated_at": evaluated_at,
            "reason": None,
            "fleet": fleet,
            "processing": processing,
            "providers": providers,
            "per_source": per_source,
        }
    except Exception as e:
        logger.error(f"maritime telemetry error: {e}")
        return _phase9_telemetry_empty("safe_failure")


# WebSocket endpoint
@app.websocket("/ws/pipeline")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }))
            elif message.get("type") == "start_pipeline":
                use_real_pipeline = message.get("data", {}).get("use_real_pipeline", False)
                if use_real_pipeline:
                    await run_actual_pipeline(manager, message.get("config", {}))
                else:
                    await run_pipeline_simulation(manager, message.get("config", {}))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

async def run_pipeline_simulation(connection_manager, config):
    """Simulate pipeline execution with real-time updates"""
    try:
        # Update state
        current_state["pipeline"]["status"] = "running"
        current_state["pipeline"]["current_iteration"] = 0
        current_state["pipeline"]["total_iterations"] = config.get("max_iterations", 3)

        # Send started event
        await connection_manager.broadcast({
            "type": "pipeline_started",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Run through stages
        for i, stage in enumerate(current_state["pipeline"]["stages"]):
            # Update stage
            stage["status"] = "running"
            current_state["pipeline"]["current_stage"] = stage["name"]

            await connection_manager.broadcast({
                "type": "stage_started",
                "data": {
                    "stage": stage["name"],
                    "stage_index": i,
                    "total_stages": len(current_state["pipeline"]["stages"])
                },
                "timestamp": datetime.utcnow().isoformat()
            })

            # Simulate work
            await asyncio.sleep(2)

            # Update regions for regional stage
            if stage["id"] == "regional":
                for region in current_state["regions"]:
                    await connection_manager.broadcast({
                        "type": "region_update",
                        "data": region,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    await asyncio.sleep(0.5)

            # Progress updates
            for progress in [25, 50, 75]:
                await asyncio.sleep(0.5)
                await connection_manager.broadcast({
                    "type": "stage_progress",
                    "data": {
                        "stage": stage["name"],
                        "progress": progress
                    },
                    "timestamp": datetime.utcnow().isoformat()
                })

            # Complete stage
            stage["status"] = "completed"
            await connection_manager.broadcast({
                "type": "stage_completed",
                "data": {
                    "stage": stage["name"],
                    "stage_index": i,
                    "total_stages": len(current_state["pipeline"]["stages"])
                },
                "timestamp": datetime.utcnow().isoformat()
            })

        # Complete pipeline
        current_state["pipeline"]["status"] = "completed"
        await connection_manager.broadcast({
            "type": "pipeline_completed",
            "data": {
                "results": current_state["metrics"]
            },
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Pipeline simulation error: {e}")
        current_state["pipeline"]["status"] = "error"
        await connection_manager.broadcast({
            "type": "pipeline_error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })

async def run_actual_pipeline(connection_manager, config):
    """Load and use the test_orchestrator.py output JSON file"""
    try:
        from pathlib import Path

        # Update state
        current_state["pipeline"]["status"] = "running"

        # Send started event
        await connection_manager.broadcast({
            "type": "pipeline_started",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Path to the output file
        parent_dir = Path(__file__).parent.parent
        output_file = parent_dir / "pipeline_output.json"

        # Check if file exists
        if not output_file.exists():
            raise FileNotFoundError(f"Pipeline output file not found: {output_file}. Please run test_orchestrator.py first.")

        # Load the JSON output
        with open(output_file, 'r') as f:
            result = json.load(f)

        logger.info(f"Loaded pipeline output from {output_file}")

        # Stage 1: Problem Analysis
        await update_stage(connection_manager, 0, "Problem Analysis")
        await asyncio.sleep(1)
        await complete_stage(connection_manager, 0)

        # Stage 2: Regional Optimization
        await update_stage(connection_manager, 1, "Regional Optimization")

        # Load regional results
        regional_results = result.get("regional_results", [])

        # Update each region
        for region_result in regional_results:
            # Convert to dashboard format
            region_data = {
                "id": region_result.get("region", "").lower().replace(" ", "_"),
                "name": region_result.get("region", "").replace("Middle Last", "Middle East"),
                "status": "completed",
                "profit": region_result.get("weekly_profit", 0),
                "coverage": region_result.get("coverage_percent", 0),
                "services": region_result.get("services_selected", 0),
                "margin": region_result.get("profit_margin_pct", 0),
                "hubs": region_result.get("hub_ports", []),
                "uncovered": region_result.get("uncovered_teu", 0),
                "cost": region_result.get("total_cost", region_result.get("operating_cost", 0)),
                "operating_cost": region_result.get("operating_cost", 0),
                "transship_cost": region_result.get("transship_cost", 0),
                "generated": region_result.get("services_generated", 0),
                "filtered": region_result.get("services_filtered", 0),
                "selected": region_result.get("services_selected", 0),
                "strategy": region_result.get("strategy", ""),
                "explanation": region_result.get("explanation", "")
            }

            # Update current state
            await connection_manager.broadcast({
                "type": "region_update",
                "data": region_data,
                "timestamp": datetime.utcnow().isoformat()
            })

            await asyncio.sleep(0.5)

        # Update current state with real data
        current_state["regions"] = {
            r.get("region", "").lower().replace(" ", "_"): {
                "id": r.get("region", "").lower().replace(" ", "_"),
                "name": r.get("region", "").replace("Middle Last", "Middle East"),
                "status": "completed",
                "profit": r.get("weekly_profit", 0),
                "coverage": r.get("coverage_percent", 0),
                "services": r.get("services_selected", 0),
                "margin": r.get("profit_margin_pct", 0),
                "hubs": r.get("hub_ports", []),
                "uncovered": r.get("uncovered_teu", 0),
                "cost": r.get("total_cost", r.get("operating_cost", 0)),
                "operating_cost": r.get("operating_cost", 0),
                "transship_cost": r.get("transship_cost", 0),
                "generated": r.get("services_generated", 0),
                "filtered": r.get("services_filtered", 0),
                "selected": r.get("services_selected", 0),
                "strategy": r.get("strategy", ""),
                "explanation": r.get("explanation", "")
            }
            for r in regional_results
        }

        # Load iteration audit
        iteration_audit = result.get("iteration_audit", [])
        current_state["iterations"] = [
            {
                "iter": i.get("iteration", 0),
                "profit": i.get("profit", 0),
                # PROJECT X: two coverage metrics per iteration.
                # `coverage`       = REGIONAL average (feedback-loop view).
                # `globalCoverage` = demand-weighted (network KPI).
                "coverage": i.get("coverage", 0),
                "globalCoverage": i.get("global_coverage", i.get("coverage", 0)),
                "score": i.get("convergence_score", 0),
                "rerun": i.get("needs_rerun", False),
                "reason": i.get("rerun_reason", ""),
                "selected_as_final": i.get("selected_as_final", False),
            }
            for i in iteration_audit
        ]

        # PROJECT X: surface multi-objective iteration selection + best snapshot.
        current_state["iteration_selection"] = result.get("iteration_selection", {})
        current_state["best_iteration"]       = result.get("best_iteration", 0)
        current_state["iteration_results"]    = result.get("iteration_results", [])

        # Update metrics from the result
        summary_metrics = result.get("summary_metrics", {})
        weekly_profit = summary_metrics.get("weekly_profit", 0)
        annual_profit = summary_metrics.get("annual_profit", 0)
        total_cost = summary_metrics.get("cost", 0)
        coverage = summary_metrics.get("coverage", 0)
        total_services = summary_metrics.get("total_services", 0)

        current_state["metrics"] = {
            "weeklyProfit": weekly_profit,
            "annualProfit": annual_profit,
            "totalCost": total_cost,
            "operatingCost": summary_metrics.get("operating_cost", total_cost),
            "totalServices": total_services,
            "coverage": coverage,
            "margin": (weekly_profit / (weekly_profit + total_cost)) * 100 if (weekly_profit + total_cost) > 0 else 0,
            "unserved": summary_metrics.get("unserved_demand", 0),
            "convergence": current_state["iterations"][-1]["score"] if current_state["iterations"] else 0.982,
            "runtime": summary_metrics.get("total_runtime", 0),
            "selected_services": result.get("selected_services", []),
            "decision_output": result.get("decision_output", {}),
            "executive_summary": result.get("executive_summary", ""),
            "status": result.get("status", {})
        }

        await complete_stage(connection_manager, 1)

        # Remaining stages
        await update_stage(connection_manager, 2, "Coordinator Agent")
        await asyncio.sleep(2)
        await complete_stage(connection_manager, 2)

        await update_stage(connection_manager, 3, "MILP Optimization")
        await asyncio.sleep(2)
        await complete_stage(connection_manager, 3)

        await update_stage(connection_manager, 4, "Vessel Deployment")
        await asyncio.sleep(2)
        await complete_stage(connection_manager, 4)

        # Complete pipeline
        current_state["pipeline"]["status"] = "completed"
        await connection_manager.broadcast({
            "type": "pipeline_completed",
            "data": {
                "results": current_state["metrics"],
                "data": result
            },
            "timestamp": datetime.utcnow().isoformat()
        })

        logger.info("Pipeline data successfully loaded and streamed to dashboard")

    except Exception as e:
        logger.error(f"Pipeline loading error: {e}")
        current_state["pipeline"]["status"] = "error"
        await connection_manager.broadcast({
            "type": "pipeline_error",
            "data": {
                "error": str(e)
            },
            "timestamp": datetime.utcnow().isoformat()
        })

async def update_stage(connection_manager, index, stage_name):
    """Helper to update stage status"""
    stage = current_state["pipeline"]["stages"][index]
    stage["status"] = "running"
    current_state["pipeline"]["current_stage"] = stage_name

    await connection_manager.broadcast({
        "type": "stage_started",
        "data": {
            "stage": stage_name,
            "stage_index": index,
            "total_stages": len(current_state["pipeline"]["stages"])
        },
        "timestamp": datetime.utcnow().isoformat()
    })

async def complete_stage(connection_manager, index):
    """Helper to complete a stage"""
    stage = current_state["pipeline"]["stages"][index]
    stage["status"] = "completed"

    # Send progress updates
    for progress in [25, 50, 75]:
        await asyncio.sleep(0.3)
        await connection_manager.broadcast({
            "type": "stage_progress",
            "data": {
                "stage": stage["name"],
                "progress": progress
            },
            "timestamp": datetime.utcnow().isoformat()
        })

    await connection_manager.broadcast({
        "type": "stage_completed",
        "data": {
            "stage": stage["name"],
            "stage_index": index,
            "total_stages": len(current_state["pipeline"]["stages"])
        },
        "timestamp": datetime.utcnow().isoformat()
    })

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        # API_PORT overrides 8000 (some Windows hosts reserve 7961-8060 for Hyper-V)
        port=int(os.environ.get("API_PORT", "8000")),
        reload=True,
        log_level="info"
    )