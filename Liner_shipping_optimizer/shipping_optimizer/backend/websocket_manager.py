"""
WebSocket connection manager for real-time dashboard updates
"""

import json
import logging
from typing import List, Dict, Any, Set
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connections and broadcasting"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        self.message_queue: List[Dict[str, Any]] = []
        self.max_queue_size = 100

    async def connect(self, websocket: WebSocket):
        """Accept and track new WebSocket connection"""
        await websocket.accept()

        # Add to active connections
        self.active_connections.add(websocket)

        # Store metadata
        self.connection_metadata[websocket] = {
            "connected_at": datetime.now().isoformat(),
            "client_id": f"client_{len(self.active_connections)}",
            "last_ping": datetime.now().isoformat()
        }

        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            del self.connection_metadata[websocket]
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def disconnect_all(self):
        """Disconnect all clients"""
        for connection in list(self.active_connections):
            try:
                await connection.close()
                await self.disconnect(connection)
            except:
                pass

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send message to specific WebSocket"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            await self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return

        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.now().isoformat()

        # Add to message queue
        self.message_queue.append(message)
        if len(self.message_queue) > self.max_queue_size:
            self.message_queue.pop(0)

        # Send to all connections
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to connection: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            await self.disconnect(conn)

    async def broadcast_with_filter(self, message: Dict[str, Any], filter_func):
        """Broadcast to connections matching filter function"""
        for connection in self.active_connections:
            metadata = self.connection_metadata.get(connection, {})
            if filter_func(metadata):
                await self.send_personal_message(message, connection)

    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)

    def get_connection_metadata(self, websocket: WebSocket) -> Dict[str, Any]:
        """Get metadata for specific connection"""
        return self.connection_metadata.get(websocket, {})

    def get_recent_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent messages from queue"""
        return self.message_queue[-limit:]

    async def ping_all(self):
        """Send ping to all connections to check health"""
        ping_message = {
            "type": "ping",
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(ping_message)