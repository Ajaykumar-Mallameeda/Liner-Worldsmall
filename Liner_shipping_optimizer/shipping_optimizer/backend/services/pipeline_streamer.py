"""
Pipeline Streamer - Streams real-time updates during optimization execution
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass

from ..websocket_manager import WebSocketManager
from ..models.schemas import (
    PipelineEvent, RegionData, IterationData, MapUpdate,
    ServiceRoute, PortCoordinates, MapCorridor
)

logger = logging.getLogger(__name__)

@dataclass
class EventCallback:
    """Event callback definition"""
    event_type: str
    callback: Callable

class PipelineStreamer:
    """Streams real-time updates from the optimization pipeline"""

    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager
        self.event_callbacks: List[EventCallback] = []
        self.is_running = False
        self.current_iteration = 0
        self.total_iterations = 0

    # ============================================================================
    # Event Registration
    # ============================================================================

    def on_event(self, event_type: str):
        """Decorator to register event callbacks"""
        def decorator(func):
            self.event_callbacks.append(EventCallback(event_type, func))
            return func
        return decorator

    async def emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit an event to all registered callbacks"""
        event = PipelineEvent(
            type=event_type,
            timestamp=datetime.utcnow().isoformat(),
            data=data
        )

        # Call all registered callbacks
        for callback in self.event_callbacks:
            if callback.event_type == event_type:
                try:
                    await callback.callback(event)
                except Exception as e:
                    logger.error(f"Error in event callback for {event_type}: {e}")

    # ============================================================================
    # Main Streaming Method
    # ============================================================================

    async def stream_pipeline_run(self, config: Dict[str, Any], run_state: Dict[str, Any]):
        """Stream the entire pipeline execution with real-time updates"""
        try:
            self.is_running = True
            self.total_iterations = config.get("max_iterations", 3)
            self.current_iteration = 0

            # Import here to avoid circular imports
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

            from src.agents.orchestrator_agent import OrchestratorAgent

            # Initialize orchestrator with streaming callback
            orchestrator = OrchestratorAgent(streaming_callback=self._stream_orchestrator_update)

            # Phase 1: Problem Analysis
            await self._stream_problem_analysis(run_state)

            # Phase 2: Run iterations
            for iteration in range(self.total_iterations):
                if not self.is_running:
                    break

                self.current_iteration = iteration
                await self._stream_iteration(iteration, orchestrator, run_state)

            # Phase 3: Final optimization
            await self._stream_final_optimization(run_state)

            # Phase 4: Map updates
            await self._stream_map_updates(run_state)

            self.is_running = False

        except Exception as e:
            logger.error(f"Pipeline streaming error: {e}")
            await self.emit_event("pipeline_error", {"error": str(e)})
            self.is_running = False

    # ============================================================================
    # Streaming Methods
    # ============================================================================

    async def _stream_orchestrator_update(self, update_type: str, data: Dict[str, Any]):
        """Handle updates from the orchestrator agent"""
        await self.emit_event(f"orchestrator_{update_type}", data)

    async def _stream_problem_analysis(self, run_state: Dict[str, Any]):
        """Stream problem analysis phase"""
        await self.emit_event("problem_analysis_started", {})

        # Simulate problem analysis
        await asyncio.sleep(1)

        # Update run state with problem stats
        run_state["problem_stats"] = {
            "total_ports": 500,
            "total_vessels": 150,
            "total_demand": 2500000,
            "regions_count": 5,
            "problem_size": "Large"
        }

        await self.emit_event("problem_analysis_complete", run_state["problem_stats"])

    async def _stream_iteration(self, iteration: int, orchestrator, run_state: Dict[str, Any]):
        """Stream a single iteration"""
        await self.emit_event("iteration_started", {
            "iteration": iteration,
            "total": self.total_iterations
        })

        # Update current iteration in run state
        run_state["current_iteration"] = iteration

        # Simulate iteration execution
        await asyncio.sleep(2)

        # Generate mock regional results
        regions = await self._generate_mock_regions(iteration)

        # Stream regional results
        for region in regions:
            await self.emit_event("region_complete", region.dict())
            run_state["regions"][region.id] = region.dict()
            await asyncio.sleep(0.5)  # Small delay between regions

        # Generate iteration metrics
        iteration_metrics = await self._generate_iteration_metrics(iteration, regions)

        await self.emit_event("iteration_complete", iteration_metrics)
        run_state["iterations"].append(iteration_metrics)

        # Update global metrics
        run_state["metrics"] = await self._calculate_global_metrics(regions)

    async def _stream_final_optimization(self, run_state: Dict[str, Any]):
        """Stream final optimization phase"""
        await self.emit_event("final_optimization_started", {})

        # Simulate MILP optimization
        await asyncio.sleep(3)

        await self.emit_event("final_optimization_complete", {
            "milp_profit_improvement": 5.2,
            "services_optimized": 45,
            "cost_reduction": 1250000
        })

    async def _stream_map_updates(self, run_state: Dict[str, Any]):
        """Stream map visualization updates"""
        await self.emit_event("map_update_started", {})

        # Generate map corridors
        corridors = await self._generate_map_corridors(run_state["regions"])

        map_update = {
            "corridors": [c.dict() for c in corridors],
            "timestamp": datetime.utcnow().isoformat()
        }

        await self.emit_event("map_update_complete", map_update)
        run_state["corridors"] = map_update["corridors"]

    # ============================================================================
    # Data Generation Methods
    # ============================================================================

    async def _generate_mock_regions(self, iteration: int) -> List[RegionData]:
        """Generate mock regional data for demonstration"""
        regions = ["Asia", "Europe", "Americas", "Africa", "Oceania"]
        results = []

        for i, region_name in enumerate(regions):
            # Base values with some randomness
            base_profit = 100000000 + (iteration * 10000000)
            profit_variation = int(base_profit * (0.8 + (i * 0.04)))

            region = RegionData(
                id=f"region_{i}",
                name=region_name,
                status="completed",
                services_generated=800 + iteration * 50,
                services_filtered=400 + iteration * 25,
                services_selected=95 + iteration * 5,
                profit=profit_variation,
                coverage=65.0 + iteration * 2.5,
                cost=profit_variation * 0.25,
                hub_ports=[146 + i, 176 + i, 282 + i],
                optimization_type="hybrid",
                execution_time=12.5 + iteration * 0.5
            )
            results.append(region)

        return results

    async def _generate_iteration_metrics(self, iteration: int, regions: List[RegionData]) -> Dict[str, Any]:
        """Generate iteration summary metrics"""
        total_profit = sum(r.profit for r in regions)
        total_cost = sum(r.cost for r in regions)
        avg_coverage = sum(r.coverage for r in regions) / len(regions)
        total_services = sum(r.services_selected for r in regions)

        return {
            "iteration": iteration,
            "timestamp": datetime.utcnow().isoformat(),
            "profit": total_profit,
            "coverage": avg_coverage,
            "cost": total_cost,
            "services": total_services,
            "convergence_score": min(0.95, 0.8 + (iteration * 0.05)),
            "regions_completed": len(regions),
            "total_regions": 5,
            "rerun_triggered": iteration < 2,  # Trigger rerun for first 2 iterations
            "rerun_reason": "Coverage below threshold" if iteration < 2 else None
        }

    async def _calculate_global_metrics(self, regions: List[RegionData]) -> Dict[str, Any]:
        """Calculate global metrics from regional data"""
        total_weekly_profit = sum(r.profit for r in regions)
        total_cost = sum(r.cost for r in regions)
        total_services = sum(r.services_selected for r in regions)
        avg_coverage = sum(r.coverage for r in regions) / len(regions)

        return {
            "weekly_profit": total_weekly_profit,
            "annual_profit": total_weekly_profit * 52,
            "total_cost": total_cost,
            "total_services": total_services,
            "coverage_percentage": avg_coverage,
            "profit_margin": ((total_weekly_profit - total_cost) / total_weekly_profit) * 100,
            "vessels_utilized": int(total_services * 0.8),
            "total_teu_moved": int(total_weekly_profit / 1000 * 2500)  # Estimate
        }

    async def _generate_map_corridors(self, regions: Dict[str, Any]) -> List[MapCorridor]:
        """Generate maritime corridors for map visualization"""
        corridors = []

        # Major trade lanes
        major_corridors = [
            {"origin": "Asia", "destination": "Europe", "demand": 500000},
            {"origin": "Asia", "destination": "Americas", "demand": 450000},
            {"origin": "Europe", "destination": "Americas", "demand": 350000},
            {"origin": "Europe", "destination": "Africa", "demand": 200000},
            {"origin": "Americas", "destination": "Oceania", "demand": 150000}
        ]

        for corridor_data in major_corridors:
            # Get region data
            origin_region = next((r for r in regions.values() if r["name"] == corridor_data["origin"]), None)
            dest_region = next((r for r in regions.values() if r["name"] == corridor_data["destination"]), None)

            if not origin_region or not dest_region:
                continue

            # Create corridor
            corridor = MapCorridor(
                corridor_id=f"{corridor_data['origin']}_to_{corridor_data['destination']}",
                origin=PortCoordinates(
                    port_id=origin_region["hub_ports"][0],
                    name=f"Hub {corridor_data['origin']}",
                    latitude=0.0,  # Would be populated from real data
                    longitude=0.0,
                    region=corridor_data["origin"],
                    is_hub=True,
                    teu_throughput=int(corridor_data["demand"] * 0.8)
                ),
                destination=PortCoordinates(
                    port_id=dest_region["hub_ports"][0],
                    name=f"Hub {corridor_data['destination']}",
                    latitude=0.0,
                    longitude=0.0,
                    region=corridor_data["destination"],
                    is_hub=True,
                    teu_throughput=int(corridor_data["demand"] * 0.8)
                ),
                demand_teu=corridor_data["demand"],
                serviced_teu=int(corridor_data["demand"] * 0.75),
                coverage_percentage=75.0,
                services=[
                    ServiceRoute(
                        service_id=f"svc_{i}",
                        origin_port=origin_region["hub_ports"][0],
                        destination_port=dest_region["hub_ports"][0],
                        origin_coords=[0.0, 0.0],
                        destination_coords=[0.0, 0.0],
                        weekly_teu=int(corridor_data["demand"] / 10),
                        vessel_type="Panamax",
                        region=corridor_data["origin"],
                        flow_strength=0.8
                    )
                    for i in range(5)
                ],
                color_intensity=0.8
            )
            corridors.append(corridor)

        return corridors

    # ============================================================================
    # Control Methods
    # ============================================================================

    def stop(self):
        """Stop the streaming process"""
        self.is_running = False
        logger.info("Pipeline streaming stopped")

    def is_streaming(self) -> bool:
        """Check if currently streaming"""
        return self.is_running