"""
Candidate-service feasibility (Task 3).

Part A -- the feasibility model on SYNTHETIC fixtures with hand-computed expected values
          (vessel "V12": 12 kn design, 10-14 kn range, 1,000 TEU, USD 8,000/day, 5 vessels).
Part B -- the production candidate pool on the canonical WorldSmall data, re-derived
          independently of the module under test.
No LLM or network access.
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
from src.services import service_feasibility as sf
from src.services.service_feasibility import (
    CandidateReport,
    PortTimeAssumptions,
    ServiceFeasibilityError,
    choose_vessel_class,
    evaluate_rotation,
    reassign_vessel_class,
    required_vessels,
    rotation_legs,
    rotation_ports,
)


# ---------------------------------------------------------------------------
# SYNTHETIC fixtures (not data)
# ---------------------------------------------------------------------------
def V(name="V12", qty=5, cap=1000.0, tc=8000.0, lo=10.0, design=12.0, hi=14.0):
    return FleetClass(vessel_class=name, quantity=qty, capacity_teu=cap, tc_rate_daily=tc,
                      min_speed=lo, design_speed=design, max_speed=hi)


DM2 = {"A": {"B": 1000.0}, "B": {"A": 1200.0}}                      # asymmetric, directed
DM3 = {"A": {"B": 500.0}, "B": {"C": 700.0}, "C": {"A": 900.0}}


# ===========================================================================
# A. Route closure and legs
# ===========================================================================
class TestClosedRotation:
    def test_open_and_explicitly_closed_forms_are_the_same_rotation(self):
        assert rotation_ports(["A", "B", "C"]) == ["A", "B", "C"]
        assert rotation_ports(["A", "B", "C", "A"]) == ["A", "B", "C"]

    def test_return_leg_is_included_exactly_once(self):
        expected = [("A", "B"), ("B", "C"), ("C", "A")]
        assert rotation_legs(["A", "B", "C"]) == expected
        assert rotation_legs(["A", "B", "C", "A"]) == expected

    def test_two_port_service_sails_each_direction_once(self):
        assert rotation_legs(["A", "B"]) == [("A", "B"), ("B", "A")]
        assert rotation_legs(["A", "B", "A"]) == [("A", "B"), ("B", "A")]

    def test_fewer_than_two_ports_have_no_legs(self):
        assert rotation_legs(["A"]) == [] and rotation_legs([]) == []
        assert rotation_legs(["A", "A"]) == []

    def test_distance_is_the_sum_of_directed_legs_including_the_return(self):
        f = evaluate_rotation(["A", "B"], V(), DM2)
        assert f.feasible and f.distance_nm == 2200.0            # 1000 + 1200, not 1000 or 2000
        assert f.legs == [("A", "B", 1000.0), ("B", "A", 1200.0)]
        g = evaluate_rotation(["A", "B", "C", "A"], V(), DM3)
        assert g.distance_nm == 2100.0 and len(g.legs) == 3


# ===========================================================================
# B. Time, cycle and vessels
# ===========================================================================
class TestCycleTime:
    def test_sailing_port_and_cycle_time_two_ports(self):
        f = evaluate_rotation(["A", "B"], V(), DM2)
        assert f.sailing_days == pytest.approx(2200.0 / (12.0 * 24.0))        # 7.6389
        assert f.port_days == pytest.approx(2.0)                              # 2 calls x 24 h
        assert f.cycle_days == pytest.approx(2200.0 / 288.0 + 2.0)            # 9.6389
        assert f.cycle_time_days == 10                                        # declared = ceil
        assert f.cycle_days_at_max_speed == pytest.approx(2200.0 / (14.0 * 24.0) + 2.0)

    def test_three_ports(self):
        f = evaluate_rotation(["A", "B", "C"], V(), DM3)
        assert f.sailing_days == pytest.approx(2100.0 / 288.0)
        assert f.port_days == pytest.approx(3.0)
        assert f.cycle_time_days == 11                                        # 10.2917 -> 11

    def test_port_time_assumption_is_explicit_and_configurable(self):
        base = evaluate_rotation(["A", "B"], V(), DM2)
        slow = evaluate_rotation(["A", "B"], V(), DM2, port_time=PortTimeAssumptions(48.0))
        assert slow.port_days == pytest.approx(4.0)
        assert slow.cycle_days == pytest.approx(base.cycle_days + 2.0)
        assert "assumed" in base.port_time_basis                              # not source data
        zero = evaluate_rotation(["A", "B"], V(), DM2, port_time=PortTimeAssumptions(0.0))
        assert zero.port_days == 0.0

    @pytest.mark.parametrize("hours", [-1.0, float("nan"), float("inf")])
    def test_invalid_port_time_is_rejected(self, hours):
        with pytest.raises(ServiceFeasibilityError):
            PortTimeAssumptions(hours)

    def test_speed_comes_from_the_vessel_class(self):
        fast = evaluate_rotation(["A", "B"], V(design=14.0), DM2)
        assert fast.sailing_days == pytest.approx(2200.0 / (14.0 * 24.0))
        assert fast.speed_knots == 14.0


class TestVesselRequirement:
    def test_ceiling_formula_examples(self):
        assert required_vessels(21, 1) == 3
        assert required_vessels(21, 2) == 6
        assert required_vessels(22, 1) == 4          # 22/7 = 3.14 -> 4
        assert required_vessels(7, 1) == 1
        assert required_vessels(1, 1) == 1

    def test_zero_frequency_needs_zero_vessels_not_one(self):
        assert required_vessels(21, 0) == 0

    @pytest.mark.parametrize("cycle", [0, -7, float("nan"), float("inf")])
    def test_invalid_cycle_time_raises(self, cycle):
        with pytest.raises(ServiceFeasibilityError):
            required_vessels(cycle, 1)

    @pytest.mark.parametrize("freq", [-1, 1.5, float("nan"), True])
    def test_invalid_frequency_raises(self, freq):
        with pytest.raises(ServiceFeasibilityError):
            required_vessels(14, freq)

    def test_candidate_vessel_requirements(self):
        f = evaluate_rotation(["A", "B"], V(), DM2)            # cycle 10 d
        assert f.required_vessels_one_departure == 2
        assert [f.required_vessels(k) for k in (0, 1, 2, 3)] == [0, 2, 3, 5]
        g = evaluate_rotation(["A", "B", "C"], V(), DM3)       # cycle 11 d
        assert [g.required_vessels(k) for k in (1, 2, 3)] == [2, 4, 5]

    def test_class_inventory_is_a_local_necessary_condition(self):
        ok = evaluate_rotation(["A", "B"], V(qty=2), DM2)       # needs 2, has 2
        assert ok.feasible
        bad = evaluate_rotation(["A", "B"], V(qty=1), DM2)      # needs 2, has 1
        assert not bad.feasible and bad.reasons == [sf.R_EXCEEDS_INVENTORY]


# ===========================================================================
# C. Rejections: explicit reasons, no substituted values
# ===========================================================================
class TestRejections:
    def test_missing_directed_distance(self):
        dm = {"A": {"B": 1000.0}}                               # B -> A absent
        f = evaluate_rotation(["A", "B"], V(), dm)
        assert not f.feasible and f.reasons == [sf.R_MISSING_DISTANCE]
        assert "B -> A" in " ".join(f.details)
        # nothing is invented: no distance, no time, no cycle
        assert f.distance_nm is None and f.cycle_days is None and f.cycle_time_days is None
        assert f.legs == []

    @pytest.mark.parametrize("bad", [0.0, -5.0, float("nan"), float("inf"), "far"])
    def test_invalid_distance(self, bad):
        f = evaluate_rotation(["A", "B"], V(), {"A": {"B": 1000.0}, "B": {"A": bad}})
        assert f.reasons == [sf.R_INVALID_DISTANCE]

    def test_unknown_port(self):
        f = evaluate_rotation(["A", "Z"], V(), DM2, known_ports={"A", "B"})
        assert sf.R_UNKNOWN_PORT in f.reasons and not f.feasible

    def test_too_few_and_repeated_ports(self):
        assert evaluate_rotation(["A"], V(), DM2).reasons == [sf.R_TOO_FEW_PORTS]
        assert evaluate_rotation(["A", "A"], V(), DM2).reasons == [sf.R_TOO_FEW_PORTS]
        f = evaluate_rotation(["A", "B", "A", "B"], V(), DM2)
        assert sf.R_REPEATED_PORT in f.reasons

    def test_unknown_vessel_class_is_not_replaced_by_a_default(self):
        f = evaluate_rotation(["A", "B"], None, DM2)
        assert f.reasons == [sf.R_UNKNOWN_CLASS] and f.cycle_time_days is None

    @pytest.mark.parametrize("kw", [
        dict(design=0.0), dict(design=15.0), dict(lo=13.0), dict(design=float("nan")),
    ])
    def test_invalid_speed(self, kw):
        f = evaluate_rotation(["A", "B"], V(**kw), DM2)
        assert sf.R_INVALID_SPEED in f.reasons and f.cycle_time_days is None

    def test_invalid_capacity_and_empty_class(self):
        assert sf.R_INVALID_CAPACITY in evaluate_rotation(["A", "B"], V(cap=0.0), DM2).reasons
        assert sf.R_NO_VESSELS in evaluate_rotation(["A", "B"], V(qty=0), DM2).reasons


class TestDeclaredCycleTime:
    """Cycle needed: 9.639 d at design speed, 8.548 d even at max speed."""

    def test_sufficient_declared_time_is_accepted(self):
        assert evaluate_rotation(["A", "B"], V(), DM2, declared_cycle_time_days=10).feasible

    def test_shorter_than_required_is_rejected(self):
        f = evaluate_rotation(["A", "B"], V(), DM2, declared_cycle_time_days=9)
        assert f.reasons == [sf.R_DECLARED_TOO_SHORT]

    def test_impossible_even_at_maximum_speed_is_rejected(self):
        f = evaluate_rotation(["A", "B"], V(), DM2, declared_cycle_time_days=8)
        assert f.reasons == [sf.R_IMPOSSIBLE_AT_MAX_SPEED]

    @pytest.mark.parametrize("bad", [0, -3, float("nan")])
    def test_malformed_declared_time_is_rejected(self, bad):
        f = evaluate_rotation(["A", "B"], V(), DM2, declared_cycle_time_days=bad)
        assert not f.feasible


# ===========================================================================
# D. Vessel-class selection and re-assignment
# ===========================================================================
class TestVesselClass:
    @pytest.fixture(scope="class")
    def fleet(self):
        return NetworkLoader().load_fleet()

    # Fleet capacities in TEU are 2 x the ``Capacity FFE`` column since Issue 1
    # (900 / 1600 / 2400 / 4800 / 8400 / 15000); the targets are the previous ones x 2,
    # so every case keeps its meaning (including the tie 1600 / 2400 -> the smaller class).
    @pytest.mark.parametrize("target, expected", [
        (200, "Feeder_450"), (900, "Feeder_450"), (2000, "Feeder_800"),   # tie 1600/2400 -> smaller
        (2402, "Panamax_1200"), (4000, "Panamax_2400"), (10000, "Post_panamax"),
        (16000, "Super_panamax"), (28000, "Super_panamax"),
    ])
    def test_nearest_capacity_class(self, fleet, target, expected):
        assert choose_vessel_class(target, fleet).vessel_class == expected

    def test_classes_without_vessels_are_not_eligible(self):
        fleet = Fleet(classes=[V("A", qty=0, cap=1000.0), V("B", qty=3, cap=5000.0)])
        assert choose_vessel_class(900, fleet).vessel_class == "B"

    def test_no_fleet_is_an_error_not_a_default(self):
        with pytest.raises(ServiceFeasibilityError):
            choose_vessel_class(1000, None)
        with pytest.raises(ServiceFeasibilityError):
            choose_vessel_class(1000, Fleet(classes=[]))
        with pytest.raises(ServiceFeasibilityError):
            choose_vessel_class(0, Fleet(classes=[V()]))

    def test_class_change_recomputes_everything_derived(self):
        fleet = Fleet(classes=[V("V12"), V("V20", cap=3000.0, tc=20000.0, lo=12.0, design=20.0, hi=22.0)])
        before = evaluate_rotation(["A", "B"], fleet.get_class("V12"), DM2)
        after = reassign_vessel_class(before, "V20", fleet, DM2)
        assert after.feasible and after.vessel_class == "V20"
        assert after.capacity_teu == 3000.0 and before.capacity_teu == 1000.0
        assert after.weekly_vessel_cost == 140000.0 and before.weekly_vessel_cost == 56000.0
        assert after.sailing_days == pytest.approx(2200.0 / (20.0 * 24.0))
        assert after.cycle_time_days == 7 and before.cycle_time_days == 10
        assert after.required_vessels_one_departure == 1 and before.required_vessels_one_departure == 2

    def test_reassignment_to_an_unknown_class_is_a_rejection(self):
        fleet = Fleet(classes=[V("V12")])
        before = evaluate_rotation(["A", "B"], fleet.get_class("V12"), DM2)
        after = reassign_vessel_class(before, "Nope", fleet, DM2)
        assert after.reasons == [sf.R_UNKNOWN_CLASS]

    def test_capacity_unit_status_is_propagated(self):
        assert evaluate_rotation(["A", "B"], V(), DM2).capacity_unit_status == "provisional"
        assert evaluate_rotation(["A", "B"], V(), DM2,
                                 capacity_unit_status="verified").capacity_unit_status == "verified"


class TestReport:
    def test_counts_reasons_and_legacy_cycle_consistency(self):
        r = CandidateReport()
        ok = evaluate_rotation(["A", "B"], V(), DM2)                     # cycle 9.64 d
        bad = evaluate_rotation(["A", "B"], V(), {"A": {"B": 1.0}})
        r.record("direct", ok, legacy_declared=7)                       # 7 < 9.64 -> inconsistent
        r.record("direct", ok, legacy_declared=14)                      # 14 >= 9.64 -> consistent
        r.record("feeder", bad, legacy_declared=7)
        d = r.to_dict()
        assert (d["generated"], d["accepted"], d["rejected"]) == (3, 2, 1)
        assert d["rejections_by_reason"] == {sf.R_MISSING_DISTANCE: 1}
        assert d["generated_by_section"] == {"direct": 2, "feeder": 1}
        assert d["accepted_by_class"] == {"V12": 2}
        assert d["legacy_cycle_time_checked"] == 2 and d["legacy_cycle_time_inconsistent"] == 1
        assert d["capacity_feasibility_is_conditional"] is True
        assert len(d["rejected_samples"]) == 1


# ===========================================================================
# E. Production pool on the canonical WorldSmall data
# ===========================================================================
@pytest.fixture(scope="module")
def ws():
    from src.agents.service_generator_agent import ServiceGeneratorAgent
    loader = NetworkLoader()
    net = loader.load_network()
    fleet = loader.load_fleet()
    problem = Problem(ports=net["ports"], services=[], demands=net["demands"],
                      distance_matrix=net["distance_matrix"], fleet=fleet)
    random.seed(12345)
    np.random.seed(12345)
    agent = ServiceGeneratorAgent(name="t3", model="none")
    pool = agent.generate_services(problem)
    return problem, pool, agent.last_candidate_report


class TestWorldSmallPool:
    def test_pool_is_service_objects_with_unique_ids(self, ws):
        _, pool, _ = ws
        assert pool and all(isinstance(s, Service) for s in pool)
        assert len({s.id for s in pool}) == len(pool)

    def test_capacity_and_class_come_from_the_fleet(self, ws):
        problem, pool, _ = ws
        cap = {c.vessel_class: c.capacity_teu for c in problem.fleet.classes}
        assert all(s.vessel_class in cap for s in pool)
        assert all(s.capacity == cap[s.vessel_class] for s in pool)
        assert max(s.capacity for s in pool) <= max(cap.values())

    def test_every_service_is_independently_consistent(self, ws):
        """Re-derive route closure, time, cycle and vessels without the module under test."""
        problem, pool, _ = ws
        spec = {c.vessel_class: c for c in problem.fleet.classes}
        dm = problem.distance_matrix
        for s in pool:
            ports = list(s.ports[:-1] if len(s.ports) > 1 and s.ports[0] == s.ports[-1] else s.ports)
            assert len(ports) >= 2 and len(set(ports)) == len(ports), s.id
            nm = sum(dm[ports[i]][ports[(i + 1) % len(ports)]] for i in range(len(ports)))
            c = spec[s.vessel_class]
            cycle = nm / (c.design_speed * 24.0) + len(ports) * 1.0       # 24 h per call
            assert s.distance_nm == pytest.approx(nm), s.id
            assert s.cycle_time == math.ceil(round(cycle, 9)), s.id
            assert s.cycle_time + 1e-9 >= nm / (c.max_speed * 24.0), s.id  # sailable at max speed
            assert s.required_vessels == math.ceil(s.cycle_time / 7.0), s.id
            assert s.required_vessels <= c.quantity, s.id                   # one departure/week
            assert s.weekly_cost == c.tc_rate_daily * 7.0, s.id
            assert s.speed == c.design_speed, s.id
            assert s.capacity_unit_status == "reference_code", s.id

    def test_report_is_arithmetically_consistent(self, ws):
        _, pool, rep = ws
        d = rep.to_dict()
        assert d["generated"] == d["accepted"] + d["rejected"]
        assert d["accepted"] == len(pool)
        assert sum(d["generated_by_section"].values()) == d["generated"]
        assert sum(d["accepted_by_section"].values()) == d["accepted"]
        assert sum(d["accepted_by_class"].values()) == d["accepted"]
        assert all(d["accepted_by_section"].get(k, 0) <= v for k, v in d["generated_by_section"].items())
        # (the rejection paths themselves are exercised by the synthetic tests above)
        assert sum(d["rejections_by_reason"].values()) >= d["rejected"]
        assert set(d["rejections_by_reason"]) <= set(sf.ALL_REASONS)
        assert d["capacity_unit_status"] == "reference_code"
        assert d["capacity_feasibility_is_conditional"] is True

    def test_long_loops_fall_back_to_a_class_with_enough_vessels(self, ws):
        """A loop needing more vessels than the nearest-capacity class owns is re-tried
        with the next-nearest class instead of being dropped."""
        _, pool, rep = ws
        assert rep.class_fallbacks > 0
        assert rep.accepted_by_section["hub_loop"] == rep.generated_by_section["hub_loop"]
        # nothing in the pool needs more vessels than its class owns, fallback or not
        spec = {c.vessel_class: c.quantity for c in ws[0].fleet.classes}
        assert all(s.required_vessels <= spec[s.vessel_class] for s in pool)

    def test_legacy_declared_cycle_times_were_mostly_too_short(self, ws):
        """The 7/14/21-day constants cannot cover the derived requirement for most routes."""
        _, _, rep = ws
        d = rep.to_dict()
        assert d["legacy_cycle_time_checked"] > 0
        assert d["legacy_cycle_time_inconsistent"] / d["legacy_cycle_time_checked"] > 0.5

    def test_generation_is_deterministic_for_a_seed(self, ws):
        from src.agents.service_generator_agent import ServiceGeneratorAgent
        problem, pool, _ = ws
        random.seed(12345)
        np.random.seed(12345)
        again = ServiceGeneratorAgent(name="t3b", model="none").generate_services(problem)
        key = lambda p: [(s.ports, s.vessel_class, s.cycle_time, s.capacity) for s in p]
        assert key(again) == key(pool)


class TestGeneratorInputs:
    def test_fleetless_problem_is_an_explicit_error(self):
        from src.agents.service_generator_agent import ServiceGeneratorAgent
        p = Problem(ports=[Port("A", "A", 0, 0), Port("B", "B", 0, 0)], services=[],
                    demands=[Demand("A", "B", 10.0, 100.0)], distance_matrix=DM2)
        with pytest.raises(ServiceFeasibilityError, match="fleet"):
            ServiceGeneratorAgent(name="t3c", model="none").generate_services(p)

    def test_missing_distance_in_a_synthetic_network_rejects_not_invents(self):
        """SYNTHETIC 4-port network where the directed pair P4 -> P1 does not exist."""
        from src.agents.service_generator_agent import ServiceGeneratorAgent
        ids = ["P1", "P2", "P3", "P4"]
        dm = {a: {b: 100.0 for b in ids if b != a} for a in ids}
        del dm["P4"]["P1"]
        demands = [Demand("P1", "P4", 5000.0, 100.0), Demand("P1", "P2", 800.0, 100.0),
                   Demand("P2", "P3", 700.0, 100.0), Demand("P3", "P1", 600.0, 100.0)]
        fleet = Fleet(classes=[V("S_small", qty=50, cap=1500.0), V("S_big", qty=20, cap=6000.0)])
        p = Problem(ports=[Port(i, i, 0.0, 0.0) for i in ids], services=[],
                    demands=demands, distance_matrix=dm, fleet=fleet)
        random.seed(1)
        agent = ServiceGeneratorAgent(name="t3d", model="none")
        pool = agent.generate_services(p)
        rep = agent.last_candidate_report.to_dict()
        assert rep["rejections_by_reason"].get(sf.R_MISSING_DISTANCE, 0) >= 1
        assert pool, "services that do not need the missing pair must still be generated"
        for s in pool:                       # every accepted rotation uses only existing legs
            for a, b in rotation_legs(s.ports):
                assert b in dm[a], (s.id, a, b)
