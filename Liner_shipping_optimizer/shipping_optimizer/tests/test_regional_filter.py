"""Task 16 - regional candidate filter: economics instead of a class-level guess.

The legacy filter keeps a candidate iff ``capacity x 0.5 x 150 USD > one vessel's weekly hire``
(a constant per vessel CLASS) and then ranks by ``capacity / hire`` (also a class constant),
so within a class the order is generation order and the cap drops the LAST generated small
candidates.  The economic filter ranks by the canonical stand-alone profit instead, names no
class, keeps loops exempt, and never invents a value for a candidate it cannot evaluate.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.regional_agent import RegionalAgent
from src.optimization.adaptive_budget import AdaptiveBudget, compute_complexity_signals
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem, Service
from src.services import regional_filter as rf


# --------------------------------------------------------------------------- pure selection
def _svc(i, ports, cls="C", section="direct"):
    # a unique extra port makes every rotation distinct (economics are cached per rotation+class)
    s = SimpleNamespace(id=f"s{i}", ports=list(ports) + [f"P{i}"], vessel_class=cls,
                        capacity=1000.0, weekly_cost=1.0)
    s.origin_section = section
    return s


CORR = {("A", "B"), ("C", "D")}


class TestSelectEconomic:
    def test_cap_keeps_the_best_economics_not_the_first_generated(self):
        sv = [_svc(i, ("A", "B")) for i in range(5)]
        profit = {"s0": -50.0, "s1": 100.0, "s2": -10.0, "s3": 300.0, "s4": -900.0}
        kept, loops, rep = rf.select_economic(sv, CORR, 3, lambda s: profit[s.id])
        assert [s.id for s in kept] == ["s1", "s2", "s3"]          # generation order preserved
        assert rep.cut_by_cap == 2 and rep.kept == 3 and rep.considered == 5
        assert rep.cut_standalone_profit_max <= rep.kept_standalone_profit_min

    def test_loss_making_candidates_are_not_dropped_while_the_cap_has_room(self):
        sv = [_svc(i, ("A", "B")) for i in range(3)]
        kept, _, rep = rf.select_economic(sv, CORR, 10, lambda s: -1e6)
        assert len(kept) == 3 and rep.cut_by_cap == 0

    def test_demand_loops_are_exempt_and_do_not_use_cap_slots(self):
        sv = [_svc(0, ("A", "B")), _svc(1, ("A", "B")), _svc(2, ("A", "B", "C"), section="demand_loop")]
        kept, loops, rep = rf.select_economic(sv, CORR, 1, lambda s: {"s0": 5.0, "s1": 9.0}.get(s.id, -1.0))
        assert [s.id for s in kept] == ["s1"] and [s.id for s in loops] == ["s2"]
        assert rep.demand_loops_exempt == 1

    def test_no_corridor_is_still_dropped_with_its_reason_counted(self):
        sv = [_svc(0, ("A", "C")), _svc(1, ("A", "B"))]
        kept, _, rep = rf.select_economic(sv, CORR, 5, lambda s: 1.0)
        assert [s.id for s in kept] == ["s1"] and rep.no_corridor == 1

    def test_unavailable_economics_is_ranked_last_and_counted_never_zero(self):
        sv = [_svc(0, ("A", "B")), _svc(1, ("A", "B")), _svc(2, ("A", "B"))]
        vals = {"s0": None, "s1": -5.0, "s2": -7.0}
        kept, _, rep = rf.select_economic(sv, CORR, 2, lambda s: vals[s.id])
        assert [s.id for s in kept] == ["s1", "s2"]        # -5 and -7 beat "unknown", not 0
        assert rep.economics_unavailable == 1

    def test_ties_keep_generation_order_and_the_result_is_deterministic(self):
        sv = [_svc(i, ("A", "B")) for i in range(6)]
        a = rf.select_economic(sv, CORR, 3, lambda s: 1.0)[0]
        b = rf.select_economic(sv, CORR, 3, lambda s: 1.0)[0]
        assert [s.id for s in a] == ["s0", "s1", "s2"] == [s.id for s in b]

    def test_no_class_is_named_or_treated_specially(self):
        # the same economics on two different class names give the same selection
        for name in ("Feeder_450", "Anything_Else"):
            sv = [_svc(i, ("A", "B"), cls=name) for i in range(3)]
            kept, _, _ = rf.select_economic(sv, CORR, 2, lambda s: {"s0": 1.0, "s1": 2.0, "s2": 3.0}[s.id])
            assert [s.id for s in kept] == ["s1", "s2"]


# --------------------------------------------------------------------------- mode switch
class TestMode:
    def test_auto_follows_the_task_9_10_generators(self):
        assert rf.filter_mode({}) == "economic"                         # defaults on
        assert rf.filter_mode({"LINER_REGIONAL_FILTER": "auto"}) == "economic"
        assert rf.filter_mode({"LINER_DEMAND_LOOP_BUDGET": "0", "LINER_CLASS_SCREEN": "0"}) == "legacy"
        assert rf.filter_mode({"LINER_DEMAND_LOOP_BUDGET": "0"}) == "economic"   # screening still on
        assert rf.filter_mode({"LINER_CLASS_SCREEN": "0"}) == "economic"         # loops still on

    def test_explicit_values_override_and_garbage_is_an_error(self):
        assert rf.filter_mode({"LINER_REGIONAL_FILTER": "legacy"}) == "legacy"
        assert rf.filter_mode({"LINER_REGIONAL_FILTER": "ECONOMIC", "LINER_DEMAND_LOOP_BUDGET": "0",
                               "LINER_CLASS_SCREEN": "0"}) == "economic"
        with pytest.raises(ValueError):
            rf.filter_mode({"LINER_REGIONAL_FILTER": "yes"})


# --------------------------------------------------------------------------- the agent
def _problem(services):
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0,
                  transshipment_cost=0.0, variable_port_call_cost=0.0) for p in "ABCD"]
    dm = {a: {b: (1000.0 if a != b else 0.0) for b in "ABCD"} for a in "ABCD"}

    def cls(name, cap, tc, qty=20):
        return FleetClass(vessel_class=name, quantity=qty, capacity_teu=cap, tc_rate_daily=tc,
                          min_speed=10.0, design_speed=12.0, max_speed=14.0,
                          bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0)
    fleet = Fleet(classes=[cls("SMALL", 500.0, 5000.0), cls("BIG", 3000.0, 40000.0)])
    demands = [Demand("A", "B", 900.0, 1000.0), Demand("B", "A", 600.0, 1000.0),
               Demand("C", "D", 20.0, 800.0)]
    pr = Problem(ports=ports, services=services, demands=demands, distance_matrix=dm, fleet=fleet)
    pr.port_catalog = {p.id: p for p in ports}
    return pr


def _service(i, ports, cls_name, cap, tc_daily, section="direct"):
    s = Service(id=f"r_svc_{i:03d}", ports=list(ports), capacity=cap, weekly_cost=tc_daily * 7.0,
                vessel_class=cls_name)
    s.origin_section = section
    return s


def _budget(problem, cap):
    b = AdaptiveBudget.from_signals(compute_complexity_signals(
        num_ports=len(problem.ports), demands=problem.demands, fleet=problem.fleet))
    b.filter_max_services = cap
    return b


class TestAgent:
    def _services(self):
        return [
            _service(0, "AB", "BIG", 3000.0, 40000.0),       # loses: a 3,000 TEU ship for 900 TEU
            _service(1, "AB", "SMALL", 500.0, 5000.0),       # profitable stand-alone
            _service(2, "CD", "BIG", 3000.0, 40000.0),       # loses heavily (20 TEU)
            _service(3, "CD", "SMALL", 500.0, 5000.0),       # loses a little
            _service(4, "AC", "SMALL", 500.0, 5000.0),       # no corridor
            _service(5, "ABC", "SMALL", 500.0, 5000.0, section="demand_loop"),
        ]

    def test_economic_filter_end_to_end(self, monkeypatch):
        monkeypatch.setenv("LINER_REGIONAL_FILTER", "economic")
        pr = _problem(self._services())
        agent = RegionalAgent("regional_x", "X", "none")
        out = agent._filter_services(pr, _budget(pr, 2))
        ids = [s.id for s in out.services]
        rep = agent.last_filter_report
        assert "r_svc_001" in ids                       # the profitable small ship
        assert "r_svc_005" in ids                       # the loop is exempt
        assert "r_svc_004" not in ids                   # no corridor
        assert len(ids) == 3                            # cap 2 + 1 exempt loop
        assert rep.no_corridor == 1 and rep.cut_by_cap == 2 and rep.demand_loops_exempt == 1
        # every kept candidate is at least as good as every candidate that was cut
        assert rep.cut_standalone_profit_max <= rep.kept_standalone_profit_min
        # the heavy loser (BIG on a 20-TEU corridor) is what the cap removes first
        assert "r_svc_002" not in ids

    def test_legacy_filter_is_unchanged_when_selected(self, monkeypatch):
        monkeypatch.setenv("LINER_REGIONAL_FILTER", "legacy")
        pr = _problem(self._services())
        out = RegionalAgent("regional_x", "X", "none")._filter_services(pr, _budget(pr, 3))
        # legacy: margin guess (capacity*75 > hire) passes SMALL (37,500 > 35,000) and BIG
        # (225,000 < 280,000 fails); then class ratio cap=3 on the survivors + the loop
        got = sorted(s.id for s in out.services)
        assert got == ["r_svc_001", "r_svc_003", "r_svc_005"]

    def test_economic_report_reconciles(self, monkeypatch):
        monkeypatch.setenv("LINER_REGIONAL_FILTER", "economic")
        pr = _problem(self._services())
        n = len(pr.services)
        agent = RegionalAgent("regional_x", "X", "none")
        out = agent._filter_services(pr, _budget(pr, 3))
        r = agent.last_filter_report
        assert r.candidates == n
        assert r.kept + r.cut_by_cap + r.no_corridor + r.demand_loops_exempt == n
        assert len(out.services) == r.kept + r.demand_loops_exempt
