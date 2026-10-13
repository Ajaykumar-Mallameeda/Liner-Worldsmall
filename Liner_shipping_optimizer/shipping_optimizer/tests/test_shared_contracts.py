"""Shared data / unit / economic contract tests.

Part A -- fuel contract: fuel is derived from the canonical fleet specification
          (``fleet_data.csv``) at the class design speed, rotations are closed, and
          missing inputs raise instead of becoming zero.
Part B -- contracts that used to be DOCUMENTED DEFECTS (strict xfail) and are now
          ENFORCED on the network model:
              D-FUEL-TABLE   fuel table == fleet specification
              D-SVC-CAP      candidate capacity == its vessel class capacity
              D-SVC-CYCLE    cycle time covers the sailing time of the closed rotation
              D-CAP-FREQ     weekly capacity = capacity x departures per week
              D-ACCT-PROFIT  reported profit = revenue - total cost (penalty separate)
              D-ACCT-TRANSSHIP  transshipment priced at the port-specific rate
              D-MILP-FLEET   an unsustainable fleet is an explicit status, not a crash

Fixtures marked SYNTHETIC are hand-built with hand-computed expectations; the others
use the canonical WorldSmall data. No LLM or network access.

    vessel V : 1,000 TEU, design 12 kn (10-14), TC 8,000 USD/day, bunker 20 t/day,
               idle 2 t/day, 300 vessels;  price 600 USD/t; 24 h port stay
"""
import math
import random
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.network_loader import NetworkLoader
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem, Service
from src.utils import fuel_cost as fc
from src.utils.fuel_cost import (
    MissingDistanceError,
    UnknownVesselClassError,
    calculate_voyage_fuel_cost,
    calculate_weekly_fuel_cost,
)


def _fleet(qty=300, **kw):
    spec = dict(vessel_class="V", quantity=qty, capacity_teu=1000.0, tc_rate_daily=8000.0,
                min_speed=10.0, design_speed=12.0, max_speed=14.0,
                bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0)
    spec.update(kw)
    return Fleet(classes=[FleetClass(**spec)])


# SYNTHETIC fuel class "F": 16 kn, 15 t/day  ->  1000 nm = 2.604167 d = 39.0625 t = 23,437.50 USD
F16 = Fleet(classes=[FleetClass(vessel_class="F", quantity=1, capacity_teu=450.0, design_speed=16.0,
                                min_speed=10.0, max_speed=18.0,
                                bunker_consumption_tons_per_day=15.0)])
F_1000NM = 1000.0 / (16.0 * 24.0) * 15.0 * 600.0                # 23,437.50


# ===========================================================================
# Part A -- fuel cost contract
# ===========================================================================
class TestFuelCostContract:
    def test_voyage_known_value(self):
        assert calculate_voyage_fuel_cost(1000.0, "F", fleet=F16) == pytest.approx(F_1000NM, rel=1e-12)
        assert F_1000NM == pytest.approx(23_437.5)

    def test_voyage_is_linear_in_distance_and_price(self):
        base = calculate_voyage_fuel_cost(1000.0, "F", fleet=F16)
        assert calculate_voyage_fuel_cost(2500.0, "F", fleet=F16) == pytest.approx(2.5 * base)
        assert calculate_voyage_fuel_cost(1000.0, "F", bunker_price_per_ton=300.0, fleet=F16) == \
            pytest.approx(base / 2.0)

    def test_the_closing_leg_is_costed_exactly_once(self):
        dm = {"A": {"B": 1000.0}, "B": {"A": 1000.0}}
        open_form = calculate_weekly_fuel_cost(["A", "B"], dm, "F", 7, fleet=F16)
        closed_form = calculate_weekly_fuel_cost(["A", "B", "A"], dm, "F", 7, fleet=F16)
        assert open_form == closed_form == pytest.approx(2 * F_1000NM)      # 2,000 nm rotation

    def test_weekly_cost_is_rotation_fuel_times_rotations_per_week(self):
        dm = {"A": {"B": 1000.0}, "B": {"A": 1000.0}}
        assert calculate_weekly_fuel_cost(["A", "B"], dm, "F", 14, fleet=F16) == \
            pytest.approx(2 * F_1000NM * 7 / 14)

    def test_every_leg_of_a_three_port_rotation_counts(self):
        dm = {"A": {"B": 1000.0}, "B": {"C": 2000.0}, "C": {"A": 3000.0}}
        assert calculate_weekly_fuel_cost(["A", "B", "C"], dm, "F", 7, fleet=F16) == \
            pytest.approx(calculate_voyage_fuel_cost(6000.0, "F", fleet=F16))

    def test_same_port_consecutive_legs_are_zero_distance(self):
        dm = {"A": {"B": 1000.0}, "B": {"A": 1000.0}}
        assert calculate_weekly_fuel_cost(["A", "A", "B"], dm, "F", 7, fleet=F16) == \
            pytest.approx(calculate_weekly_fuel_cost(["A", "B"], dm, "F", 7, fleet=F16))

    def test_missing_distance_raises_and_invents_nothing(self):
        dm = {"A": {"B": 1000.0}}
        with pytest.raises(MissingDistanceError, match="B -> A"):       # the RETURN leg is missing
            calculate_weekly_fuel_cost(["A", "B"], dm, "F", 7, fleet=F16)
        with pytest.raises(MissingDistanceError, match="A -> Z"):
            calculate_weekly_fuel_cost(["A", "Z"], dm, "F", 7, fleet=F16)

    def test_unknown_vessel_class_raises_instead_of_a_default(self):
        dm = {"A": {"B": 1000.0}, "B": {"A": 1000.0}}
        with pytest.raises(UnknownVesselClassError, match="Nope"):
            calculate_voyage_fuel_cost(1000.0, "Nope", fleet=F16)
        with pytest.raises(UnknownVesselClassError):
            calculate_weekly_fuel_cost(["A", "B"], dm, "Nope", 7, fleet=F16)
        with pytest.raises(UnknownVesselClassError):
            fc.get_vessel_consumption_rate("Nope", fleet=F16)
        with pytest.raises(UnknownVesselClassError):
            fc.get_vessel_speed("Nope", fleet=F16)

    @pytest.mark.parametrize("cycle", [0, -7, float("nan")])
    def test_non_positive_cycle_time_raises(self, cycle):
        with pytest.raises(ValueError, match="cycle_time_days"):
            calculate_weekly_fuel_cost(["A", "B"], {"A": {"B": 1.0}, "B": {"A": 1.0}}, "F", cycle, fleet=F16)

    @pytest.mark.parametrize("dist", [-1.0, float("nan"), float("inf")])
    def test_invalid_distance_raises(self, dist):
        with pytest.raises(ValueError, match="distance_nm"):
            calculate_voyage_fuel_cost(dist, "F", fleet=F16)

    def test_route_with_fewer_than_two_ports_has_no_legs_and_costs_nothing(self):
        assert calculate_weekly_fuel_cost(["A"], {}, "F", 7, fleet=F16) == 0.0
        assert calculate_weekly_fuel_cost([], {}, "F", 7, fleet=F16) == 0.0

    def test_table_is_the_loaded_fleet_specification(self):
        """D-FUEL-TABLE: there is one source. Every class of the loaded fleet is in the
        table with exactly the fleet file's capacity, design speed and consumption."""
        fleet = NetworkLoader().load_fleet()
        assert set(fc.VESSEL_FUEL_CONSUMPTION) == {c.vessel_class for c in fleet.classes}
        for c in fleet.classes:
            t = fc.VESSEL_FUEL_CONSUMPTION[c.vessel_class]
            assert t["capacity"] == c.capacity_teu, c.vessel_class
            assert t["consumption_tons_per_day"] == pytest.approx(c.bunker_consumption_tons_per_day)
            assert t["idle_tons_per_day"] == pytest.approx(c.idle_consumption_tons_per_day)
            assert t["speed_knots"] == pytest.approx(c.design_speed)
            assert calculate_voyage_fuel_cost(1000.0, c.vessel_class) > 0.0

    def test_canonical_value_for_a_real_class(self):
        """Post_panamax: 16.5 kn, 82.2 t/day (fleet_data.csv)."""
        NetworkLoader().load_fleet()
        expected = 1000.0 / (16.5 * 24.0) * 82.2 * 600.0
        assert calculate_voyage_fuel_cost(1000.0, "Post_panamax") == pytest.approx(expected, rel=1e-12)

    def test_candidate_pool_contains_only_service_objects(self):
        from src.agents.service_generator_agent import ServiceGeneratorAgent

        loader = NetworkLoader()
        net = loader.load_network()
        problem = Problem(ports=net["ports"], services=[], demands=net["demands"],
                          distance_matrix=net["distance_matrix"], fleet=loader.load_fleet())
        random.seed(2024)
        np.random.seed(2024)
        pool = ServiceGeneratorAgent(name="contract", model="none").generate_services(problem)
        assert pool and all(isinstance(s, Service) for s in pool)
        assert len({s.id for s in pool}) == len(pool)
        assert all(isinstance(s.ports, list) and len(s.ports) >= 2 for s in pool)
        assert all(s.vessel_class in fc.VESSEL_FUEL_CONSUMPTION for s in pool)

    def test_full_worldsmall_matrix_never_needs_a_fallback_distance(self):
        net = NetworkLoader().load_network()
        dm = net["distance_matrix"]
        ids = [p.id for p in net["ports"]]
        assert all(b in dm[a] for a in ids for b in ids if a != b)


# ===========================================================================
# Part B -- former documented defects, now enforced
# ===========================================================================
@pytest.fixture(scope="module")
def ws_problem_and_candidates():
    """WorldSmall problem plus the production candidate pool (deterministic seed)."""
    from src.agents.service_generator_agent import ServiceGeneratorAgent

    loader = NetworkLoader()
    net = loader.load_network()
    fleet = loader.load_fleet()
    problem = Problem(ports=net["ports"], services=[], demands=net["demands"],
                      distance_matrix=net["distance_matrix"], fleet=fleet)
    random.seed(12345)
    np.random.seed(12345)
    services = ServiceGeneratorAgent(name="contract_audit", model="none").generate_services(problem)
    return problem, services


class TestEnforcedContracts:
    # --- D-SVC-CAP ----------------------------------------------------------
    def test_candidate_capacity_never_exceeds_the_largest_fleet_vessel(self, ws_problem_and_candidates):
        problem, services = ws_problem_and_candidates
        assert max(s.capacity for s in services) <= max(c.capacity_teu for c in problem.fleet.classes)

    def test_candidate_capacity_equals_its_vessel_class_capacity(self, ws_problem_and_candidates):
        problem, services = ws_problem_and_candidates
        cap = {c.vessel_class: c.capacity_teu for c in problem.fleet.classes}
        assert all(s.capacity == cap[s.vessel_class] for s in services)

    # --- D-SVC-CYCLE --------------------------------------------------------
    def test_cycle_time_covers_the_sailing_time_of_the_rotation(self, ws_problem_and_candidates):
        problem, services = ws_problem_and_candidates
        spec = {c.vessel_class: c for c in problem.fleet.classes}
        dm = problem.distance_matrix
        for s in services:
            legs = list(zip(s.ports, s.ports[1:]))
            if s.ports[0] != s.ports[-1]:
                legs.append((s.ports[-1], s.ports[0]))           # a rotation returns to its start
            nm = sum(dm[a][b] for a, b in legs if a != b)
            assert nm / (spec[s.vessel_class].max_speed * 24.0) <= s.cycle_time, s.id

    # --- D-CAP-FREQ ---------------------------------------------------------
    def test_weekly_capacity_is_capacity_times_departures_per_week(self):
        """A 14-day rotation sailed once a week needs 2 vessels and carries
        capacity x 1 = 1,000 TEU per week on its leg (not 1,000 x 7/14)."""
        from src.optimization.hub_milp import HubMILP

        # 3,200 nm round trip at 12 kn = 11.11 d + 2 port days -> declared 14 d
        problem = _tiny_problem(
            services=[Service(id="s", ports=["A", "B"], capacity=1000.0, weekly_cost=0.0,
                              vessel_class="V")],
            demands=[Demand("A", "B", 1000.0, 1000.0)],
            dist={"A": {"B": 1600.0}, "B": {"A": 1600.0}},
        )
        res = HubMILP(problem, {"services": [1], "frequencies": [1]}, time_limit=30).solve()
        assert res["status"] == "Optimal" and res["valid"]
        assert res["satisfied_demand"] == pytest.approx(1000.0, rel=1e-9)
        row = res["selected_services"][0]
        assert row["cycle_time_days"] == 14 and row["vessels"] == 2 and row["frequency_per_week"] == 1

    def test_capacity_per_leg_scales_with_departures(self):
        from src.optimization.hub_milp import HubMILP

        problem = _tiny_problem(
            services=[Service(id="s", ports=["A", "B"], capacity=1000.0, weekly_cost=0.0, vessel_class="V")],
            demands=[Demand("A", "B", 5000.0, 1000.0)],
            dist={"A": {"B": 1600.0}, "B": {"A": 1600.0}},
        )
        for f in (1, 2, 3):
            res = HubMILP(problem, {"services": [1], "frequencies": [f]}, time_limit=30).solve()
            assert res["satisfied_demand"] == pytest.approx(1000.0 * f, rel=1e-9), f

    def test_zero_frequency_is_not_operated_and_not_billed(self):
        from src.optimization.hub_milp import HubMILP

        problem = _tiny_problem(
            services=[Service(id="s", ports=["A", "B"], capacity=1000.0, weekly_cost=0.0, vessel_class="V")],
            demands=[Demand("A", "B", 100.0, 1000.0)],
        )
        res = HubMILP(problem, {"services": [1], "frequencies": [0]}, time_limit=30).solve()
        assert res["status"] == "Optimal"
        assert res["total_cost"] == 0.0 and res["satisfied_demand"] == 0.0
        assert res["vessels_by_class"] == {} and res["selected_services"] == []

    # --- D-ACCT-PROFIT ------------------------------------------------------
    def test_reported_profit_is_revenue_minus_total_cost(self):
        """A->B 1,000 nm, B->A 1,200 nm; demand 1,500 TEU at 1,000 USD, f = 1 (1,000 TEU
        per departure): revenue 1,000,000; vessels 2 x 56,000; fuel 94,066.67;
        port calls 2 x 1,000; handling 1,000 x (10 + 20)."""
        from src.optimization.hub_milp import HubMILP

        ports = [Port("A", "A", 0, 0, handling_cost=10.0, port_call_cost=1000.0),
                 Port("B", "B", 0, 0, handling_cost=20.0, port_call_cost=1000.0)]
        problem = _tiny_problem(
            ports=ports,
            services=[Service(id="s", ports=["A", "B"], capacity=1000.0, weekly_cost=0.0, vessel_class="V")],
            demands=[Demand("A", "B", 1500.0, 1000.0)],
            dist={"A": {"B": 1000.0}, "B": {"A": 1200.0}},
        )
        res = HubMILP(problem, {"services": [1], "frequencies": [1]}, time_limit=30).solve()
        fuel = (2200.0 / 288.0 * 20.0 + 2 * 2.0) * 600.0
        assert res["status"] == "Optimal"
        assert res["revenue"] == pytest.approx(1_000_000.0)
        assert res["cost"] == pytest.approx(112_000.0)                       # vessel hire
        assert res["fuel_cost"] == pytest.approx(fuel)
        assert res["total_cost"] == pytest.approx(112_000.0 + fuel + 2000.0 + 30_000.0, rel=1e-9)
        assert res["profit"] == pytest.approx(res["revenue"] - res["total_cost"], rel=1e-9)
        # the optimiser's own penalty is reported apart and is NOT part of profit
        assert res["unserved_penalty"] == pytest.approx(300.0 * 500.0)
        assert res["objective_value"] == pytest.approx(res["profit"] - res["unserved_penalty"], rel=1e-9)

    # --- D-ACCT-TRANSSHIP ---------------------------------------------------
    def test_transshipment_is_priced_at_the_port_specific_rate(self):
        from src.optimization.hub_milp import HubMILP

        ports = [Port(p, p, 0, 0, transshipment_cost=10.0, handling_cost=1.0, port_call_cost=0.0) for p in "ABC"]
        problem = _tiny_problem(
            ports=ports,
            services=[Service(id="s1", ports=["A", "B"], capacity=1000.0, weekly_cost=0.0, vessel_class="V"),
                      Service(id="s2", ports=["B", "C"], capacity=1000.0, weekly_cost=0.0, vessel_class="V")],
            demands=[Demand("A", "C", 100.0, 1000.0, max_transit_days=60.0)],
            dist={"A": {"B": 100.0, "C": 200.0}, "B": {"A": 100.0, "C": 100.0},
                  "C": {"A": 200.0, "B": 100.0}},
        )
        res = HubMILP(problem, {"services": [1, 1], "frequencies": [1, 1]}, time_limit=30).solve()
        assert res["status"] == "Optimal"
        assert res["transship_demand"] == pytest.approx(100.0)
        assert res["transship_cost"] == pytest.approx(100.0 * 10.0)        # hub B's own rate

    # --- D-MILP-FLEET -------------------------------------------------------
    def test_fleet_infeasible_chromosome_returns_an_explicit_status(self):
        """28-day rotation at 3 departures/week needs ceil(84/7) = 12 vessels; the fleet
        limit is 5. This used to raise a PuLP TypeError; it is an explicit status."""
        from src.optimization.hub_milp import HubMILP

        # 7,488 nm round trip at 12 kn = 26 d + 2 port days = 28 d
        problem = _tiny_problem(
            services=[Service(id="s", ports=["A", "B"], capacity=1000.0, weekly_cost=0.0, vessel_class="V")],
            demands=[Demand("A", "B", 10.0, 1000.0)],
            dist={"A": {"B": 3744.0}, "B": {"A": 3744.0}},
        )
        res = HubMILP(problem, {"services": [1], "frequencies": [3]}, fleet_size=5, time_limit=30).solve()
        assert res["status"] == "Infeasible"
        assert res["valid"] is False
        assert res["satisfied_demand"] == 0.0 and res["selected_services"] == []

    def test_class_inventory_is_enforced(self):
        from src.optimization.hub_milp import HubMILP

        problem = _tiny_problem(
            services=[Service(id="s", ports=["A", "B"], capacity=1000.0, weekly_cost=0.0, vessel_class="V")],
            demands=[Demand("A", "B", 10.0, 1000.0)],
            dist={"A": {"B": 3744.0}, "B": {"A": 3744.0}},
            fleet=_fleet(qty=5),
        )
        res = HubMILP(problem, {"services": [1], "frequencies": [3]}, time_limit=30).solve()   # needs 12
        assert res["status"] == "Infeasible" and res["valid"] is False

    def test_unmodellable_service_is_invalid_input_not_zero_cost(self):
        from src.optimization.hub_milp import HubMILP

        problem = _tiny_problem(
            services=[Service(id="s", ports=["A", "B"], capacity=1000.0, weekly_cost=0.0, vessel_class="Nope")],
            demands=[Demand("A", "B", 10.0, 1000.0)],
        )
        res = HubMILP(problem, {"services": [1], "frequencies": [1]}, time_limit=30).solve()
        assert res["status"] == "Invalid Input" and res["valid"] is False
        assert "unknown_vessel_class" in res["reasons"]


# ---------------------------------------------------------------------------
# helpers (SYNTHETIC)
# ---------------------------------------------------------------------------
def _tiny_problem(services, demands, ports=None, dist=None, fleet=None):
    ports = ports or [Port("A", "A", 0, 0, port_call_cost=1000.0), Port("B", "B", 0, 0, port_call_cost=1000.0)]
    if dist is None:
        dist = {"A": {"B": 1000.0}, "B": {"A": 1200.0}}
    all_ports = sorted({p.id for p in ports} | set(dist))
    dist = {a: dict(row) for a, row in dist.items()}
    return Problem(ports=ports, services=services, demands=demands, distance_matrix=dist,
                   fleet=fleet or _fleet())
