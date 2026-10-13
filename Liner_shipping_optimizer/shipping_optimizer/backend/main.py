"""
Unified FastAPI Backend Server for Real-time Maritime Dashboard
Consolidates main.py and server.py into a single production-ready server
"""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Import orchestrator for real optimization
import sys
sys.path.append(str(Path(__file__).parent.parent))

# Import real orchestrator integration
from real_orchestrator_integration import RealOrchestratorIntegration

# Import event validation
from event_validator import EventValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE SETUP
# ============================================================================

def init_db():
    """Initialize SQLite database for persistence"""
    conn = sqlite3.connect('optimization_results.db')
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS optimization_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            config TEXT,
            metrics TEXT,
            duration REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regional_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            region TEXT NOT NULL,
            profit REAL,
            coverage REAL,
            services INTEGER,
            cost REAL,
            FOREIGN KEY (run_id) REFERENCES optimization_runs (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS iterations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            iteration INTEGER,
            profit REAL,
            coverage REAL,
            score REAL,
            reason TEXT,
            FOREIGN KEY (run_id) REFERENCES optimization_runs (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS corridors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            from_port TEXT,
            to_port TEXT,
            teu INTEGER,
            region TEXT,
            FOREIGN KEY (run_id) REFERENCES optimization_runs (id)
        )
    ''')

    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# ============================================================================
# WEBSOCKET MANAGER
# ============================================================================

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """Broadcast validated event to all connected clients"""
        if not self.active_connections:
            return

        try:
            # Create and validate event
            event = EventValidator.create_event(event_type, data)
            message = EventValidator.to_json(event)

            disconnected = []

            async with self._lock:
                for connection in self.active_connections:
                    try:
                        await connection.send_text(message)
                    except Exception as e:
                        logger.error(f"Error sending to client: {e}")
                        disconnected.append(connection)

            # Remove disconnected clients
            for conn in disconnected:
                await self.disconnect(conn)

        except Exception as e:
            logger.error(f"Failed to broadcast event: {e}")

    async def send_personal(self, websocket: WebSocket, event_type: str, data: Optional[Dict[str, Any]] = None):
        """Send validated event to specific client"""
        try:
            # Create and validate event
            event = EventValidator.create_event(event_type, data)
            message = EventValidator.to_json(event)
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    # Legacy methods for backward compatibility
    async def broadcast_dict(self, message: Dict[str, Any]):
        """Legacy method - use broadcast with event types instead"""
        event_type = message.get("type", "unknown")
        await self.broadcast(event_type, message.get("data", {}))

# ============================================================================
# ORCHESTRATOR CALLBACK SYSTEM
# ============================================================================

class OrchestratorCallbacks:
    """Callback system for streaming orchestrator events"""

    def __init__(self, websocket_manager: WebSocketManager):
        self.ws_manager = websocket_manager
        self.current_run_id = None

    async def on_pipeline_start(self, config: Dict[str, Any]):
        """Called when pipeline starts"""
        # Save to database
        conn = sqlite3.connect('optimization_results.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO optimization_runs (timestamp, status, config)
            VALUES (?, ?, ?)
        ''', (datetime.now().isoformat(), 'running', json.dumps(config)))
        self.current_run_id = cursor.lastrowid
        conn.commit()
        conn.close()

        await self.ws_manager.broadcast("pipeline_started", {
            "run_id": self.current_run_id,
            "timestamp": datetime.now().isoformat(),
            "config": config
        })

    async def on_stage_start(self, stage_name: str, stage_data: Dict[str, Any]):
        """Called when a pipeline stage starts"""
        await self.ws_manager.broadcast("stage_started", {
            "stage": stage_name,
            "stage_data": stage_data,
            "timestamp": datetime.now().isoformat()
        })

    async def on_region_update(self, region_id: str, region_data: Dict[str, Any]):
        """Called when region agent completes"""
        # Save to database
        if self.current_run_id:
            conn = sqlite3.connect('optimization_results.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO regional_results (run_id, region, profit, coverage, services, cost)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                self.current_run_id,
                region_id,
                region_data.get('profit', 0),
                region_data.get('coverage', 0),
                region_data.get('services', 0),
                region_data.get('cost', 0)
            ))
            conn.commit()
            conn.close()

        await self.ws_manager.broadcast("region_updated", {
            "region_id": region_id,
            "region_data": region_data,
            "timestamp": datetime.now().isoformat()
        })

    async def on_iteration_complete(self, iteration: int, iteration_data: Dict[str, Any]):
        """Called when an iteration completes"""
        # Save to database
        if self.current_run_id:
            conn = sqlite3.connect('optimization_results.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO iterations (run_id, iteration, profit, coverage, score, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                self.current_run_id,
                iteration,
                iteration_data.get('profit', 0),
                iteration_data.get('coverage', 0),
                iteration_data.get('score', 0),
                iteration_data.get('reason', '')
            ))
            conn.commit()
            conn.close()

        await self.ws_manager.broadcast("iteration_completed", {
            "iteration": iteration,
            "iteration_data": iteration_data,
            "timestamp": datetime.now().isoformat()
        })

    async def on_map_update(self, corridors: List[Dict[str, Any]]):
        """Called when map data is ready"""
        # Save to database
        if self.current_run_id:
            conn = sqlite3.connect('optimization_results.db')
            cursor = conn.cursor()
            for corridor in corridors:
                cursor.execute('''
                    INSERT INTO corridors (run_id, from_port, to_port, teu, region)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    self.current_run_id,
                    corridor.get('from'),
                    corridor.get('to'),
                    corridor.get('teu', 0),
                    corridor.get('region', '')
                ))
            conn.commit()
            conn.close()

        await self.ws_manager.broadcast("map_updated", {
            "corridors": corridors,
            "timestamp": datetime.now().isoformat()
        })

    async def on_pipeline_complete(self, results: Dict[str, Any]):
        """Called when pipeline completes"""
        # Update database
        if self.current_run_id:
            conn = sqlite3.connect('optimization_results.db')
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE optimization_runs
                SET status = ?, metrics = ?, duration = ?
                WHERE id = ?
            ''', (
                'completed',
                json.dumps(results.get('metrics', {})),
                results.get('duration', 0),
                self.current_run_id
            ))
            conn.commit()
            conn.close()

        await self.ws_manager.broadcast("pipeline_completed", {
            "run_id": self.current_run_id,
            "results": results,
            "timestamp": datetime.now().isoformat()
        })

    async def on_error(self, error: str, context: Dict[str, Any] = None):
        """Called when an error occurs"""
        # Update database
        if self.current_run_id:
            conn = sqlite3.connect('optimization_results.db')
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE optimization_runs
                SET status = ?
                WHERE id = ?
            ''', ('error', self.current_run_id))
            conn.commit()
            conn.close()

        await self.ws_manager.broadcast("pipeline_error", {
            "error": error,
            "context": context or {},
            "timestamp": datetime.now().isoformat()
        })

# ============================================================================
# GLOBAL STATE
# ============================================================================

# WebSocket manager
websocket_manager = WebSocketManager()

# Store current run state
current_run_state: Dict[str, Any] = {
    "status": "idle",
    "run_id": None,
    "start_time": None,
    "current_iteration": 0,
    "total_iterations": 0,
    "current_stage": None,
    "metrics": {},
    "regions": {},
    "iterations": [],
    "corridors": [],
}

# ============================================================================
# LIFECYCLE MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting unified FastAPI backend...")
    yield
    # Shutdown
    logger.info("Shutting down backend...")
    await websocket_manager.disconnect_all()

# Create FastAPI app
app = FastAPI(
    title="Maritime Optimizer API",
    description="Unified API for liner shipping optimization dashboard",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# PIPELINE EXECUTION
# ============================================================================

async def run_real_optimization(config: Dict[str, Any]):
    """Run the actual optimization pipeline with real-time streaming"""
    # Create real orchestrator integration
    integration = RealOrchestratorIntegration(websocket_manager)

    try:
        # Update state
        current_run_state.update({
            "status": "running",
            "run_id": None,  # Will be set by integration
            "start_time": datetime.now().isoformat(),
            "config": config
        })

        # Run the real optimization
        await integration.run_optimization(config)

        # Update final state
        current_run_state["status"] = "completed"

    except Exception as e:
        logger.error(f"Optimization error: {e}")
        current_run_state["status"] = "error"

        # Broadcast error
        await websocket_manager.broadcast("pipeline_error", {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })

# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time updates"""
    await websocket_manager.connect(websocket)

    try:
        # Send initial state using event validator
        initial_event = EventValidator.create_event("initial_state", current_run_state)
        await websocket_manager.send_personal(websocket, EventValidator.to_json(initial_event))

        # Handle messages
        while True:
            try:
                # Receive and validate message
                data = await websocket.receive_text()
                event = EventValidator.validate_incoming(data)

                # Handle event based on type
                if event.type == "start_pipeline":
                    config = event.data
                    await run_real_optimization(config)

                elif event.type == "ping":
                    pong_event = EventValidator.create_event("pong", {
                        "timestamp": datetime.now().isoformat()
                    })
                    await websocket_manager.send_personal(websocket, EventValidator.to_json(pong_event))

                elif event.type == "get_status":
                    status_event = EventValidator.create_event("status_update", current_run_state)
                    await websocket_manager.send_personal(websocket, EventValidator.to_json(status_event))

                elif event.type == "stop_pipeline":
                    # Handle stop request
                    current_run_state["status"] = "stopping"
                    await websocket_manager.broadcast("pipeline_stopped", {
                        "reason": "User requested stop"
                    })

            except ValueError as e:
                # Send error response for invalid events
                error_event = EventValidator.create_event("pipeline_error", {
                    "error": str(e),
                    "context": {"event_type": event.type if 'event' in locals() else "unknown"}
                })
                await websocket_manager.send_personal(websocket, EventValidator.to_json(error_event))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket_manager.disconnect(websocket)

# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "connected_clients": len(websocket_manager.active_connections),
        "current_run": current_run_state.get("run_id"),
        "pipeline_status": current_run_state.get("status")
    }

@app.get("/api/status")
async def get_status():
    """Get current pipeline status"""
    return {
        "status": current_run_state["status"],
        "run_id": current_run_state.get("run_id"),
        "current_stage": current_run_state.get("current_stage"),
        "current_iteration": current_run_state.get("current_iteration"),
        "start_time": current_run_state.get("start_time")
    }

@app.get("/api/metrics")
async def get_metrics():
    """Get global optimization metrics"""
    return current_run_state.get("metrics", {})

@app.get("/api/regions")
async def get_regions():
    """Get regional agent results"""
    return list(current_run_state.get("regions", {}).values())

@app.get("/api/iterations")
async def get_iterations():
    """Get iteration history"""
    return current_run_state.get("iterations", [])

@app.get("/api/corridors")
async def get_corridors():
    """Get maritime corridors for map visualization"""
    return current_run_state.get("corridors", [])

@app.get("/api/history")
async def get_history():
    """Get optimization history from database"""
    conn = sqlite3.connect('optimization_results.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM optimization_runs
        ORDER BY timestamp DESC
        LIMIT 10
    ''')

    runs = [dict(row) for row in cursor.fetchall()]

    # Get regional results for each run
    for run in runs:
        cursor.execute('''
            SELECT * FROM regional_results
            WHERE run_id = ?
        ''', (run['id'],))
        run['regions'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {"runs": runs}

@app.delete("/api/reset")
async def reset_state():
    """Reset current state (for testing)"""
    global current_run_state
    current_run_state = {
        "status": "idle",
        "run_id": None,
        "start_time": None,
        "current_iteration": 0,
        "total_iterations": 0,
        "current_stage": None,
        "metrics": {},
        "regions": {},
        "iterations": [],
        "corridors": [],
    }

    await websocket_manager.broadcast({
        "type": "state_reset",
        "data": current_run_state
    })

    return {"status": "reset"}

# ============================================================================
# SERVE STATIC FILES
# ============================================================================

# Mount static files for React app (if built)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_frontend():
    """Serve the React application or fallback"""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)

    # Fallback response if no frontend built
    return {
        "message": "Maritime Optimizer API Server",
        "status": "running",
        "websocket_endpoint": "ws://localhost:8000/ws",
        "api_docs": "/docs"
    }

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "backend.unified_main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )