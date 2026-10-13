"""
FastAPI Backend Server for Real-time Maritime Dashboard
Provides WebSocket streaming and REST API endpoints
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from websocket_manager import WebSocketManager
from pipeline_streamer import PipelineStreamer
from models.schemas import (
    PipelineStatus,
    RegionData,
    IterationData,
    GlobalMetrics,
    WebSocketMessage,
    MapCorridor,
    MapUpdate,
    PipelineEvent,
    ProblemStats
)
from services.pipeline_service import PipelineService
from services.optimization_service import OptimizationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global WebSocket manager
websocket_manager = WebSocketManager()
pipeline_streamer = PipelineStreamer(websocket_manager)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting FastAPI backend...")
    # Initialize any background tasks here
    yield
    # Shutdown
    logger.info("Shutting down FastAPI backend...")
    await websocket_manager.disconnect_all()

# Create FastAPI app
app = FastAPI(
    title="Maritime Optimizer API",
    description="Real-time API for liner shipping optimization dashboard",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (React build)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize services
pipeline_service = PipelineService()
optimization_service = OptimizationService()

# Store current run state
current_run_state: Dict[str, Any] = {
    "status": "idle",
    "start_time": None,
    "current_iteration": 0,
    "total_iterations": 0,
    "metrics": {},
    "regions": {},
    "iterations": [],
    "corridors": [],
}

# ============================================================================
# WebSocket Endpoints
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time updates"""
    await websocket_manager.connect(websocket)

    try:
        # Send initial state
        await websocket.send_json({
            "type": "initial_state",
            "data": current_run_state
        })

        # Handle messages from client
        while True:
            data = await websocket.receive_json()
            message = WebSocketMessage(**data)

            if message.type == "start_pipeline":
                await handle_start_pipeline(websocket, message.data)
            elif message.type == "stop_pipeline":
                await handle_stop_pipeline(websocket, message.data)
            elif message.type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        await websocket_manager.disconnect(websocket)

async def handle_start_pipeline(websocket: WebSocket, config: Dict[str, Any]):
    """Start optimization pipeline with streaming updates"""
    global current_run_state

    try:
        # Update state
        current_run_state.update({
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "config": config,
            "current_iteration": 0,
            "total_iterations": config.get("max_iterations", 3)
        })

        # Notify all clients
        await websocket_manager.broadcast({
            "type": "pipeline_started",
            "data": {
                "status": current_run_state["status"],
                "start_time": current_run_state["start_time"],
                "config": config
            }
        })

        # Run pipeline with streaming
        await pipeline_streamer.stream_pipeline_run(
            websocket_manager,
            config,
            current_run_state
        )

        # Mark as complete
        current_run_state["status"] = "complete"
        await websocket_manager.broadcast({
            "type": "pipeline_complete",
            "data": {
                "status": current_run_state["status"],
                "final_metrics": current_run_state["metrics"],
                "end_time": datetime.now().isoformat()
            }
        })

    except Exception as e:
        logger.error(f"Pipeline run error: {e}")
        current_run_state["status"] = "error"
        current_run_state["error"] = str(e)

        await websocket_manager.broadcast({
            "type": "pipeline_error",
            "data": {
                "error": str(e),
                "status": current_run_state["status"]
            }
        })

async def handle_stop_pipeline(websocket: WebSocket, data: Dict[str, Any]):
    """Stop running pipeline"""
    global current_run_state

    if current_run_state["status"] == "running":
        current_run_state["status"] = "stopped"

        await websocket_manager.broadcast({
            "type": "pipeline_stopped",
            "data": {
                "status": current_run_state["status"],
                "stop_time": datetime.now().isoformat()
            }
        })

# ============================================================================
# REST API Endpoints
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "connected_clients": len(websocket_manager.active_connections)
    }

@app.get("/api/status")
async def get_status():
    """Get current pipeline status"""
    return current_run_state

@app.get("/api/problem-stats")
async def get_problem_stats() -> ProblemStats:
    """Get problem statistics"""
    try:
        stats = await pipeline_service.get_problem_statistics()
        return ProblemStats(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/regions")
async def get_regions() -> List[RegionData]:
    """Get regional agent results"""
    regions = current_run_state.get("regions", {})
    return [RegionData(**r) for r in regions.values()]

@app.get("/api/metrics")
async def get_metrics() -> GlobalMetrics:
    """Get global optimization metrics"""
    metrics = current_run_state.get("metrics", {})
    return GlobalMetrics(**metrics)

@app.get("/api/iterations")
async def get_iterations() -> List[IterationData]:
    """Get iteration history"""
    iterations = current_run_state.get("iterations", [])
    return [IterationData(**it) for it in iterations]

@app.get("/api/corridors")
async def get_corridors() -> List[MapCorridor]:
    """Get maritime corridors for map visualization"""
    corridors = current_run_state.get("corridors", [])
    return [MapCorridor(**c) for c in corridors]

@app.get("/api/export")
async def export_results():
    """Export full results as JSON"""
    return {
        "run_state": current_run_state,
        "export_timestamp": datetime.now().isoformat()
    }

@app.post("/api/optimize")
async def trigger_optimization(config: Dict[str, Any]):
    """Trigger optimization in background"""
    # This would trigger the pipeline without WebSocket updates
    try:
        results = await optimization_service.run_optimization(config)
        return {
            "status": "completed",
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Serve React App
# ============================================================================

@app.get("/")
async def serve_react_app():
    """Serve the React application"""
    return FileResponse("static/index.html")

# ============================================================================
# Event Handlers
# ============================================================================

@pipeline_streamer.on_problem_analyzed
async def on_problem_analyzed(event: PipelineEvent):
    """Handle problem analysis event"""
    await websocket_manager.broadcast({
        "type": "problem_analyzed",
        "data": event.data
    })

@pipeline_streamer.on_region_started
async def on_region_started(event: PipelineEvent):
    """Handle region agent started event"""
    region_id = event.data["region_id"]

    # Initialize region data
    if region_id not in current_run_state["regions"]:
        current_run_state["regions"][region_id] = {
            "id": region_id,
            "status": "running",
            "services_generated": 0,
            "services_filtered": 0,
            "services_selected": 0,
            "profit": 0,
            "coverage": 0,
            "cost": 0
        }

    await websocket_manager.broadcast({
        "type": "region_started",
        "data": {
            "region_id": region_id,
            "timestamp": event.timestamp
        }
    })

@pipeline_streamer.on_iteration_complete
async def on_iteration_complete(event: PipelineEvent):
    """Handle iteration complete event"""
    iteration_data = event.data
    current_run_state["current_iteration"] = iteration_data["iteration"]
    current_run_state["iterations"].append(iteration_data)

    await websocket_manager.broadcast({
        "type": "iteration_complete",
        "data": iteration_data
    })

@pipeline_streamer.on_map_update
async def on_map_update(event: PipelineEvent):
    """Handle map visualization update"""
    map_data = event.data
    current_run_state["corridors"] = map_data.get("corridors", [])

    await websocket_manager.broadcast({
        "type": "map_update",
        "data": map_data
    })

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )