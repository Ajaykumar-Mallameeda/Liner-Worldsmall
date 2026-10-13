"""
Pydantic models for API requests and responses
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum

# ============================================================================
# Enums
# ============================================================================

class PipelineStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    STOPPED = "stopped"

class RegionStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"

class OptimizationType(str, Enum):
    GENETIC = "genetic"
    MILP = "milp"
    HYBRID = "hybrid"

# ============================================================================
# WebSocket Message Types
# ============================================================================

class WebSocketMessage(BaseModel):
    type: str
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None

class PipelineEvent(BaseModel):
    type: str
    timestamp: str
    data: Dict[str, Any]

# ============================================================================
# Pipeline Models
# ============================================================================

class ProblemStats(BaseModel):
    total_ports: int = Field(..., description="Total number of ports in the problem")
    total_vessels: int = Field(..., description="Total number of vessels available")
    total_demand: int = Field(..., description="Total TEU demand")
    regions_count: int = Field(..., description="Number of regions")
    problem_size: str = Field(..., description="Problem size classification")

class RegionData(BaseModel):
    id: str
    name: str
    status: RegionStatus
    services_generated: int = 0
    services_filtered: int = 0
    services_selected: int = 0
    profit: float = 0.0
    coverage: float = 0.0
    cost: float = 0.0
    hub_ports: List[int] = []
    optimization_type: Optional[OptimizationType] = None
    execution_time: Optional[float] = None
    error_message: Optional[str] = None

class IterationData(BaseModel):
    iteration: int
    timestamp: str
    profit: float
    coverage: float
    cost: float
    services: int
    convergence_score: float
    regions_completed: int
    total_regions: int
    rerun_triggered: bool = False
    rerun_reason: Optional[str] = None

class GlobalMetrics(BaseModel):
    weekly_profit: float = Field(..., description="Total weekly profit in USD")
    annual_profit: float = Field(..., description="Projected annual profit in USD")
    total_cost: float = Field(..., description="Total weekly cost in USD")
    total_services: int = Field(..., description="Total number of services selected")
    coverage_percentage: float = Field(..., description="Demand coverage percentage")
    profit_margin: float = Field(..., description="Profit margin percentage")
    vessels_utilized: int = Field(..., description="Number of vessels utilized")
    total_teu_moved: int = Field(..., description="Total TEU moved weekly")

# ============================================================================
# Map Visualization Models
# ============================================================================

class PortCoordinates(BaseModel):
    port_id: int
    name: str
    latitude: float
    longitude: float
    region: str
    is_hub: bool = False
    teu_throughput: int = 0

class ServiceRoute(BaseModel):
    service_id: str
    origin_port: int
    destination_port: int
    origin_coords: List[float]  # [lon, lat]
    destination_coords: List[float]  # [lon, lat]
    weekly_teu: int
    vessel_type: str
    region: str
    flow_strength: float = Field(0.0, ge=0.0, le=1.0)
    active: bool = True

class MapCorridor(BaseModel):
    corridor_id: str
    origin: PortCoordinates
    destination: PortCoordinates
    demand_teu: int
    serviced_teu: int
    coverage_percentage: float
    services: List[ServiceRoute]
    color_intensity: float = Field(0.0, ge=0.0, le=1.0)

class MapUpdate(BaseModel):
    corridors: List[MapCorridor]
    ports: List[PortCoordinates]
    routes: List[ServiceRoute]
    timestamp: str

# ============================================================================
# Configuration Models
# ============================================================================

class PipelineConfig(BaseModel):
    max_iterations: int = Field(3, description="Maximum number of iterations")
    convergence_threshold: float = Field(0.95, description="Convergence threshold")
    optimization_type: OptimizationType = OptimizationType.HYBRID
    regions: Optional[List[str]] = None
    seed: Optional[int] = None
    enable_logging: bool = True
    parallel_regions: bool = True

class OptimizationConfig(BaseModel):
    genetic: Dict[str, Any] = Field(default_factory=dict)
    milp: Dict[str, Any] = Field(default_factory=dict)
    regional: Dict[str, Any] = Field(default_factory=dict)

# ============================================================================
# Request/Response Models
# ============================================================================

class PipelineStartRequest(BaseModel):
    config: PipelineConfig
    optimization_config: Optional[OptimizationConfig] = None

class PipelineStatusResponse(BaseModel):
    status: PipelineStatus
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    current_iteration: int = 0
    total_iterations: int = 0
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: Optional[float] = None

class PipelineResults(BaseModel):
    status: PipelineStatus
    start_time: str
    end_time: str
    total_execution_time: float
    problem_stats: ProblemStats
    global_metrics: GlobalMetrics
    regions: List[RegionData]
    iterations: List[IterationData]
    map_data: MapUpdate
    conflicts_resolved: int = 0
    optimization_log: List[str] = []

class ErrorResponse(BaseModel):
    error: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None

# ============================================================================
# Event Types for WebSocket
# ============================================================================

class EventType(str, Enum):
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_STOPPED = "pipeline_stopped"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_ERROR = "pipeline_error"

    PROBLEM_ANALYZED = "problem_analyzed"
    REGION_STARTED = "region_started"
    REGION_COMPLETED = "region_completed"
    REGION_ERROR = "region_error"

    ITERATION_STARTED = "iteration_started"
    ITERATION_COMPLETED = "iteration_complete"
    CONVERGENCE_UPDATE = "convergence_update"

    OPTIMIZATION_STARTED = "optimization_started"
    OPTIMIZATION_PROGRESS = "optimization_progress"
    OPTIMIZATION_COMPLETED = "optimization_completed"

    MAP_UPDATE = "map_update"
    ROUTE_ADDED = "route_added"
    ROUTE_REMOVED = "route_removed"

    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"

    METRICS_UPDATE = "metrics_update"
    STATUS_UPDATE = "status_update"

# ============================================================================
# Dashboard State Models
# ============================================================================

class DashboardState(BaseModel):
    is_live: bool = False
    auto_refresh: bool = True
    refresh_interval: int = 5  # seconds
    selected_region: Optional[str] = None
    selected_iteration: Optional[int] = None
    map_filters: Dict[str, Any] = Field(default_factory=dict)
    chart_preferences: Dict[str, Any] = Field(default_factory=dict)

class UserPreferences(BaseModel):
    theme: str = "light"  # light, dark
    notifications_enabled: bool = True
    sound_enabled: bool = False
    language: str = "en"