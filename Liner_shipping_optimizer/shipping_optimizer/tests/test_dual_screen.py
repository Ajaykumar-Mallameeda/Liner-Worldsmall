"""Network marginal-value pricing of candidate services from LP duals (``src/network/dual_screen.py``, study tool).

A feeder with a negative STAND-ALONE profit can add network value through a transfer to an operated trunk; the dual price must
see it, a worthless service must price at zero, and the price must agree in sign with the actual LP increment.  SYNTHETIC."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.dual_screen import BaseLp, actual_incremental_bound, fleet_duals, price_candidate
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

DM = {"A": {"B": 1000.0, "C": 2000.0, "D": 1500.0}, "B": {"A": 1000.0, "C": 1000.0, "D": 700.0},
      "C": {"A": 2000.0, "B": 1000.0, "D": 900.0}, "D": {"A": 1500.0, "B": 700.0, "C": 900.0}}


def _problem():
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=500.0, transshipment_cost=20.0, variable_port_call_cost=0.0, draft=12.0)
             for p in "ABCD"]
    v = FleetClass(vessel_class="V", quantity=30, capacity_teu=1000.0, tc_rate_daily=6000.0, min_speed=10.0, design_speed=12.0,
                   max_speed=14.0, bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0)
    dem = [Demand("B", "C", 400.0, 900.0, max_transit_days=60.0),          # carried by the trunk
           Demand("A", "C", 300.0, 1000.0, max_transit_days=60.0),         # needs a feeder A -> B then the trunk
           Demand("A", "B", 10.0, 40.0, max_transit_days=60.0)]            # the feeder's only direct cargo: tiny, so stand-alone < 0
    return Problem(ports=ports, services=[], demands=dem, distance_matrix=DM, fleet=Fleet(classes=[v]))


TRUNK = Candidate("T", ("B", "C"), "V")
FEEDER = Candidate("F", ("A", "B"), "V")
USELESS = Candidate("X", ("A", "D"), "V")


def test_feeder_with_negative_standalone_has_positive_network_value():
    pr = _problem()
    planner = NetworkPlanner(pr)
    base = BaseLp(planner, [TRUNK])
    assert base.ok and base.operated, "the trunk is operated in the relaxation"
    # stand-alone: on its own (pool = the feeder only) the relaxation does not operate it - its direct cargo loses money
    alone = BaseLp(planner, [FEEDER])
    assert alone.ok and alone.operated == [] and alone.bound == pytest.approx(0.0, abs=1e-6)
    p = price_candidate(base, FEEDER)
    assert p["value_usd_per_week"] > 1000.0 and p["transfer_paths_used"] >= 1
    act = actual_incremental_bound(base, [TRUNK], FEEDER)
    assert act["delta_bound_usd_per_week"] > 1000.0
    assert p["value_usd_per_week"] == pytest.approx(act["delta_bound_usd_per_week"], rel=0.35)


def test_service_without_cargo_is_worth_nothing():
    base = BaseLp(NetworkPlanner(_problem()), [TRUNK])
    p = price_candidate(base, USELESS)
    assert p["value_usd_per_week"] <= 1e-6
    assert actual_incremental_bound(base, [TRUNK], USELESS)["delta_bound_usd_per_week"] <= 1e-3


def test_fleet_duals_are_non_negative_and_listed_per_class():
    base = BaseLp(NetworkPlanner(_problem()), [TRUNK, FEEDER])
    fd = fleet_duals(base.lp)
    assert set(fd) == {"V"} and fd["V"] >= -1e-9
