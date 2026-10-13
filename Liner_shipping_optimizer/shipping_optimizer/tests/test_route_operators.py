"""
Task 21: time-feasible class correction in the class screening, route-level operators and
elitism.  All fixtures are SYNTHETIC with hand-computed values (see test_multi_hop_paths.py for
the network: A-B 1,000 nm, B-C 600 nm, C-D 800 nm, 288 nm/day at 12 kn).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.economics import DEFAULT_ASSUMPTIONS
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem
from src.services.class_screening import (
    ClassScreener, ClassScreeningConfig, WHY_TIME_FEASIBLE, config_from_environment as screen_cfg,
)
from src.services.route_operators import (
    RouteOperatorConfig, config_from_environment as ro_cfg, generate_operator_rotations,
)

DM = {
    "A": {"B": 1000.0, "C": 1600.0, "D": 2400.0},
    "B": {"A": 1000.0, "C": 600.0, "D": 1400.0},
    "C": {"A": 1600.0, "B": 600.0, "D": 800.0},
    "D": {"A": 2400.0, "B": 1400.0, "C": 800.0},
}


def cls(name, cap, design, tc=8000.0, qty=10):
    return FleetClass(vessel_class=name, quantity=qty, capacity_teu=cap, tc_rate_daily=tc,
                      min_speed=design - 2.0, design_speed=design, max_speed=design + 2.0,
                      bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0)


def problem(demands, classes):
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0,
                  transshipment_cost=0.0, variable_port_call_cost=0.0) for p in "ABCD"]
    return Problem(ports=ports, services=[], demands=demands, distance_matrix=DM,
                   fleet=Fleet(classes=classes))


# ===================================================================== A. configuration
class TestConfig:
    def test_defaults(self):
        assert not ro_cfg({}).enabled                      # operators / elitism: opt-in
        assert screen_cfg({}).time_feasible                # the correction is the default (Task 21)
        assert not screen_cfg({"LINER_CLASS_TIME_FEASIBLE": "0"}).time_feasible    # rollback
        # it only acts while the class screening itself is on
        assert not screen_cfg({"LINER_CLASS_SCREEN": "0"}).enabled

    def test_values(self):
        c = ro_cfg({"LINER_ROUTE_OPERATORS": "30", "LINER_ELITISM": "1"})
        assert c.budget == 30 and c.elitism and c.enabled
        assert screen_cfg({"LINER_CLASS_TIME_FEASIBLE": "1"}).time_feasible
        # the Task 10 switch keeps its meaning
        assert screen_cfg({"LINER_CLASS_SCREEN": "0", "LINER_CLASS_TIME_FEASIBLE": "1"}).k == 0

    @pytest.mark.parametrize("env", [{"LINER_ROUTE_OPERATORS": "-1"}, {"LINER_ROUTE_OPERATORS": "x"},
                                     {"LINER_ELITISM": "maybe"}])
    def test_malformed_route_operator_values_raise(self, env):
        with pytest.raises(ValueError):
            ro_cfg(env)

    def test_malformed_time_feasible_value_raises(self):
        with pytest.raises(ValueError):
            screen_cfg({"LINER_CLASS_TIME_FEASIBLE": "2"})


# ============================================================ B. time-feasible class screening
class TestTimeFeasibleClass:
    """A->B must arrive in 4 days: 1,000 nm needs 3.47 d at 12 kn but 6.5 d at 8 kn.  Revenue is
    too low for any class to be profitable stand-alone, so the legacy (nearest-capacity) class
    is kept - and that class cannot meet the limit."""

    def _screener(self, time_feasible):
        d = [Demand("A", "B", 100.0, 30.0, max_transit_days=4.0)]
        pr = problem(d, [cls("Slow", 500.0, 8.0), cls("Fast", 2000.0, 12.0)])
        return ClassScreener(pr, pr.fleet, DEFAULT_ASSUMPTIONS,
                             ClassScreeningConfig(k=1, time_feasible=time_feasible))

    def test_task10_behaviour_keeps_the_class_that_cannot_carry_anything(self):
        sel = self._screener(False).screen(["A", "B"], 500.0).selected
        assert [e.vessel_class for e in sel] == ["Slow"]
        assert sel[0].direct_ride_feasible_ods == 0

    def test_time_feasible_correction_offers_the_class_that_can(self):
        sel = self._screener(True).screen(["A", "B"], 500.0).selected
        assert [e.vessel_class for e in sel] == ["Fast"]
        assert sel[0].selected_because == WHY_TIME_FEASIBLE
        assert sel[0].direct_ride_feasible_teu == pytest.approx(100.0)

    def test_a_profitable_rotation_is_not_touched(self):
        d = [Demand("A", "B", 1500.0, 3000.0, max_transit_days=20.0)]
        pr = problem(d, [cls("Slow", 500.0, 8.0), cls("Fast", 2000.0, 12.0)])
        for tf in (False, True):
            scr = ClassScreener(pr, pr.fleet, DEFAULT_ASSUMPTIONS, ClassScreeningConfig(k=1, time_feasible=tf))
            assert [e.vessel_class for e in scr.screen(["A", "B"], 500.0).selected] == \
                   [e.vessel_class for e in
                    ClassScreener(pr, pr.fleet, DEFAULT_ASSUMPTIONS, ClassScreeningConfig(k=1))
                    .screen(["A", "B"], 500.0).selected]

    def test_the_legacy_class_is_kept_when_it_can_carry_cargo(self):
        d = [Demand("A", "B", 100.0, 30.0, max_transit_days=40.0)]       # both classes meet 40 d
        pr = problem(d, [cls("Slow", 500.0, 8.0), cls("Fast", 2000.0, 12.0)])
        scr = ClassScreener(pr, pr.fleet, DEFAULT_ASSUMPTIONS, ClassScreeningConfig(k=1, time_feasible=True))
        assert [e.vessel_class for e in scr.screen(["A", "B"], 500.0).selected] == ["Slow"]


# ============================================================================ C. operators
class TestOperators:
    CLASSES = [cls("M", 1000.0, 12.0), cls("L", 3000.0, 14.0)]

    def _setup(self):
        d = [Demand("A", "B", 800.0, 3000.0, max_transit_days=30.0),
             Demand("B", "C", 700.0, 3000.0, max_transit_days=30.0),
             Demand("C", "D", 600.0, 3000.0, max_transit_days=30.0),
             Demand("A", "D", 500.0, 3000.0, max_transit_days=30.0),
             Demand("B", "D", 400.0, 3000.0, max_transit_days=30.0)]
        return problem(d, self.CLASSES)

    def test_disabled_configuration_produces_nothing(self):
        pr = self._setup()
        out, rep = generate_operator_rotations(pr, pr.fleet, [], RouteOperatorConfig())
        assert out == [] and not rep.elites_in

    def test_variants_are_new_feasible_and_bounded(self):
        pr = self._setup()
        existing = [(["A", "B"], "M")]
        cfg = RouteOperatorConfig(budget=6)
        out, rep = generate_operator_rotations(pr, pr.fleet, existing, cfg,
                                               elite_pool=[(["A", "B"], "M")])
        assert 0 < len(out) <= 6
        keys = {(tuple(p.ports), p.vessel_class) for p in out}
        assert len(keys) == len(out)                                   # no duplicates
        assert (("A", "B"), "M") not in keys                           # not an existing rotation
        assert {p.operator for p in out} <= {"insert", "remove", "swap", "reclass"}
        assert all(len(set(p.ports)) == len(p.ports) >= 2 for p in out)
        assert rep.variants_evaluated >= len(out)
        # reclass of the elite onto the other class and insertion of a port are both offered
        ops = {p.operator for p in out}
        assert "reclass" in ops and "insert" in ops

    def test_deterministic(self):
        pr = self._setup()
        cfg = RouteOperatorConfig(budget=8)
        a, _ = generate_operator_rotations(pr, pr.fleet, [(["A", "B"], "M")], cfg,
                                           elite_pool=[(["A", "B"], "M"), (["B", "C"], "M")])
        b, _ = generate_operator_rotations(pr, pr.fleet, [(["A", "B"], "M")], cfg,
                                           elite_pool=[(["A", "B"], "M"), (["B", "C"], "M")])
        assert [(p.ports, p.vessel_class, p.operator) for p in a] == \
               [(p.ports, p.vessel_class, p.operator) for p in b]

    def test_infeasible_variants_are_dropped_not_repaired(self):
        pr = self._setup()
        pr.fleet = Fleet(classes=[cls("M", 1000.0, 12.0, qty=1)])      # one vessel: long loops infeasible
        out, rep = generate_operator_rotations(pr, pr.fleet, [(["A", "B"], "M")],
                                               RouteOperatorConfig(budget=20),
                                               elite_pool=[(["A", "B"], "M")])
        from src.network.economics import build_service_model
        pl = {p.id: p for p in pr.ports}
        for p in out:
            m = build_service_model("t", list(p.ports), pr.fleet.get_class(p.vessel_class), DM, pl)
            assert m.max_departures() >= 1

    def test_elitism_reoffers_the_previous_networks_rotations_once(self):
        pr = self._setup()
        feedback = {"iteration": 0, "profit": 1.0,
                    "operated": [{"ports": ["A", "B", "C"], "vessel_class": "M", "frequency": 1},
                                 {"ports": ["A", "B"], "vessel_class": "M", "frequency": 1}],
                    "unserved_od_teu": {"A|D": 500.0}}
        existing = [(["A", "B"], "M")]                                  # the second elite is in the pool
        cfg = RouteOperatorConfig(elitism=True)
        out, rep = generate_operator_rotations(pr, pr.fleet, existing, cfg, feedback=feedback)
        assert [(p.ports, p.vessel_class, p.operator) for p in out] == [(("A", "B", "C"), "M", "elite")]
        assert rep.elites_from_feedback == 2 and rep.elites_reoffered == 1

    def test_unserved_demand_steers_the_insertion(self):
        pr = self._setup()
        fb = {"operated": [{"ports": ["A", "B"], "vessel_class": "M", "frequency": 1}],
              "unserved_od_teu": {"B|D": 400.0}}
        out, _ = generate_operator_rotations(pr, pr.fleet, [(["A", "B"], "M")],
                                             RouteOperatorConfig(budget=3), feedback=fb)
        inserted = [p for p in out if p.operator == "insert"]
        assert inserted and "D" in inserted[0].ports
