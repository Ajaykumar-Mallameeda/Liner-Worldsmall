"""
WebSocket routes for real-time updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List
import json
import asyncio
import logging
from datetime import datetime

router = APIRouter(prefix="/ws", tags=["websocket"])

logger = logging.getLogger(__name__)

# Store active connections
active_connections: List[WebSocket] = []

async def connect_websocket(websocket: WebSocket):
    """Accept and store WebSocket connection"""
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"WebSocket connected. Total: {len(active_connections)}")

    # Send initial message
    await websocket.send_text(json.dumps({
        "type": "connected",
        "message": "Connected to shipping optimizer WebSocket",
        "timestamp": datetime.utcnow().isoformat()
    }))

def disconnect_websocket(websocket: WebSocket):
    """Remove WebSocket connection"""
    if websocket in active_connections:
        active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(active_connections)}")

async def broadcast_message(message: Dict[str, Any]):
    """Broadcast message to all connected clients"""
    if not active_connections:
        return

    message_str = json.dumps(message)
    disconnected = []

    for connection in active_connections:
        try:
            await connection.send_text(message_str)
        except:
            disconnected.append(connection)

    # Remove disconnected clients
    for conn in disconnected:
        disconnect_websocket(conn)

@router.websocket("/pipeline")
async def websocket_pipeline_endpoint(websocket: WebSocket):
    """WebSocket endpoint for pipeline updates"""
    await connect_websocket(websocket)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle different message types
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }))
            elif message.get("type") == "subscribe":
                # Handle subscription to specific events
                await handle_subscription(websocket, message.get("events", []))
            elif message.get("type") == "start_pipeline":
                # Trigger pipeline start
                await handle_pipeline_start(websocket, message.get("config", {}))

    except WebSocketDisconnect:
        disconnect_websocket(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        disconnect_websocket(websocket)

async def handle_subscription(websocket: WebSocket, events: List[str]):
    """Handle client subscription to specific events"""
    await websocket.send_text(json.dumps({
        "type": "subscription_confirmed",
        "events": events,
        "timestamp": datetime.utcnow().isoformat()
    }))

async def handle_pipeline_start(websocket: WebSocket, config: Dict[str, Any]):
    """Handle pipeline start request"""
    # Send pipeline started event
    await broadcast_message({
        "type": "pipeline_started",
        "config": config,
        "timestamp": datetime.utcnow().isoformat()
    })

    # Simulate pipeline execution with real-time updates
    await simulate_pipeline_with_updates()

async def simulate_pipeline_with_updates():
    """Simulate pipeline execution and send updates"""
    stages = [
        {"name": "Problem Analysis", "duration": 2},
        {"name": "Regional Optimization", "duration": 5},
        {"name": "Coordinator Agent", "duration": 3},
        {"name": "MILP Optimization", "duration": 4},
        {"name": "Vessel Deployment", "duration": 2}
    ]

    for i, stage in enumerate(stages):
        # Stage started
        await broadcast_message({
            "type": "stage_started",
            "stage": stage["name"],
            "stage_index": i,
            "total_stages": len(stages),
            "timestamp": datetime.utcnow().isoformat()
        })

        # Simulate work
        await asyncio.sleep(stage["duration"])

        # Stage completed
        await broadcast_message({
            "type": "stage_completed",
            "stage": stage["name"],
            "stage_index": i,
            "total_stages": len(stages),
            "timestamp": datetime.utcnow().isoformat()
        })

        # Send progress updates during long stages
        if stage["duration"] > 3:
            for progress in [25, 50, 75]:
                await asyncio.sleep(stage["duration"] / 4)
                await broadcast_message({
                    "type": "stage_progress",
                    "stage": stage["name"],
                    "progress": progress,
                    "timestamp": datetime.utcnow().isoformat()
                })

    # Pipeline completed
    await broadcast_message({
        "type": "pipeline_completed",
        "timestamp": datetime.utcnow().isoformat(),
        "results": {
            "total_profit": 773616415,
            "total_services": 465,
            "coverage": 59.5
        }
    })