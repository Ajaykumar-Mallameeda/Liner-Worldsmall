"""
Objective configuration for AI Vessel Routing System.
Supports both legacy coverage-first and profit-first modes.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class ObjectiveConfig:
    """Configuration for optimizer objective weights and modes."""

    # Objective mode selection
    objective_mode: str = "profit_first"  # "legacy" or "profit_first"

    # Coverage constraint (for profit-first mode)
    min_coverage_percent: float = 70.0  # Minimum coverage requirement

    # Service profitability gate (for profit-first mode)
    profitability_gate_enabled: bool = True  # Enabled in P2
    min_margin_percent: float = 0.05  # 5% minimum margin for profitability gate

    # Runtime logging control
    verbose_runtime_logs: bool = False  # Control GA/MILP runtime noise

    # Legacy weights (coverage-first)
    legacy_weights: Dict[str, float] = None

    # Profit-first weights (P2 calibrated)
    profit_first_weights: Dict[str, float] = None

    def __post_init__(self):
        if self.legacy_weights is None:
            self.legacy_weights = {
                'profit': 0.5,
                'coverage': 0.4,
                'cost': 0.1,
            }

        if self.profit_first_weights is None:
            self.profit_first_weights = {
                'profit': 0.60,  # Reduced to 60% weight on profit (was 70%)
                'coverage': 0.25,  # Increased to 25% weight on coverage (was 15%)
                'cost': 0.15,     # 15% weight on cost
            }

    def get_weights(self) -> Dict[str, float]:
        """Get active weights based on objective mode."""
        if self.objective_mode == "legacy":
            return self.legacy_weights.copy()
        elif self.objective_mode == "profit_first":
            return self.profit_first_weights.copy()
        else:
            raise ValueError(f"Unknown objective mode: {self.objective_mode}")

    def is_profit_first_active(self) -> bool:
        """Check if profit-first mode is active."""
        return self.objective_mode == "profit_first"


# Global configuration instance
CONFIG = ObjectiveConfig()