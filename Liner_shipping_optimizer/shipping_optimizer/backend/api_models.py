"""
Pydantic models for API requests and responses
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


# ============================================================================
# WebSocket Messages
# ============================================================================

class WebSocketMessage(BaseModel):
    """Base WebSocket message"""
    type: str
    data: Optional[Dict[str, Any]] = None


# ============================================================================
# Pipeline Models
# ============================================================================

class PipelineStatus(BaseModel):
    """Pipeline execution status"""
    status: str = Field(..., description="idle|running|complete|error|stopped")
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    current_iteration: int = 0
    total_iterations: int = 3
    runtime_seconds: Optional[float] = None
    progress_percent: float = 0.0


class ProblemStats(BaseModel):
    """Problem statistics"""
    ports: int
    lanes: int
    services: int
    weekly_demand: int
    avg_demand_per_lane: float
    network_density: float


class RegionData(BaseModel):
    """Regional agent data"""
    id: str
    name: str
    status: str = "idle"
    services_generated: int = 0
    services_filtered: int = 0
    services_selected: int = 0
    weekly_profit: float = 0.0
    coverage_percent: float = 0.0
    operating_cost: float = 0.0
    profit_margin_pct: float = 0.0
    profit_per_service: float = 0.0
    cost_per_service: float = 0.0
    uncovered_teu: float = 0.0
    hub_ports: List[int] = []
    strategy: str = ""
    explanation: str = ""
    color: str = "#00d4ff"


class IterationData(BaseModel):
    """Iteration data for feedback loop"""
    iteration: int
    timestamp: datetime
    weekly_profit: float
    coverage: float
    convergence_score: float
    needs_rerun: bool
    rerun_reason: str
    weights_used: Dict[str, float]
    regions: List[RegionData]


class GlobalMetrics(BaseModel):
    """Global optimization metrics"""
    weekly_profit: float
    annual_profit: float
    operating_cost: float
    transship_cost: float = 0.0
    port_cost: float = 0.0
    total_cost: float
    cost: float  # Alias for total_cost
    total_services: int
    satisfied_demand: float
    unserved_demand: float
    coverage: float
    profit_margin_pct: float
    profit_per_service: float
    cost_per_service: float
    uncovered_pct: float


# ============================================================================
# Map Visualization Models
# ============================================================================

class MapCorridor(BaseModel):
    """Maritime corridor for map visualization"""
    from_port: str = Field(..., alias="from")
    to_port: str = Field(..., alias="to")
    teu: int
    region: str
    color: str = "#00d4ff"
    active: bool = True


class MapUpdate(BaseModel):
    """Map update event"""
    iteration: int
    corridors: List[MapCorridor]
    new_routes: List[MapCorridor] = []
    removed_routes: List[MapCorridor] = []


# ============================================================================
# Pipeline Events
# ============================================================================

class PipelineEvent(BaseModel):
    """Pipeline event for streaming"""
    type: str
    timestamp: datetime
    data: Dict[str, Any]


class StageProgress(BaseModel):
    """Progress for a pipeline stage"""
    stage: str
    iteration: int = 0
    message: str
    progress: float  # 0-100


# ============================================================================
# Configuration Models
# ============================================================================

class OptimizationConfig(BaseModel):
    """Optimization configuration"""
    dataset: str = "data/datasets/worldsmall_shipping_problem.json"
    max_iterations: int = 3
    target_coverage: float = 70.0
    target_profit_margin: float = 80.0
    region_count: int = 5
    ga_config: Dict[str, Any] = {}
    milp_config: Dict[str, Any] = {}


# ============================================================================
# Response Models
# ============================================================================

class APIResponse(BaseModel):
    """Base API response"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    message: str
    timestamp: datetime


class ExportResponse(BaseModel):
    """Export response"""
    format: str
    data: Dict[str, Any]
    export_timestamp: datetime


# ============================================================================
# Dashboard State Models
# ============================================================================

class DashboardState(BaseModel):
    """Complete dashboard state"""
    status: PipelineStatus
    problem_stats: ProblemStats
    regions: List[RegionData]
    metrics: GlobalMetrics
    iterations: List[IterationData]
    corridors: List[MapCorridor]
    last_updated: datetime


# ============================================================================
# Request Models
# ============================================================================

class StartPipelineRequest(BaseModel):
    """Start pipeline request"""
    config: OptimizationConfig


class StopPipelineRequest(BaseModel):
    """Stop pipeline request"""
    reason: Optional[str] = None


class ExportRequest(BaseModel):
    """Export request"""
    format: str = "json"  # json|csv|xlsx
    include_iterations: bool = True
    include_raw_data: bool = False