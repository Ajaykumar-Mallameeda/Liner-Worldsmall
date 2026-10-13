"""
Adaptive Budget Policy — Phase A / B / C
=========================================

Derives computational/search budgets from measurable instance- and
region-level complexity signals.  Does NOT alter:
  - demand values / semantics
  - revenue / fuel / cost formulas
  - GA operators, crossover, mutation, fitness
  - MILP formulation or constraints
  - alpha_unserved (= 300 USD/TEU, fixed)
  - negative-profit-service policy (no hard floor added here)

Only the following values become adaptive:
  Service-generation candidate targets (direct / hub-loop / feeder /
    heuristic / trunk)
  Regional-filter cap
  ServiceGA: pop_size, max_generations, stagnation_limit
  FrequencyGA: pop_size, max_generations, stagnation_limit
  MILP: max_transfer_pairs, time_limit

Formulas are deterministic for identical inputs.  Every calculation is
logged with input signals, raw value, clamped result, and bounds.
"""

from __future__ import annotations
import math
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComplexitySignals:
    """Immutable snapshot of measurable instance/region properties."""
    num_ports: int = 0
    num_lanes: int = 0
    total_demand_teu: float = 0.0
    avg_demand_per_lane: float = 0.0
    median_demand_per_lane: float = 0.0
    density_pct: float = 0.0
    fleet_total_vessels: int = 0


def compute_complexity_signals(
    *,
    num_ports: int,
    demands,
    fleet,
) -> ComplexitySignals:
    """Compute complexity signals from a Problem-like view."""
    if not demands:
        return ComplexitySignals(num_ports=num_ports)

    total_demand = sum(d.weekly_teu for d in demands)
    num_lanes = len(demands)
    avg_demand = total_demand / num_lanes if num_lanes else 0.0
    sorted_demands = sorted(d.weekly_teu for d in demands)
    median_demand = sorted_demands[num_lanes // 2] if num_lanes else 0.0
    max_possible_lanes = num_ports * (num_ports - 1) if num_ports > 1 else 1
    density_pct = num_lanes / max_possible_lanes * 100.0

    fleet_total = fleet.total_vessels if fleet else 0

    return ComplexitySignals(
        num_ports=num_ports,
        num_lanes=num_lanes,
        total_demand_teu=total_demand,
        avg_demand_per_lane=avg_demand,
        median_demand_per_lane=median_demand,
        density_pct=density_pct,
        fleet_total_vessels=fleet_total,
    )


_SMALL_LANE = 400
_MEDIUM_LANE = 800
_DENSE_THRESHOLD = 100.0

_DIRECT_BASE = 500
_DIRECT_MAX = 800
_HUB_BASE = 10
_HUB_MIN = 4
_FEEDER_BASE = 100
_FEEDER_MIN = 20
_HEURISTIC_BASE = 150
_HEURISTIC_MAX = 250
_TRUNK_BASE = 45

_SGA_POP_MIN = 60
_SGA_POP_MAX = 140
_SGA_POP_PER_SIGNAL = 0.8
_SGA_GEN_MIN = 40
_SGA_GEN_MAX = 120
_SGA_STAG_MIN = 5
_SGA_STAG_MAX = 12

_FREQ_POP_MIN = 20
_FREQ_POP_MAX = 60
_FREQ_POP_PER_SIGNAL = 0.5
_FREQ_GEN_MIN = 30
_FREQ_GEN_MAX = 80
_FREQ_STAG_MIN = 5
_FREQ_STAG_MAX = 10

_FILTER_CAP_MIN = 100
_FILTER_CAP_MAX = 600

_MILP_XFER_MIN = 400
_MILP_XFER_MAX = 4000
_MILP_TIME_MIN = 30
_MILP_TIME_MAX = 90


def _tier(complexity: ComplexitySignals) -> str:
    if complexity.num_lanes >= 1500 and complexity.density_pct >= _DENSE_THRESHOLD:
        return "large_dense"
    elif complexity.num_lanes >= 1200:
        return "large"
    elif complexity.num_lanes >= _MEDIUM_LANE:
        return "medium"
    elif complexity.num_lanes >= _SMALL_LANE:
        return "small_dense"
    else:
        return "small"


def _clamp(value: float, lo: float, hi: float) -> int:
    return max(lo, min(hi, int(round(value))))


def _complexity_factor(cs: ComplexitySignals) -> float:
    """
    Dimensionless scaling factor in [0.5, 2.0].
    Drivers: lane count, density %, avg demand per lane, fleet size.
    """
    lane_factor = 0.4 + 0.8 * min(1.0, cs.num_lanes / 2000.0)
    dens_factor = 0.0 + 0.5 * min(1.0, cs.density_pct / _DENSE_THRESHOLD)
    demand_factor = 0.0 + 0.3 * min(1.0, cs.avg_demand_per_lane / 500.0)
    fleet_factor = 0.5 + 0.7 * min(1.0, cs.fleet_total_vessels / 500.0)
    raw = (lane_factor + dens_factor + demand_factor) * fleet_factor
    return max(0.5, min(2.0, raw))


@dataclass
class AdaptiveBudget:
    """Complete adaptive budget for one Problem instance (or one Region)."""
    signals: ComplexitySignals
    complexity_tier: str = ""

    direct_target: int = 0
    hub_loop_target: int = 0
    feeder_target: int = 0
    heuristic_target: int = 0
    trunk_target: int = 45
    candidate_cap: int = 0

    sga_population_size: int = 0
    sga_max_generations: int = 0
    sga_stagnation_limit: int = 0

    freq_population_size: int = 0
    freq_max_generations: int = 0
    freq_stagnation_limit: int = 0

    filter_max_services: int = 0

    milp_candidate_limit: int = 0
    milp_transfer_pair_limit: int = 0
    milp_time_limit_sec: int = 0

    logs: List[str] = field(default_factory=list)

    def _log(self, **kwargs):
        self.logs.append(" | ".join(f"{k}={v}" for k, v in kwargs.items()))

    @classmethod
    def from_signals(cls, cs: ComplexitySignals) -> "AdaptiveBudget":
        factory = cls(signals=cs)
        factory._build()
        return factory

    def _build(self):
        cf = _complexity_factor(self.signals)
        tier = _tier(self.signals)
        self.complexity_tier = tier

        self._log(phase="build", tier=tier, complexity_factor=round(cf, 3),
                  ports=self.signals.num_ports,
                  lanes=self.signals.num_lanes,
                  density_pct=round(self.signals.density_pct, 1),
                  fleet=self.signals.fleet_total_vessels)

        # ---- Service-generation targets ----
        self.direct_target = _clamp(_DIRECT_BASE * cf, _DIRECT_BASE // 2, _DIRECT_MAX)
        self.hub_loop_target = _clamp(_HUB_BASE * cf, _HUB_MIN, int(_HUB_BASE * 2.0))
        self.feeder_target = _clamp(_FEEDER_BASE * cf, _FEEDER_MIN, int(_FEEDER_BASE * 2.5))
        self.heuristic_target = _clamp(_HEURISTIC_BASE * cf, 30, _HEURISTIC_MAX)
        self.trunk_target = _clamp(_TRUNK_BASE * cf * 0.7, 10, _TRUNK_BASE)
        self.candidate_cap = (self.direct_target + self.hub_loop_target
                              + self.feeder_target + self.heuristic_target
                              + self.trunk_target)

        self._log(phase="service_gen",
                  direct_target=self.direct_target,
                  hub_loop_target=self.hub_loop_target,
                  feeder_target=self.feeder_target,
                  heuristic_target=self.heuristic_target,
                  trunk_target=self.trunk_target,
                  candidate_cap=self.candidate_cap)

        # ---- ServiceGA budget ----
        sga_signal = self.signals.num_lanes * 0.001 + self.signals.density_pct * 0.01
        self.sga_population_size = _clamp(
            _SGA_POP_MIN + _SGA_POP_PER_SIGNAL * sga_signal * 100,
            _SGA_POP_MIN, _SGA_POP_MAX)
        self.sga_max_generations = _clamp(
            _SGA_GEN_MIN + 0.3 * self.signals.num_lanes,
            _SGA_GEN_MIN, _SGA_GEN_MAX)
        self.sga_stagnation_limit = _clamp(
            int(0.08 * self.sga_max_generations + 2),
            _SGA_STAG_MIN, _SGA_STAG_MAX)

        self._log(phase="service_ga",
                  population=self.sga_population_size,
                  max_generations=self.sga_max_generations,
                  stagnation_limit=self.sga_stagnation_limit)

        # ---- FrequencyGA budget ----
        freq_signal = self.signals.num_lanes * 0.0005 + self.signals.density_pct * 0.005
        self.freq_population_size = _clamp(
            _FREQ_POP_MIN + _FREQ_POP_PER_SIGNAL * freq_signal * 100,
            _FREQ_POP_MIN, _FREQ_POP_MAX)
        self.freq_max_generations = _clamp(
            _FREQ_GEN_MIN + 0.2 * self.signals.num_lanes,
            _FREQ_GEN_MIN, _FREQ_GEN_MAX)
        self.freq_stagnation_limit = _clamp(
            int(0.10 * self.freq_max_generations + 2),
            _FREQ_STAG_MIN, _FREQ_STAG_MAX)

        self._log(phase="frequency_ga",
                  population=self.freq_population_size,
                  max_generations=self.freq_max_generations,
                  stagnation_limit=self.freq_stagnation_limit)

        # ---- Regional filter cap ----
        filter_raw = (_FILTER_CAP_MIN + 0.4 * self.signals.num_lanes
                      + 0.5 * self.signals.density_pct)
        self.filter_max_services = _clamp(filter_raw,
                                          _FILTER_CAP_MIN, _FILTER_CAP_MAX)

        self._log(phase="filter",
                  max_services=self.filter_max_services,
                  raw=round(filter_raw, 1))

        # ---- MILP workload limits ----
        self.milp_transfer_pair_limit = _clamp(
            int(1500 + 1.0 * self.signals.num_lanes),
            _MILP_XFER_MIN, _MILP_XFER_MAX)
        time_raw = max(
            _MILP_TIME_MIN,
            min(_MILP_TIME_MAX,
                30 + 0.02 * self.signals.num_lanes
                + 0.1 * self.signals.density_pct))
        self.milp_time_limit_sec = int(round(time_raw))

        self._log(phase="milp",
                  transfer_pairs=self.milp_transfer_pair_limit,
                  time_limit_sec=self.milp_time_limit_sec)


def get_service_generation_params(budget: AdaptiveBudget) -> dict:
    """Return a dict consumable by ServiceGeneratorAgent / CandidateServiceGenerator."""
    return {
        "direct_target": budget.direct_target,
        "hub_loop_target": budget.hub_loop_target,
        "feeder_target": budget.feeder_target,
        "heuristic_target": budget.heuristic_target,
        "trunk_target": budget.trunk_target,
        "candidate_cap": budget.candidate_cap,
    }


def get_filter_params(budget: AdaptiveBudget) -> dict:
    return {"max_services": budget.filter_max_services}


def get_service_ga_params(budget: AdaptiveBudget) -> dict:
    return {
        "pop_size": budget.sga_population_size,
        "generations": budget.sga_max_generations,
        "stagnation_limit": budget.sga_stagnation_limit,
    }


def get_frequency_ga_params(budget: AdaptiveBudget) -> dict:
    return {
        "pop_size": budget.freq_population_size,
        "generations": budget.freq_max_generations,
        "stagnation_limit": budget.freq_stagnation_limit,
    }


def get_milp_params(budget: AdaptiveBudget) -> dict:
    return {
        "max_transfer_pairs": budget.milp_transfer_pair_limit,
        "time_limit": budget.milp_time_limit_sec,
    }
