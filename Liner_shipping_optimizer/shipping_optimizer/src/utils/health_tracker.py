import time
import threading
from typing import Dict, Any, Optional
from src.utils.logger import logger


class HealthTracker:
    """Minimal runtime health tracking for the optimizer"""

    def __init__(self):
        self._lock = threading.Lock()
        self._reset()

    def _reset(self):
        """Reset health state"""
        self.start_time = None
        self.end_time = None
        self.status = "not_started"
        self.current_region = None
        self.last_failure = None
        self.iterations = 0
        self.regions_completed = []
        self.regions_failed = []

    def optimizer_started(self):
        """Record optimizer start"""
        with self._lock:
            self.start_time = time.time()
            self.status = "running"
            logger.info("health_optimizer_started", timestamp=self.start_time)

    def optimizer_completed(self, success: bool = True):
        """Record optimizer completion"""
        with self._lock:
            self.end_time = time.time()
            self.status = "completed" if success else "failed"
            runtime = self.end_time - (self.start_time or self.end_time)
            logger.info("health_optimizer_completed",
                       status=self.status,
                       runtime=runtime,
                       iterations=self.iterations)

    def region_started(self, region_name: str):
        """Record region start"""
        with self._lock:
            self.current_region = region_name
            logger.info("health_region_started", region=region_name)

    def region_completed(self, region_name: str, success: bool = True):
        """Record region completion"""
        with self._lock:
            if success:
                self.regions_completed.append(region_name)
                logger.info("health_region_completed", region=region_name)
            else:
                self.regions_failed.append(region_name)
                logger.warning("health_region_failed", region=region_name)

            if self.current_region == region_name:
                self.current_region = None

    def iteration_started(self, iteration: int):
        """Record iteration start"""
        with self._lock:
            self.iterations = iteration
            logger.info("health_iteration_started", iteration=iteration)

    def failure_occurred(self, component: str, error: str):
        """Record a failure"""
        with self._lock:
            self.last_failure = {
                "timestamp": time.time(),
                "component": component,
                "error": error
            }
            logger.error("health_failure_occurred",
                        component=component,
                        error=error)

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        with self._lock:
            now = time.time()
            runtime = (self.end_time or now) - (self.start_time or now)

            return {
                "status": self.status,
                "runtime_seconds": round(runtime, 2),
                "iterations": self.iterations,
                "current_region": self.current_region,
                "regions_completed": self.regions_completed.copy(),
                "regions_failed": self.regions_failed.copy(),
                "last_failure": self.last_failure,
                "success_rate": (
                    len(self.regions_completed) /
                    (len(self.regions_completed) + len(self.regions_failed))
                    if (len(self.regions_completed) + len(self.regions_failed)) > 0
                    else 0.0
                )
            }


# Global instance
health_tracker = HealthTracker()