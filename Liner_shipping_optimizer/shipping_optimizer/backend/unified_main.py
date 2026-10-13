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
from src.agents.orchestrator_agent import OrchestratorAgent
from src.data.network_loader import NetworkLoader

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

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return

        message_str = json.dumps(message)
        disconnected = []

        async with self._lock:
            for connection in self.active_connections:
                try:
                    await connection.send_text(message_str)
                except Exception as e:
                    logger.error(f"Error sending to client: {e}")
                    disconnected.append(connection)

        # Remove disconnected clients
        for conn in disconnected:
            await self.disconnect(conn)

    async def send_personal(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send message to specific client"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

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

        await self.ws_manager.broadcast({
            "type": "pipeline_started",
            "data": {
                "run_id": self.current_run_id,
                "timestamp": datetime.now().isoformat(),
                "config": config
            }
        })

    async def on_stage_start(self, stage_name: str, stage_data: Dict[str, Any]):
        """Called when a pipeline stage starts"""
        await self.ws_manager.broadcast({
            "type": "stage_started",
            "data": {
                "stage": stage_name,
                "stage_data": stage_data,
                "timestamp": datetime.now().isoformat()
            }
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

        await self.ws_manager.broadcast({
            "type": "region_updated",
            "data": {
                "region_id": region_id,
                "region_data": region_data,
                "timestamp": datetime.now().isoformat()
            }
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

        await self.ws_manager.broadcast({
            "type": "iteration_updated",
            "data": {
                "iteration": iteration,
                "iteration_data": iteration_data,
                "timestamp": datetime.now().isoformat()
            }
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

        await self.ws_manager.broadcast({
            "type": "map_updated",
            "data": {
                "corridors": corridors,
                "timestamp": datetime.now().isoformat()
            }
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

        await self.ws_manager.broadcast({
            "type": "pipeline_completed",
            "data": {
                "run_id": self.current_run_id,
                "results": results,
                "timestamp": datetime.now().isoformat()
            }
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

        await self.ws_manager.broadcast({
            "type": "pipeline_error",
            "data": {
                "error": error,
                "context": context or {},
                "timestamp": datetime.now().isoformat()
            }
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
    callbacks = OrchestratorCallbacks(websocket_manager)

    try:
        # Notify start
        await callbacks.on_pipeline_start(config)

        # Update state
        current_run_state.update({
            "status": "running",
            "run_id": callbacks.current_run_id,
            "start_time": datetime.now().isoformat(),
            "config": config
        })

        # Load problem data
        await callbacks.on_stage_start("problem_loading", {})

        loader = NetworkLoader()
        dataset_path = config.get("dataset_path", "data/liner_shipping_dataset.csv")

        try:
            problem = loader.load_problem(dataset_path)
            await callbacks.on_stage_start("problem_analysis", {
                "ports": len(problem.ports),
                "lanes": len(problem.lanes),
                "demand": problem.demand.sum()
            })
        except Exception as e:
            await callbacks.on_error(f"Failed to load problem: {str(e)}")
            return

        # Initialize orchestrator
        await callbacks.on_stage_start("orchestrator_init", {})
        orchestrator = OrchestratorAgent()

        # Run optimization with streaming
        start_time = datetime.now()

        # Mock streaming for now (to be replaced with actual streaming implementation)
        # This would be integrated into the orchestrator itself
        await asyncio.sleep(1)

        # Load results from existing JSON for now (temporary)
        parent_dir = Path(__file__).parent.parent
        output_file = parent_dir / "pipeline_output.json"

        if output_file.exists():
            with open(output_file, 'r') as f:
                result = json.load(f)

            # Stream regional results
            regional_results = result.get("regional_results", [])
            for region_result in regional_results:
                await callbacks.on_region_update(
                    region_result.get("region", "").lower(),
                    {
                        "profit": region_result.get("weekly_profit", 0),
                        "coverage": region_result.get("coverage_percent", 0),
                        "services": region_result.get("services_selected", 0),
                        "cost": region_result.get("operating_cost", 0),
                        "margin": region_result.get("profit_margin_pct", 0),
                        "uncovered": region_result.get("uncovered_teu", 0),
                        "hubs": region_result.get("hub_ports", [])
                    }
                )
                await asyncio.sleep(0.5)

            # Stream iterations
            iterations = result.get("iterations", [])
            for i, it in enumerate(iterations):
                await callbacks.on_iteration_complete(i, it)
                await asyncio.sleep(0.3)

            # Stream map data
            corridors = result.get("top_corridors", [])
            if corridors:
                map_corridors = []
                for c in corridors[:10]:  # Top 10 corridors
                    map_corridors.append({
                        "from": f"Port {c.get('from_port', '')}",
                        "to": f"Port {c.get('to_port', '')}",
                        "teu": c.get("teu_flow", 0),
                        "region": c.get("region", "").lower()
                    })
                await callbacks.on_map_update(map_corridors)

            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()

            # Final results
            summary_metrics = result.get("summary_metrics", {})
            # summary_metrics has no ``profit_margin_pct`` key (the old lookup always
            # returned 0). Margin on revenue = profit / (profit + all-in cost), the same
            # figure backend/server.py and network_ledger.weekly_usd report.
            _wp = summary_metrics.get("weekly_profit", 0) or 0
            _tc = summary_metrics.get("total_cost", summary_metrics.get("cost", 0)) or 0
            await callbacks.on_pipeline_complete({
                "metrics": {
                    "weeklyProfit": summary_metrics.get("weekly_profit", 0),
                    "annualProfit": summary_metrics.get("annual_profit", 0),
                    "coverage": summary_metrics.get("coverage", 0),
                    "totalServices": summary_metrics.get("total_services", 0),
                    "margin": (_wp / (_wp + _tc) * 100) if (_wp + _tc) > 0 else 0,
                    "operatingCost": summary_metrics.get("cost", 0),
                    "unserved": result.get("global_stats", {}).get("unserved_teu", 0)
                },
                "duration": duration
            })

            # Update current state
            current_run_state.update({
                "status": "completed",
                "metrics": result.get("summary_metrics", {}),
                "regions": {r.get("region", "").lower(): r for r in regional_results},
                "iterations": iterations,
                "corridors": map_corridors
            })

        else:
            await callbacks.on_error("No pipeline output found. Run test_orchestrator.py first.")

    except Exception as e:
        logger.error(f"Optimization error: {e}")
        await callbacks.on_error(str(e))
        current_run_state["status"] = "error"

# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time updates"""
    await websocket_manager.connect(websocket)

    try:
        # Send initial state
        await websocket_manager.send_personal(websocket, {
            "type": "initial_state",
            "data": current_run_state
        })

        # Handle messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            msg_type = message.get("type")

            if msg_type == "start_pipeline":
                config = message.get("data", {})
                await run_real_optimization(config)

            elif msg_type == "ping":
                await websocket_manager.send_personal(websocket, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })

            elif msg_type == "get_status":
                await websocket_manager.send_personal(websocket, {
                    "type": "status_update",
                    "data": current_run_state
                })

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