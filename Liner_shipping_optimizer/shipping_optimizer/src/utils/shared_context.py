"""
Shared Context for multi-agent coordination.

Holds the SHARED_CONTEXT dict that all agents can read and propose updates to.
The orchestrator hosts it and propagates it at iteration boundaries.

Ownership rules (from MULTI_AGENT_INTERACTION_MAP.md Section 3.2):

    global_objectives        → Coordinator
    regional_priorities.*    → Regional Agent (one per region)
    service_archetype_plan   → Service Generator Agent
    hub_strategy             → Orchestrator (aggregation)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class GlobalObjectives:
    """Set by Coordinator, read by all agents."""

    profit_weight: float = 0.50
    coverage_weight: float = 0.40
    cost_weight: float = 0.10
    iteration: int = 0
    coverage_target: float = 70.0
    profit_floor: float = 0.0
    max_iterations: int = 3
    current_coverage: float = 0.0
    current_profit: float = 0.0
    convergence_score: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "profit_weight": self.profit_weight,
            "coverage_weight": self.coverage_weight,
            "cost_weight": self.cost_weight,
            "iteration": self.iteration,
            "coverage_target": self.coverage_target,
            "profit_floor": self.profit_floor,
            "max_iterations": self.max_iterations,
            "current_coverage": self.current_coverage,
            "current_profit": self.current_profit,
            "convergence_score": self.convergence_score,
        }

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "GlobalObjectives":
        if d is None:
            return cls()
        return cls(
            profit_weight=float(d.get("profit_weight", 0.50)),
            coverage_weight=float(d.get("coverage_weight", 0.40)),
            cost_weight=float(d.get("cost_weight", 0.10)),
            iteration=int(d.get("iteration", 0)),
            coverage_target=float(d.get("coverage_target", 70.0)),
            profit_floor=float(d.get("profit_floor", 0.0)),
            max_iterations=int(d.get("max_iterations", 3)),
            current_coverage=float(d.get("current_coverage", 0.0)),
            current_profit=float(d.get("current_profit", 0.0)),
            convergence_score=float(d.get("convergence_score", 0.0)),
        )


@dataclass
class RegionalPriority:
    """Set by each Regional Agent for its own region."""

    coverage_priority: float = 0.50
    profit_priority: float = 0.50
    hub_focus: List[str] = field(default_factory=list)
    min_service_margin: float = 0.05
    vessel_bias: str = "balanced"
    current_coverage: float = 0.0
    current_profit: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coverage_priority": self.coverage_priority,
            "profit_priority": self.profit_priority,
            "hub_focus": list(self.hub_focus),
            "min_service_margin": self.min_service_margin,
            "vessel_bias": self.vessel_bias,
            "current_coverage": self.current_coverage,
            "current_profit": self.current_profit,
        }

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "RegionalPriority":
        if d is None:
            return cls()
        return cls(
            coverage_priority=float(d.get("coverage_priority", 0.50)),
            profit_priority=float(d.get("profit_priority", 0.50)),
            hub_focus=list(d.get("hub_focus", [])),
            min_service_margin=float(d.get("min_service_margin", 0.05)),
            vessel_bias=str(d.get("vessel_bias", "balanced")),
            current_coverage=float(d.get("current_coverage", 0.0)),
            current_profit=float(d.get("current_profit", 0.0)),
        )


# =============================================================================
# SharedContext
# =============================================================================


@dataclass
class SharedContext:
    """The single shared context dict hosted by the orchestrator."""

    global_objectives: GlobalObjectives = field(default_factory=GlobalObjectives)
    regional_priorities: Dict[str, RegionalPriority] = field(default_factory=dict)
    service_archetype_plan: Dict[str, Any] = field(default_factory=lambda: {
        "direct_ratio": 0.60,
        "hub_loop_ratio": 0.15,
        "feeder_ratio": 0.20,
        "trunk_ratio": 0.05,
        "vessel_bias": "balanced",
    })
    hub_strategy: Dict[str, Any] = field(default_factory=lambda: {
        "primary_hubs": [],
        "recommended_hubs": {},
        "overlap_hubs": [],
    })

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for agent input_data."""
        return {
            "global_objectives": self.global_objectives.to_dict(),
            "regional_priorities": {
                name: rp.to_dict()
                for name, rp in self.regional_priorities.items()
            },
            "service_archetype_plan": dict(self.service_archetype_plan),
            "hub_strategy": dict(self.hub_strategy),
        }

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "SharedContext":
        """Deserialize from a plain dict."""
        if d is None:
            return cls()
        raw = d if isinstance(d, dict) else {}
        regional_raw = raw.get("regional_priorities", {}) or {}
        return cls(
            global_objectives=GlobalObjectives.from_dict(
                raw.get("global_objectives")
            ),
            regional_priorities={
                name: RegionalPriority.from_dict(rp)
                for name, rp in regional_raw.items()
            },
            service_archetype_plan=dict(raw.get("service_archetype_plan", {}) or {}),
            hub_strategy=dict(raw.get("hub_strategy", {}) or {}),
        )

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def get_global_objectives_dict(self) -> Dict[str, Any]:
        """Return global objectives as a plain dict (used in agent prompts)."""
        return self.global_objectives.to_dict()

    def get_regional_priority(self, region: str) -> Optional[RegionalPriority]:
        """Get a specific region's priority, or None."""
        return self.regional_priorities.get(region)

    def set_regional_priority(self, region: str, priority: RegionalPriority) -> None:
        """Set a region's priority (ownership: Regional Agent)."""
        self.regional_priorities[region] = priority

    def update_hub_strategy(self) -> None:
        """Recompute hub_strategy from current regional_priorities."""
        all_hubs: List[str] = []
        recommended: Dict[str, List[str]] = {}
        for name, rp in self.regional_priorities.items():
            hubs = rp.hub_focus
            recommended[name] = list(hubs)
            all_hubs.extend(hubs)

        from collections import Counter
        hub_counts = Counter(all_hubs)
        self.hub_strategy = {
            "primary_hubs": sorted([h for h, c in hub_counts.items() if c >= 2]),
            "recommended_hubs": recommended,
            "overlap_hubs": sorted([h for h, c in hub_counts.items() if c >= 2]),
        }
