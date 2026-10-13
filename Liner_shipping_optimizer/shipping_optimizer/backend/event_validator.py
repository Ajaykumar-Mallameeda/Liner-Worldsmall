"""
WebSocket Event Validator
Validates incoming and outgoing WebSocket events
"""

import json
import logging
from typing import Dict, Any, Optional, Union
from event_schemas import (
    validate_event,
    is_client_event,
    is_server_event,
    BaseEvent
)

logger = logging.getLogger(__name__)

class EventValidator:
    """Validates WebSocket events"""

    @staticmethod
    def validate_incoming(message: Union[str, bytes]) -> BaseEvent:
        """Validate incoming client message"""
        try:
            # Parse JSON
            data = json.loads(message) if isinstance(message, str) else json.loads(message.decode())
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message: {e}")
            raise ValueError("Invalid JSON format")

        # Get event type
        event_type = data.get("type")
        if not event_type:
            raise ValueError("Missing event type")

        # Check if it's a valid client event
        if not is_client_event(event_type):
            logger.warning(f"Client sent invalid event type: {event_type}")
            raise ValueError(f"Invalid client event: {event_type}")

        # Validate against schema
        try:
            event = validate_event(event_type, data.get("data", {}))
            return event
        except Exception as e:
            logger.error(f"Event validation failed: {e}")
            raise ValueError(f"Event validation failed: {e}")

    @staticmethod
    def create_event(event_type: str, data: Optional[Dict[str, Any]] = None) -> BaseEvent:
        """Create a valid server event"""
        # Check if it's a valid server event
        if not is_server_event(event_type):
            logger.warning(f"Server creating invalid event type: {event_type}")
            raise ValueError(f"Invalid server event: {event_type}")

        # Create and validate event
        try:
            event = validate_event(event_type, data or {})
            return event
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            raise ValueError(f"Failed to create event: {e}")

    @staticmethod
    def to_json(event: BaseEvent) -> str:
        """Convert event to JSON string"""
        try:
            return json.dumps({
                "type": event.type,
                "timestamp": event.timestamp,
                "data": event.data
            })
        except Exception as e:
            logger.error(f"Failed to serialize event: {e}")
            raise ValueError(f"Failed to serialize event: {e}")

    @staticmethod
    def safe_extract(data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Safely extract value from event data"""
        if not isinstance(data, dict):
            return default
        return data.get(key, default)