"""
Pipeline event streamer for real-time dashboard updates
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

from .websocket_manager import WebSocketManager
from .api_models import PipelineEvent

logger = logging.getLogger(__name__)

class PipelineStreamer:
    """Streams pipeline execution events via WebSocket"""

    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager
        self.is_running = False
        self.run_task: Optional[asyncio.Task] = None

        # Event callbacks
        self._event_handlers: Dict[str, Callable] = {}

    def on(self, event_type: str):
        """Decorator for event handlers"""
        def decorator(func):
            self._event_handlers[event_type] = func
            return func
        return decorator

    async def emit(self, event_type: str, data: Dict[str, Any]):
        """Emit an event"""
        event = PipelineEvent(
            type=event_type,
            timestamp=datetime.now().isoformat(),
            data=data
        )

        # Call registered handler if exists
        if event_type in self._event_handlers:
            await self._event_handlers[event_type](event)

        # Also send via WebSocket
        await self.websocket_manager.broadcast({
            "type": event_type,
            "data": data,
            "timestamp": event.timestamp
        })

    async def stream_pipeline_run(self, websocket_manager: WebSocketManager,
                                 config: Dict[str, Any], run_state: Dict[str, Any]):
        """Stream entire pipeline run with real-time updates"""
        self.is_running = True

        try:
            # Import here to avoid circular imports
            import sys
            sys.path.append(str(Path(__file__).parent.parent))

            from src.agents.orchestrator_agent import OrchestratorAgent
            from src.data.network_loader import NetworkLoader
            from src.optimization.data import Problem, Port, Service, Demand

            # Initialize orchestrator
            await self.emit("pipeline_starting", {
                "message": "Initializing optimization pipeline...",
                "stage": "initialization"
            })

            orchestrator = OrchestratorAgent()

            # Load problem
            await self.emit("loading_problem", {
                "message": "Loading shipping network data...",
                "dataset": config.get("dataset", "data/datasets/worldsmall_shipping_problem.json")
            })

            problem = await self._load_problem(config.get("dataset"))

            # Analyze problem
            await self.emit("analyzing_problem", {
                "message": "Analyzing network complexity and characteristics...",
                "stage": "analysis"
            })

            analysis = orchestrator.analyze_problem(problem)

            # Update run state with problem stats
            problem_stats = {
                "ports": len(problem.ports),
                "lanes": len(problem.demands),
                "services": len(problem.services),
                "weekly_demand": sum(d.weekly_teu for d in problem.demands)
            }
            run_state["problem_stats"] = problem_stats

            await self.emit("problem_analyzed", {
                "analysis": analysis,
                "stats": problem_stats,
                "stage": "analysis_complete"
            })

            # Start pipeline execution
            max_iterations = config.get("max_iterations", 3)
            iterations_data = []

            for iteration in range(max_iterations):
                if not self.is_running:
                    break

                await self.emit("iteration_start", {
                    "iteration": iteration,
                    "max_iterations": max_iterations,
                    "message": f"Starting optimization iteration {iteration + 1}..."
                })

                # Simulate pipeline stages with delays
                stages = [
                    ("decomposition", "Decomposing problem into regional clusters..."),
                    ("regional_optimization", "Running regional agents (GA + MILP)..."),
                    ("service_generation", "Generating and filtering candidate services..."),
                    ("conflict_resolution", "Resolving inter-regional conflicts...")
                ]

                for stage, message in stages:
                    if not self.is_running:
                        break

                    await self.emit("stage_progress", {
                        "stage": stage,
                        "iteration": iteration,
                        "message": message,
                        "progress": 25 * stages.index((stage, message)) + 25
                    })

                    # Simulate work with realistic delays
                    await asyncio.sleep(2 + iteration * 0.5)

                # Generate mock iteration results
                iteration_data = self._generate_mock_iteration(iteration, problem_stats)
                iterations_data.append(iteration_data)

                await self.emit("iteration_complete", {
                    "iteration": iteration,
                    "results": iteration_data,
                    "convergence_score": 0.975 + (iteration * 0.005),
                    "needs_rerun": iteration < 2,
                    "rerun_reason": "Coverage below target" if iteration < 2 else "Converged"
                })

                # Update map with new routes
                await self._update_map_visualization(iteration, run_state)

            # Complete pipeline
            await self.emit("pipeline_complete", {
                "message": "Optimization pipeline completed successfully!",
                "total_iterations": len(iterations_data),
                "final_metrics": self._generate_final_metrics(iterations_data, problem_stats),
                "iterations": iterations_data
            })

        except Exception as e:
            logger.error(f"Pipeline streaming error: {e}")
            await self.emit("pipeline_error", {
                "error": str(e),
                "message": "Pipeline execution failed"
            })
        finally:
            self.is_running = False

    async def _load_problem(self, dataset_path: str):
        """Load shipping network problem"""
        # This would load the actual problem data
        # For now, return a mock problem
        return MockProblem()

    def _generate_mock_iteration(self, iteration: int, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock iteration results"""
        base_profit = 700000000 + (iteration * 20000000)
        base_coverage = 65 + (iteration * 2)

        return {
            "iteration": iteration,
            "weekly_profit": base_profit,
            "coverage": base_coverage + (iteration * 0.5),
            "convergence_score": 0.975 + (iteration * 0.005),
            "services_deployed": 450 + (iteration * 5),
            "regions": [
                {
                    "id": "asia",
                    "name": "Asia",
                    "profit": base_profit * 0.14,
                    "coverage": 75 + iteration,
                    "services": 95 + iteration,
                    "cost": 20000000,
                    "margin": 78 + iteration,
                    "hubs": [146, 176, 282]
                },
                {
                    "id": "europe",
                    "name": "Europe",
                    "profit": base_profit * 0.09,
                    "coverage": 45 + iteration * 2,
                    "services": 85 + iteration,
                    "cost": 18000000,
                    "margin": 70 + iteration,
                    "hubs": [221, 36, 75]
                },
                {
                    "id": "americas",
                    "name": "Americas",
                    "profit": base_profit * 0.60,
                    "coverage": 55 + iteration,
                    "services": 90 + iteration,
                    "cost": 19000000,
                    "margin": 91 + iteration,
                    "hubs": [235, 285, 100]
                },
                {
                    "id": "middle_east",
                    "name": "Middle East",
                    "profit": base_profit * 0.07,
                    "coverage": 85 + iteration,
                    "services": 75 + iteration,
                    "cost": 17000000,
                    "margin": 72 + iteration,
                    "hubs": [229, 225, 190]
                },
                {
                    "id": "africa",
                    "name": "Africa",
                    "profit": base_profit * 0.10,
                    "coverage": 60 + iteration,
                    "services": 105 + iteration,
                    "cost": 21000000,
                    "margin": 69 + iteration,
                    "hubs": [113, 112, 69]
                }
            ]
        }

    def _generate_final_metrics(self, iterations: List[Dict[str, Any]],
                               stats: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final aggregated metrics"""
        if not iterations:
            return {}

        last_iter = iterations[-1]
        total_profit = sum(r["profit"] for r in last_iter["regions"])
        total_cost = sum(r["cost"] for r in last_iter["regions"])

        return {
            "weekly_profit": total_profit,
            "annual_profit": total_profit * 52,
            "operating_cost": total_cost,
            "total_services": sum(r["services"] for r in last_iter["regions"]),
            "coverage": sum(r["coverage"] for r in last_iter["regions"]) / len(last_iter["regions"]),
            "profit_margin": (total_profit / (total_profit + total_cost)) * 100 if (total_profit + total_cost) > 0 else 0,
            "convergence_score": last_iter["convergence_score"],
            "iterations_run": len(iterations)
        }

    async def _update_map_visualization(self, iteration: int, run_state: Dict[str, Any]):
        """Update maritime map with new routes"""
        # Generate mock corridors
        corridors = [
            {"from": f"Port {285}", "to": f"Port {146}", "teu": 10902 + iteration * 100, "region": "americas"},
            {"from": f"Port {235}", "to": f"Port {36}", "teu": 5292 + iteration * 50, "region": "americas"},
            {"from": f"Port {221}", "to": f"Port {100}", "teu": 1932 + iteration * 30, "region": "europe"},
            {"from": f"Port {112}", "to": f"Port {176}", "teu": 1128 + iteration * 20, "region": "africa"},
            {"from": f"Port {220}", "to": f"Port {229}", "teu": 966 + iteration * 25, "region": "middle_east"}
        ]

        run_state["corridors"] = corridors

        await self.emit("map_update", {
            "iteration": iteration,
            "corridors": corridors,
            "new_routes": corridors[:2]  # Highlight new routes
        })

    async def stop(self):
        """Stop the streaming pipeline"""
        self.is_running = False
        if self.run_task:
            self.run_task.cancel()
            try:
                await self.run_task
            except asyncio.CancelledError:
                pass


# Mock classes for testing
class MockProblem:
    def __init__(self):
        self.ports = [MockPort(i) for i in range(435)]
        self.demands = [MockDemand(i) for i in range(9622)]
        self.services = [MockService(i) for i in range(1200)]

class MockPort:
    def __init__(self, id):
        self.id = id
        self.name = f"Port {id}"

class MockDemand:
    def __init__(self, id):
        self.id = id
        self.weekly_teu = 100 + id % 1000

class MockService:
    def __init__(self, id):
        self.id = id
        self.name = f"Service {id}"