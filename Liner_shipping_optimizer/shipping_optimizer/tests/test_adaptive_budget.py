"""
Adaptive Budget Policy — Unit & Property Tests
===============================================
Tests for src/optimization/adaptive_budget.py covering:
  1. Deterministic budget calculation
  2. Minimum / maximum bounds
  3. No zero values produced
  4. Monotonic behavior where expected
  5. Region-specific adaptation
  6. Service-count adaptation
  7. Active-service adaptation
  8. MILP workload adaptation
  9. LLM independence
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.optimization.adaptive_budget import (
    AdaptiveBudget,
    ComplexitySignals,
    compute_complexity_signals,
    get_service_generation_params,
    get_filter_params,
    get_service_ga_params,
    get_frequency_ga_params,
    get_milp_params,
    # Expose constants for bound checks
    _SGA_POP_MIN, _SGA_POP_MAX, _SGA_GEN_MIN, _SGA_GEN_MAX,
    _SGA_STAG_MIN, _SGA_STAG_MAX,
    _FREQ_POP_MIN, _FREQ_POP_MAX, _FREQ_GEN_MIN, _FREQ_GEN_MAX,
    _FREQ_STAG_MIN, _FREQ_STAG_MAX,
    _FILTER_CAP_MIN, _FILTER_CAP_MAX,
    _MILP_XFER_MIN, _MILP_XFER_MAX,
    _MILP_TIME_MIN, _MILP_TIME_MAX,
)


# ---------------------------------------------------------------------------
# Fixture: shared complexity signals for common instance sizes
# ---------------------------------------------------------------------------

@pytest.fixture
def worldsmall_signals():
    return ComplexitySignals(
        num_ports=47,
        num_lanes=1764,
        total_demand_teu=276447.0,
        avg_demand_per_lane=156.7,
        median_demand_per_lane=38.0,
        density_pct=163.2,
        fleet_total_vessels=263,
    )


@pytest.fixture
def small_signals():
    """Smallest valid synthetic Problem."""
    return ComplexitySignals(
        num_ports=10,
        num_lanes=150,
        total_demand_teu=20000.0,
        avg_demand_per_lane=133.3,
        median_demand_per_lane=100.0,
        density_pct=33.3,
        fleet_total_vessels=50,
    )


@pytest.fixture
def medium_signals():
    """Medium synthetic Problem."""
    return ComplexitySignals(
        num_ports=30,
        num_lanes=800,
        total_demand_teu=120000.0,
        avg_demand_per_lane=150.0,
        median_demand_per_lane=120.0,
        density_pct=58.8,
        fleet_total_vessels=150,
    )


@pytest.fixture
def large_signals():
    """Larger synthetic Problem."""
    return ComplexitySignals(
        num_ports=200,
        num_lanes=18000,
        total_demand_teu=3_000_000.0,
        avg_demand_per_lane=166.7,
        median_demand_per_lane=120.0,
        density_pct=91.8,
        fleet_total_vessels=500,
    )


# ---------------------------------------------------------------------------
# 1. Deterministic budget calculation
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_signals_same_budget(self, worldsmall_signals):
        b1 = AdaptiveBudget.from_signals(worldsmall_signals)
        b2 = AdaptiveBudget.from_signals(worldsmall_signals)
        assert b1.sga_population_size == b2.sga_population_size
        assert b1.sga_max_generations == b2.sga_max_generations
        assert b1.filter_max_services == b2.filter_max_services
        assert b1.milp_transfer_pair_limit == b2.milp_transfer_pair_limit

    def test_log_content_deterministic(self, worldsmall_signals):
        b1 = AdaptiveBudget.from_signals(worldsmall_signals)
        b2 = AdaptiveBudget.from_signals(worldsmall_signals)
        assert b1.logs == b2.logs


# ---------------------------------------------------------------------------
# 2. Minimum / Maximum bounds
# ---------------------------------------------------------------------------

class TestBounds:
    def test_sga_bounds_worldsmall(self, worldsmall_signals):
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        assert _SGA_POP_MIN <= b.sga_population_size <= _SGA_POP_MAX
        assert _SGA_GEN_MIN <= b.sga_max_generations <= _SGA_GEN_MAX
        assert _SGA_STAG_MIN <= b.sga_stagnation_limit <= _SGA_STAG_MAX

    def test_frequency_ga_bounds_worldsmall(self, worldsmall_signals):
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        assert _FREQ_POP_MIN <= b.freq_population_size <= _FREQ_POP_MAX
        assert _FREQ_GEN_MIN <= b.freq_max_generations <= _FREQ_GEN_MAX
        assert _FREQ_STAG_MIN <= b.freq_stagnation_limit <= _FREQ_STAG_MAX

    def test_filter_cap_bounds_worldsmall(self, worldsmall_signals):
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        assert _FILTER_CAP_MIN <= b.filter_max_services <= _FILTER_CAP_MAX

    def test_milp_bounds_worldsmall(self, worldsmall_signals):
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        assert _MILP_XFER_MIN <= b.milp_transfer_pair_limit <= _MILP_XFER_MAX
        assert _MILP_TIME_MIN <= b.milp_time_limit_sec <= _MILP_TIME_MAX

    def test_all_bound_types(self, small_signals, worldsmall_signals, large_signals):
        for signals in [small_signals, worldsmall_signals, large_signals]:
            b = AdaptiveBudget.from_signals(signals)
            # SGA
            assert _SGA_POP_MIN <= b.sga_population_size <= _SGA_POP_MAX
            assert _SGA_GEN_MIN <= b.sga_max_generations <= _SGA_GEN_MAX
            # FreqGA
            assert _FREQ_POP_MIN <= b.freq_population_size <= _FREQ_POP_MAX
            assert _FREQ_GEN_MIN <= b.freq_max_generations <= _FREQ_GEN_MAX
            # Filter
            assert _FILTER_CAP_MIN <= b.filter_max_services <= _FILTER_CAP_MAX
            # MILP
            assert _MILP_XFER_MIN <= b.milp_transfer_pair_limit <= _MILP_XFER_MAX
            assert _MILP_TIME_MIN <= b.milp_time_limit_sec <= _MILP_TIME_MAX


# ---------------------------------------------------------------------------
# 3. No zero values produced
# ---------------------------------------------------------------------------

class TestNoZeroValues:
    def test_no_zero_sga_values(self, worldsmall_signals):
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        assert b.sga_population_size > 0
        assert b.sga_max_generations > 0
        assert b.sga_stagnation_limit > 0

    def test_no_zero_frequency_ga_values(self, worldsmall_signals):
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        assert b.freq_population_size > 0
        assert b.freq_max_generations > 0
        assert b.freq_stagnation_limit > 0

    def test_no_zero_filter_values(self, worldsmall_signals):
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        assert b.filter_max_services > 0

    def test_no_zero_milp_values(self, worldsmall_signals):
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        assert b.milp_transfer_pair_limit > 0
        assert b.milp_time_limit_sec > 0

    def test_small_instance_no_zeros(self, small_signals):
        b = AdaptiveBudget.from_signals(small_signals)
        assert b.sga_population_size > 0
        assert b.sga_max_generations > 0
        assert b.filter_max_services > 0
        assert b.milp_transfer_pair_limit > 0
        assert b.milp_time_limit_sec > 0


# ---------------------------------------------------------------------------
# 4. Monotonic behavior where mathematically expected
# ---------------------------------------------------------------------------

class TestMonotonicBehavior:
    def test_smaller_instance_gets_smaller_or_equal_budgets(self, small_signals, worldsmall_signals):
        b_small = AdaptiveBudget.from_signals(small_signals)
        b_ws = AdaptiveBudget.from_signals(worldsmall_signals)
        # Smaller instance should not get a larger budget
        assert b_small.sga_population_size <= b_ws.sga_population_size
        assert b_small.sga_max_generations <= b_ws.sga_max_generations
        assert b_small.filter_max_services <= b_ws.filter_max_services
        assert b_small.milp_transfer_pair_limit <= b_ws.milp_transfer_pair_limit

    def test_medium_between_small_and_large(self, small_signals, medium_signals, large_signals):
        b_s = AdaptiveBudget.from_signals(small_signals)
        b_m = AdaptiveBudget.from_signals(medium_signals)
        b_l = AdaptiveBudget.from_signals(large_signals)
        # Medium should fall between small and large for SGA pop
        assert b_s.sga_population_size <= b_m.sga_population_size <= b_l.sga_population_size
        # And for filter cap
        assert b_s.filter_max_services <= b_m.filter_max_services <= b_l.filter_max_services


# ---------------------------------------------------------------------------
# 5. Region-specific adaptation
# ---------------------------------------------------------------------------

class TestRegionSpecificAdaptation:
    def test_different_regions_different_budgets(self):
        region_a = ComplexitySignals(
            num_ports=20, num_lanes=500, total_demand_teu=50000,
            avg_demand_per_lane=100.0, median_demand_per_lane=80.0,
            density_pct=27.0, fleet_total_vessels=100,
        )
        region_b = ComplexitySignals(
            num_ports=20, num_lanes=1000, total_demand_teu=100000,
            avg_demand_per_lane=100.0, median_demand_per_lane=80.0,
            density_pct=54.0, fleet_total_vessels=100,
        )
        ba = AdaptiveBudget.from_signals(region_a)
        bb = AdaptiveBudget.from_signals(region_b)
        assert ba.sga_population_size != bb.sga_population_size
        assert ba.filter_max_services != bb.filter_max_services

    def test_identical_region_same_budget(self):
        s = ComplexitySignals(
            num_ports=47, num_lanes=1764, total_demand_teu=276447,
            avg_demand_per_lane=156.7, median_demand_per_lane=38.0,
            density_pct=163.2, fleet_total_vessels=263,
        )
        b1 = AdaptiveBudget.from_signals(s)
        b2 = AdaptiveBudget.from_signals(s)
        assert b1.sga_population_size == b2.sga_population_size


# ---------------------------------------------------------------------------
# 6. Service-count adaptation
# ---------------------------------------------------------------------------

class TestServiceCountAdaptation:
    def test_direct_target_scales_with_complexity(self, small_signals, worldsmall_signals, large_signals):
        b_s = AdaptiveBudget.from_signals(small_signals)
        b_ws = AdaptiveBudget.from_signals(worldsmall_signals)
        b_l = AdaptiveBudget.from_signals(large_signals)
        assert b_s.direct_target <= b_ws.direct_target <= b_l.direct_target
        assert b_s.hub_loop_target <= b_ws.hub_loop_target <= b_l.hub_loop_target
        assert b_s.feeder_target <= b_ws.feeder_target <= b_l.feeder_target
        assert b_s.heuristic_target <= b_ws.heuristic_target <= b_l.heuristic_target


# ---------------------------------------------------------------------------
# 7. Active-service adaptation (FrequencyGA depends on active search space)
# ---------------------------------------------------------------------------

class TestActiveServiceAdaptation:
    def test_freq_ga_budget_scales_with_lanes(self, small_signals, worldsmall_signals, large_signals):
        b_s = AdaptiveBudget.from_signals(small_signals)
        b_ws = AdaptiveBudget.from_signals(worldsmall_signals)
        b_l = AdaptiveBudget.from_signals(large_signals)
        assert b_s.freq_population_size <= b_ws.freq_population_size <= b_l.freq_population_size
        assert b_s.freq_max_generations <= b_ws.freq_max_generations <= b_l.freq_max_generations


# ---------------------------------------------------------------------------
# 8. MILP workload adaptation
# ---------------------------------------------------------------------------

class TestMilpWorkloadAdaptation:
    def test_milp_workload_scales_with_complexity(self, small_signals, worldsmall_signals, large_signals):
        b_s = AdaptiveBudget.from_signals(small_signals)
        b_ws = AdaptiveBudget.from_signals(worldsmall_signals)
        b_l = AdaptiveBudget.from_signals(large_signals)
        assert b_s.milp_transfer_pair_limit <= b_ws.milp_transfer_pair_limit <= b_l.milp_transfer_pair_limit
        assert b_s.milp_time_limit_sec <= b_ws.milp_time_limit_sec <= b_l.milp_time_limit_sec

    def test_milp_params_accessible(self, worldsmall_signals):
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        params = get_milp_params(b)
        assert "max_transfer_pairs" in params
        assert "time_limit" in params
        assert params["max_transfer_pairs"] > 0
        assert params["time_limit"] > 0


# ---------------------------------------------------------------------------
# 9. LLM independence — budgets don't depend on LLM output
# ---------------------------------------------------------------------------

class TestLlmIndependence:
    def test_budget_does_not_depend_on_llm_state(self, worldsmall_signals):
        """Building a budget should succeed even without any LLM being available."""
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        assert b.sga_population_size > 0
        assert b.filter_max_services > 0

    def test_multiple_runs_without_llm(self, small_signals, medium_signals):
        for signals in [small_signals, medium_signals]:
            b1 = AdaptiveBudget.from_signals(signals)
            b2 = AdaptiveBudget.from_signals(signals)
            assert b1.sga_population_size == b2.sga_population_size
            assert b1.filter_max_services == b2.filter_max_services


# ---------------------------------------------------------------------------
# 10. Accessor functions work correctly
# ---------------------------------------------------------------------------

class TestAccessorFunctions:
    def test_get_service_generation_params(self, worldsmall_signals):
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        p = get_service_generation_params(b)
        assert p["direct_target"] > 0
        assert p["hub_loop_target"] > 0
        assert p["feeder_target"] > 0
        assert p["heuristic_target"] > 0
        assert p["trunk_target"] > 0
        assert p["candidate_cap"] > 0

    def test_get_filter_params(self, worldsmall_signals):
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        p = get_filter_params(b)
        assert "max_services" in p
        assert p["max_services"] > 0

    def test_get_service_ga_params(self, worldsmall_signals):
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        p = get_service_ga_params(b)
        assert "pop_size" in p
        assert "generations" in p
        assert "stagnation_limit" in p
        assert p["pop_size"] > 0
        assert p["generations"] > 0

    def test_get_frequency_ga_params(self, worldsmall_signals):
        b = AdaptiveBudget.from_signals(worldsmall_signals)
        p = get_frequency_ga_params(b)
        assert "pop_size" in p
        assert "generations" in p
        assert "stagnation_limit" in p
        assert p["pop_size"] > 0
        assert p["generations"] > 0


# ---------------------------------------------------------------------------
# 11. Edge cases — empty demands
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_compute_signals_empty_demands(self):
        cs = compute_complexity_signals(num_ports=47, demands=[], fleet=None)
        assert cs.num_ports == 47
        assert cs.num_lanes == 0
        assert cs.total_demand_teu == 0.0

    def test_budget_from_empty_signals(self):
        """A budget can be built from minimal signals without crashing."""
        cs = ComplexitySignals(num_ports=5, num_lanes=10, total_demand_teu=1000.0,
                               avg_demand_per_lane=100.0, median_demand_per_lane=100.0,
                               density_pct=5.3, fleet_total_vessels=10)
        b = AdaptiveBudget.from_signals(cs)
        assert b.sga_population_size > 0
        assert b.filter_max_services > 0
