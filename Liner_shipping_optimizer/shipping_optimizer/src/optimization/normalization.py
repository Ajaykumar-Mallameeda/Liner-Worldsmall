"""
Objective normalization layer for AI Vessel Routing System.
Provides mathematically stable scaling for objective components.
"""

import numpy as np
from typing import Dict, Tuple, Optional


class ObjectiveNormalizer:
    """Normalizes objective components using mathematically stable scaling."""

    def __init__(self):
        # Predefined scaling factors based on calibration report
        # Orders of magnitude from OBJECTIVE_WEIGHT_CALIBRATION_REPORT.md
        self.scaling_factors = {
            'profit': 1e7,      # ~10^7 magnitude
            'coverage': 1e0,    # ~10^0 magnitude
            'cost': 1e7,        # ~10^6-10^7 magnitude
            'revenue': 1e8,     # ~10^8 magnitude
            'fuel_cost': 1e7,   # ~10^7 magnitude
            'port_cost': 1e8,   # ~10^8 magnitude
            'unserved_penalty': 1e7,  # ~10^7 magnitude
            'overcap_penalty': 1e5,    # ~10^5 magnitude
            'transship_cost': 1e6,     # ~10^6 magnitude
            'alignment_penalty': 1e0,  # ~10^0 magnitude
        }

        # Runtime min/max tracking for adaptive normalization
        self.runtime_bounds: Dict[str, Tuple[float, float]] = {}

    def normalize_component(self, component_name: str, value: float) -> float:
        """
        Normalize a single component value.

        Args:
            component_name: Name of the component (e.g., 'profit', 'coverage')
            value: Raw component value

        Returns:
            Normalized value (typically in range [0, 1] or [-1, 1])
        """
        scaling = self.scaling_factors.get(component_name, 1.0)

        # Handle very small scaling factors to avoid division issues
        if scaling == 0:
            return value

        normalized = value / scaling

        # Update runtime bounds
        if component_name not in self.runtime_bounds:
            self.runtime_bounds[component_name] = (value, value)
        else:
            min_val, max_val = self.runtime_bounds[component_name]
            self.runtime_bounds[component_name] = (
                min(min_val, value),
                max(max_val, value)
            )

        return normalized

    def normalize_objective_components(self, components: Dict[str, float]) -> Dict[str, float]:
        """
        Normalize all objective components.

        Args:
            components: Dictionary of component name -> raw value

        Returns:
            Dictionary of component name -> normalized value
        """
        normalized = {}

        for name, value in components.items():
            normalized[name] = self.normalize_component(name, value)

        return normalized

    def get_normalization_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Get statistics about normalization scaling.

        Returns:
            Dictionary with min, max, mean values for each component
        """
        stats = {}

        for name, (min_val, max_val) in self.runtime_bounds.items():
            scaling = self.scaling_factors.get(name, 1.0)
            stats[name] = {
                'raw_min': min_val,
                'raw_max': max_val,
                'raw_range': max_val - min_val,
                'normalized_min': min_val / scaling if scaling != 0 else min_val,
                'normalized_max': max_val / scaling if scaling != 0 else max_val,
                'scaling_factor': scaling
            }

        return stats


class ObjectiveWeights:
    """Configurable objective weight framework."""

    # Default weights (legacy coverage-first)
    LEGACY_WEIGHTS = {
        'profit': 0.5,
        'coverage': 0.4,
        'cost': 0.1,
    }

    # Profit-first weights (for future use)
    PROFIT_FIRST_WEIGHTS = {
        'profit': 10.0,
        'coverage': 0.01,
        'cost': 0.1,
    }

    def __init__(self, mode: str = "legacy"):
        """
        Initialize weights for given mode.

        Args:
            mode: Either "legacy" or "profit_first"
        """
        self.mode = mode

        if mode == "legacy":
            self.weights = self.LEGACY_WEIGHTS.copy()
        elif mode == "profit_first":
            self.weights = self.PROFIT_FIRST_WEIGHTS.copy()
        else:
            raise ValueError(f"Unknown weight mode: {mode}")

 # No coverage scaling - weights are applied directly
        self.coverage_scaling = 1.0

    def get_weights(self) -> Dict[str, float]:
        """Get current weight configuration."""
        return self.weights.copy()

    def set_weight(self, component: str, weight: float):
        """Set individual component weight."""
        self.weights[component] = weight

    def calculate_weighted_score(self, normalized_components: Dict[str, float]) -> float:
        """
        Calculate final weighted score from normalized components.

        Args:
            normalized_components: Dict of normalized component values

        Returns:
            Weighted composite score
        """
        score = 0.0

        for component, weight in self.weights.items():
            if component in normalized_components:
                value = normalized_components[component]

                score += weight * value

        return score

    def get_weight_contributions(self, normalized_components: Dict[str, float]) -> Dict[str, float]:
        """
        Get contribution percentage of each component to final score.

        Args:
            normalized_components: Dict of normalized component values

        Returns:
            Dict of component -> contribution percentage
        """
        contributions = {}
        total_score = 0.0
        raw_contributions = {}

        # Calculate raw contributions
        for component, weight in self.weights.items():
            if component in normalized_components:
                value = normalized_components[component]

                contribution = weight * value
                raw_contributions[component] = contribution
                total_score += abs(contribution)  # Use absolute for percentage

        # Convert to percentages
        if total_score > 0:
            for component, contribution in raw_contributions.items():
                contributions[component] = (abs(contribution) / total_score) * 100
        else:
            # If no score, distribute equally
            equal_share = 100.0 / len(raw_contributions)
            contributions = {c: equal_share for c in raw_contributions}

        return contributions