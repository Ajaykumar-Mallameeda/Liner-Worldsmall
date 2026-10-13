"""
Standardized WebSocket Event Schemas
Defines all event types and their payload structures
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# ============================================================================
# BASE EVENT MODEL
# ============================================================================

class BaseEvent(BaseModel):
    """Base WebSocket event model"""
    type: str = Field(..., description="Event type identifier")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    data: Dict[str, Any] = Field(default_factory=dict, description="Event payload")

# ============================================================================
# PIPELINE EVENTS
# ============================================================================

class PipelineStartedEvent(BaseEvent):
    """Pipeline execution started"""
    type: Literal["pipeline_started"] = "pipeline_started"
    data: Dict[str, Any] = Field(..., description={
        "run_id": "Optional run identifier",
        "config": "Optimization configuration",
        "message": "Optional start message"
    })

class PipelineCompletedEvent(BaseEvent):
    """Pipeline execution completed"""
    type: Literal["pipeline_completed"] = "pipeline_completed"
    data: Dict[str, Any] = Field(..., description={
        "run_id": "Run identifier",
        "results": "Final optimization results",
        "duration": "Total runtime in seconds",
        "iterations": "Iteration history"
    })

class PipelineErrorEvent(BaseEvent):
    """Pipeline execution error"""
    type: Literal["pipeline_error"] = "pipeline_error"
    data: Dict[str, Any] = Field(..., description={
        "error": "Error message",
        "context": "Additional error context",
        "stage": "Stage where error occurred"
    })

class PipelineStoppedEvent(BaseEvent):
    """Pipeline execution stopped"""
    type: Literal["pipeline_stopped"] = "pipeline_stopped"
    data: Dict[str, Any] = Field(..., description={
        "reason": "Stop reason",
        "partial_results": "Any results computed before stop"
    })

# ============================================================================
# STAGE EVENTS
# ============================================================================

class StageStartedEvent(BaseEvent):
    """Pipeline stage started"""
    type: Literal["stage_started"] = "stage_started"
    data: Dict[str, Any] = Field(..., description={
        "stage": "Stage name",
        "stage_id": "Stage identifier",
        "metadata": "Stage-specific metadata",
        "total_stages": "Total number of stages",
        "stage_index": "Current stage index"
    })

class StageProgressEvent(BaseEvent):
    """Pipeline stage progress update"""
    type: Literal["stage_progress"] = "stage_progress"
    data: Dict[str, Any] = Field(..., description={
        "stage": "Stage name",
        "stage_id": "Stage identifier",
        "progress": "Progress percentage (0-100)",
        "message": "Progress message"
    })

class StageCompletedEvent(BaseEvent):
    """Pipeline stage completed"""
    type: Literal["stage_completed"] = "stage_completed"
    data: Dict[str, Any] = Field(..., description={
        "stage": "Stage name",
        "stage_id": "Stage identifier",
        "results": "Stage results",
        "duration": "Stage duration"
    })

# ============================================================================
# REGION EVENTS
# ============================================================================

class RegionUpdatedEvent(BaseEvent):
    """Region agent updated"""
    type: Literal["region_updated"] = "region_updated"
    data: Dict[str, Any] = Field(..., description={
        "region_id": "Region identifier",
        "region_data": {
            "name": "Region display name",
            "profit": "Weekly profit",
            "coverage": "Demand coverage percentage",
            "services": "Number of services",
            "margin": "Profit margin",
            "cost": "Operating cost",
            "uncovered": "Uncovered TEU",
            "hubs": "Hub port list"
        }
    })

# ============================================================================
# ITERATION EVENTS
# ============================================================================

class IterationStartedEvent(BaseEvent):
    """Optimization iteration started"""
    type: Literal["iteration_started"] = "iteration_started"
    data: Dict[str, Any] = Field(..., description={
        "iteration": "Iteration number",
        "max_iterations": "Maximum iterations",
        "message": "Iteration message"
    })

class IterationUpdatedEvent(BaseEvent):
    """Optimization iteration updated"""
    type: Literal["iteration_updated"] = "iteration_updated"
    data: Dict[str, Any] = Field(..., description={
        "iteration": "Iteration number",
        "iteration_data": {
            "profit": "Total profit",
            "coverage": "Coverage percentage",
            "score": "Convergence score",
            "rerun": "Whether rerun needed",
            "reason": "Rerun reason",
            "total_services": "Total services",
            "operating_cost": "Operating cost",
            "margin": "Profit margin",
            "regions": "Regional results"
        }
    })

class IterationCompletedEvent(BaseEvent):
    """Optimization iteration completed"""
    type: Literal["iteration_completed"] = "iteration_completed"
    data: Dict[str, Any] = Field(..., description={
        "iteration": "Iteration number",
        "results": "Iteration results",
        "convergence_score": "Convergence score",
        "needs_rerun": "Whether rerun needed",
        "rerun_reason": "Rerun reason"
    })

# ============================================================================
# MAP EVENTS
# ============================================================================

class MapUpdatedEvent(BaseEvent):
    """Map visualization updated"""
    type: Literal["map_updated"] = "map_updated"
    data: Dict[str, Any] = Field(..., description={
        "corridors": [
            {
                "from": "Origin port",
                "to": "Destination port",
                "teu": "TEU flow",
                "region": "Region identifier"
            }
        ],
        "new_routes": "Newly added routes"
    })

# ============================================================================
# STATE EVENTS
# ============================================================================

class InitialStateEvent(BaseEvent):
    """Initial state sent to new client"""
    type: Literal["initial_state"] = "initial_state"
    data: Dict[str, Any] = Field(..., description={
        "status": "Pipeline status",
        "run_id": "Current run ID",
        "current_iteration": "Current iteration",
        "metrics": "Current metrics",
        "regions": "Regional data",
        "corridors": "Map corridors"
    })

class StateResetEvent(BaseEvent):
    """State reset"""
    type: Literal["state_reset"] = "state_reset"
    data: Dict[str, Any] = Field(..., description={
        "status": "New status",
        "message": "Reset message"
    })

class StatusUpdateEvent(BaseEvent):
    """Status update"""
    type: Literal["status_update"] = "status_update"
    data: Dict[str, Any] = Field(..., description={
        "status": "Current status",
        "run_id": "Run ID",
        "current_stage": "Current stage",
        "current_iteration": "Current iteration",
        "start_time": "Start time"
    })

# ============================================================================
# CLIENT EVENTS
# ============================================================================

class PingEvent(BaseEvent):
    """Client ping"""
    type: Literal["ping"] = "ping"
    data: Dict[str, Any] = Field(default_factory=dict)

class PongEvent(BaseEvent):
    """Server pong response"""
    type: Literal["pong"] = "pong"
    data: Dict[str, Any] = Field(default_factory=dict, description={
        "timestamp": "Response timestamp"
    })

class StartPipelineEvent(BaseEvent):
    """Client requests to start pipeline"""
    type: Literal["start_pipeline"] = "start_pipeline"
    data: Dict[str, Any] = Field(..., description={
        "dataset_path": "Path to dataset",
        "max_iterations": "Maximum iterations",
        "config": "Additional configuration"
    })

class StopPipelineEvent(BaseEvent):
    """Client requests to stop pipeline"""
    type: Literal["stop_pipeline"] = "stop_pipeline"
    data: Dict[str, Any] = Field(default_factory=dict)

class GetStatusEvent(BaseEvent):
    """Client requests current status"""
    type: Literal["get_status"] = "get_status"
    data: Dict[str, Any] = Field(default_factory=dict)

# ============================================================================
# EVENT MAPPINGS
# ============================================================================

# Map event types to their models
EVENT_MODELS = {
    "pipeline_started": PipelineStartedEvent,
    "pipeline_completed": PipelineCompletedEvent,
    "pipeline_error": PipelineErrorEvent,
    "pipeline_stopped": PipelineStoppedEvent,
    "stage_started": StageStartedEvent,
    "stage_progress": StageProgressEvent,
    "stage_completed": StageCompletedEvent,
    "region_updated": RegionUpdatedEvent,
    "iteration_started": IterationStartedEvent,
    "iteration_updated": IterationUpdatedEvent,
    "iteration_completed": IterationCompletedEvent,
    "map_updated": MapUpdatedEvent,
    "initial_state": InitialStateEvent,
    "state_reset": StateResetEvent,
    "status_update": StatusUpdateEvent,
    "ping": PingEvent,
    "pong": PongEvent,
    "start_pipeline": StartPipelineEvent,
    "stop_pipeline": StopPipelineEvent,
    "get_status": GetStatusEvent,
}

# Valid event types
VALID_EVENT_TYPES = set(EVENT_MODELS.keys())

# Client-initiated events
CLIENT_EVENTS = {
    "ping",
    "start_pipeline",
    "stop_pipeline",
    "get_status"
}

# Server-initiated events
SERVER_EVENTS = VALID_EVENT_TYPES - CLIENT_EVENTS

def validate_event(event_type: str, data: Dict[str, Any]) -> BaseEvent:
    """Validate an event against its schema"""
    if event_type not in EVENT_MODELS:
        raise ValueError(f"Unknown event type: {event_type}")

    model = EVENT_MODELS[event_type]
    return model(type=event_type, data=data)

def is_client_event(event_type: str) -> bool:
    """Check if event is client-initiated"""
    return event_type in CLIENT_EVENTS

def is_server_event(event_type: str) -> bool:
    """Check if event is server-initiated"""
    return event_type in SERVER_EVENTS