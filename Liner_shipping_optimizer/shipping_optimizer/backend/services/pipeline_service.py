"""
Pipeline service for running optimization tasks
"""

import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class PipelineService:
    """Service for running the optimization pipeline"""

    def __init__(self):
        self.current_run: Optional[Dict[str, Any]] = None
        self.run_lock = asyncio.Lock()

    async def run_pipeline(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run the full optimization pipeline"""
        async with self.run_lock:
            if self.current_run:
                raise ValueError("Pipeline already running")

            try:
                self.current_run = {
                    "status": "running",
                    "start_time": datetime.now(),
                    "config": config
                }

                # Import and run orchestrator
                result = await self._execute_orchestrator(config)

                self.current_run.update({
                    "status": "complete",
                    "end_time": datetime.now(),
                    "result": result
                })

                return result

            except Exception as e:
                logger.error(f"Pipeline error: {e}")
                self.current_run.update({
                    "status": "error",
                    "end_time": datetime.now(),
                    "error": str(e)
                })
                raise
            finally:
                self.current_run = None

    async def _execute_orchestrator(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the orchestrator agent"""
        # Import here to avoid circular imports
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))

        from src.agents.orchestrator_agent import OrchestratorAgent
        from src.data.network_loader import NetworkLoader
        from src.optimization.data import Problem, Port, Service, Demand

        # Initialize orchestrator
        orchestrator = OrchestratorAgent()

        # Load problem
        dataset_path = config.get("dataset", "data/datasets/worldsmall_shipping_problem.json")
        problem = await self._load_problem(dataset_path)

        # Run optimization
        input_data = {"problem": problem}
        result = orchestrator.process(input_data)

        return result

    async def _load_problem(self, dataset_path: str):
        """Load problem from dataset"""
        # For now, return a mock problem
        # In production, this would load the actual dataset
        return MockProblem()

    async def get_problem_statistics(self) -> Dict[str, Any]:
        """Get problem statistics without running full pipeline"""
        return {
            "ports": 47,
            "lanes": 1764,
            "services": 551,
            "weekly_demand": 276447,
            "avg_demand_per_lane": 156.7,
            "network_density": 163.2
        }

    async def get_current_status(self) -> Optional[Dict[str, Any]]:
        """Get current pipeline status"""
        return self.current_run.copy() if self.current_run else None


class MockProblem:
    """Mock problem for testing"""
    def __init__(self):
        self.ports = [MockPort(i) for i in range(435)]
        self.demands = [MockDemand(i) for i in range(9622)]
        self.services = [MockService(i) for i in range(1200)]
        self.distance_matrix = [[0] * 435 for _ in range(435)]


class MockPort:
    def __init__(self, id):
        self.id = id
        self.name = f"Port {id}"


class MockDemand:
    def __init__(self, id):
        self.id = id
        self.origin = id % 435
        self.destination = (id + 1) % 435
        self.weekly_teu = 100 + id % 1000


class MockService:
    def __init__(self, id):
        self.id = id
        self.name = f"Service {id}"
        self.ports = [(id % 435), ((id + 1) % 435), ((id + 2) % 435)]