"""Service-cost ownership between regions that proposed the same rotation.

The regional split of cost is an accounting partition (cargo -> origin region, a
service's vessel/fuel/port-call cost -> a region that PROPOSED it). When several
regions proposed the same rotation and class, the cost goes to the one whose own
cargo uses the service most (tie: the first proposer). Network totals never change.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.reconcile import collect_candidates, collect_candidates_with_proposers, reconcile
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem


def _problem():
    ports = [Port(p, p, 0, 0, port_call_cost=1000.0) for p in "ABC"]
    fleet = Fleet(classes=[FleetClass("V", 10, 1000.0, 8000.0, min_speed=10, design_speed=12, max_speed=14,
                                      bunker_consumption_tons_per_day=20.0,
                                      idle_consumption_tons_per_day=2.0)])
    dm = {"A": {"B": 1000.0, "C": 1500.0}, "B": {"A": 1000.0, "C": 800.0}, "C": {"A": 1500.0, "B": 800.0}}
    demands = [Demand("A", "B", 100.0, 1000.0), Demand("B", "A", 900.0, 1000.0)]
    return Problem(ports=ports, services=[], demands=demands, distance_matrix=dm, fleet=fleet)


def _pools():
    # both regions propose the same A-B rotation (listed in a different order)
    return {"First": [{"id": "first_svc_1", "ports": ["A", "B"], "vessel_class": "V"}],
            "Second": [{"id": "second_svc_1", "ports": ["B", "A"], "vessel_class": "V"}]}


def test_collect_candidates_keeps_the_legacy_signature_and_first_proposer():
    cands, owner = collect_candidates(_pools())
    assert len(cands) == 1 and owner[cands[0].service_id] == "First"


def test_all_proposers_are_recorded():
    cands, owner, proposers = collect_candidates_with_proposers(_pools())
    assert proposers[cands[0].service_id] == ["First", "Second"]


def test_service_cost_goes_to_the_region_whose_cargo_uses_it_most():
    # the 900-TEU flow originates in B (region Second), the 100-TEU flow in A (First)
    region_of_od = {("A", "B"): "First", ("B", "A"): "Second"}
    out = reconcile(_problem(), _pools(), region_of_od, ["First", "Second"], time_limit_sec=30)
    assert out.ok, out.message
    first, second = out.region_updates["First"], out.region_updates["Second"]
    assert second["services_selected"] == 1 and first["services_selected"] == 0
    assert second["operating_cost"] > 0 and first["operating_cost"] == 0
    # network totals are unaffected by who owns the service
    led = out.network_ledger["weekly_usd"]
    assert first["total_cost"] + second["total_cost"] == pytest.approx(led["total_operating_cost"])
    assert first["weekly_profit"] + second["weekly_profit"] == pytest.approx(led["operating_profit"])


def test_a_tie_keeps_the_first_proposer():
    problem = _problem()
    problem.demands = [Demand("A", "B", 500.0, 1000.0), Demand("B", "A", 500.0, 1000.0)]
    region_of_od = {("A", "B"): "First", ("B", "A"): "Second"}
    out = reconcile(problem, _pools(), region_of_od, ["First", "Second"], time_limit_sec=30)
    assert out.ok, out.message
    assert out.region_updates["First"]["services_selected"] == 1
    assert out.region_updates["Second"]["services_selected"] == 0


def test_a_region_whose_cargo_is_served_is_represented_by_a_service_it_proposed_and_uses():
    """Two rotations, both proposed by both regions; the First region's cargo dominates
    both. A pure majority rule would give First both services and Second (whose cargo is
    served too) none; the representation rule gives Second the one it uses."""
    ports = [Port(p, p, 0, 0, port_call_cost=1000.0) for p in "ABC"]
    fleet = Fleet(classes=[FleetClass("V", 10, 1000.0, 8000.0, min_speed=10, design_speed=12, max_speed=14,
                                      bunker_consumption_tons_per_day=20.0,
                                      idle_consumption_tons_per_day=2.0)])
    dm = {"A": {"B": 1000.0, "C": 1000.0}, "B": {"A": 1000.0, "C": 800.0}, "C": {"A": 1000.0, "B": 800.0}}
    demands = [Demand("A", "B", 900.0, 1000.0), Demand("B", "A", 100.0, 1000.0),
               Demand("A", "C", 800.0, 1000.0), Demand("C", "A", 50.0, 1000.0)]
    problem = Problem(ports=ports, services=[], demands=demands, distance_matrix=dm, fleet=fleet)
    pools = {"First": [{"id": "f1", "ports": ["A", "B"], "vessel_class": "V"},
                       {"id": "f2", "ports": ["A", "C"], "vessel_class": "V"}],
             "Second": [{"id": "s1", "ports": ["B", "A"], "vessel_class": "V"},
                        {"id": "s2", "ports": ["C", "A"], "vessel_class": "V"}]}
    region_of_od = {("A", "B"): "First", ("B", "A"): "Second", ("A", "C"): "First", ("C", "A"): "Second"}
    out = reconcile(problem, pools, region_of_od, ["First", "Second"], time_limit_sec=30)
    assert out.ok, out.message
    first, second = out.region_updates["First"], out.region_updates["Second"]
    assert first["services_selected"] == 1 and second["services_selected"] == 1
    led = out.network_ledger["weekly_usd"]
    assert first["total_cost"] + second["total_cost"] == pytest.approx(led["total_operating_cost"])
    assert first["weekly_profit"] + second["weekly_profit"] == pytest.approx(led["operating_profit"])


def test_a_region_that_proposed_nothing_but_uses_the_network_is_still_represented():
    """The regional cost split follows usage: a region whose cargo is served is given a
    service it rides even when it proposed none of the operated rotations."""
    problem = _problem()
    problem.demands = [Demand("A", "B", 500.0, 1000.0), Demand("B", "A", 500.0, 1000.0)]
    pools = {"First": [{"id": "f1", "ports": ["A", "B"], "vessel_class": "V"}], "Second": []}
    region_of_od = {("A", "B"): "First", ("B", "A"): "Second"}
    out = reconcile(problem, pools, region_of_od, ["First", "Second"], time_limit_sec=30)
    assert out.ok, out.message
    # one operated service, used by both regions: First (a proposer, tie on cargo) keeps it ...
    assert out.region_updates["First"]["services_selected"] + out.region_updates["Second"]["services_selected"] == 1
    led = out.network_ledger["weekly_usd"]
    tc = sum(r["total_cost"] for r in out.region_updates.values())
    assert tc == pytest.approx(led["total_operating_cost"])
    assert sum(r["revenue"] for r in out.region_updates.values()) == pytest.approx(led["revenue"])


def test_with_two_services_each_region_that_uses_the_network_gets_one_even_if_it_proposed_none():
    ports = [Port(p, p, 0, 0, port_call_cost=1000.0) for p in "ABC"]
    fleet = Fleet(classes=[FleetClass("V", 10, 1000.0, 8000.0, min_speed=10, design_speed=12, max_speed=14,
                                      bunker_consumption_tons_per_day=20.0,
                                      idle_consumption_tons_per_day=2.0)])
    dm = {"A": {"B": 1000.0, "C": 1000.0}, "B": {"A": 1000.0, "C": 800.0}, "C": {"A": 1000.0, "B": 800.0}}
    demands = [Demand("A", "B", 900.0, 1000.0), Demand("B", "A", 100.0, 1000.0),
               Demand("A", "C", 800.0, 1000.0), Demand("C", "A", 50.0, 1000.0)]
    problem = Problem(ports=ports, services=[], demands=demands, distance_matrix=dm, fleet=fleet)
    pools = {"First": [{"id": "f1", "ports": ["A", "B"], "vessel_class": "V"},
                       {"id": "f2", "ports": ["A", "C"], "vessel_class": "V"}], "Second": []}
    region_of_od = {("A", "B"): "First", ("B", "A"): "Second", ("A", "C"): "First", ("C", "A"): "Second"}
    out = reconcile(problem, pools, region_of_od, ["First", "Second"], time_limit_sec=30)
    assert out.ok, out.message
    assert out.region_updates["First"]["services_selected"] == 1
    assert out.region_updates["Second"]["services_selected"] == 1


def test_regional_split_reconciles_component_by_component_and_counts_no_service_twice():
    """Approved allocation rule (usage-based): every service's cost is charged to exactly
    ONE region, so the regional totals add up to the network ledger line by line and a
    service used by several regions is not counted once per user."""
    ports = [Port(p, p, 0, 0, port_call_cost=1000.0) for p in "ABC"]
    fleet = Fleet(classes=[FleetClass("V", 10, 1000.0, 8000.0, min_speed=10, design_speed=12, max_speed=14,
                                      bunker_consumption_tons_per_day=20.0,
                                      idle_consumption_tons_per_day=2.0)])
    dm = {"A": {"B": 1000.0, "C": 1000.0}, "B": {"A": 1000.0, "C": 800.0}, "C": {"A": 1000.0, "B": 800.0}}
    demands = [Demand("A", "B", 900.0, 1000.0), Demand("B", "A", 400.0, 1000.0),
               Demand("A", "C", 800.0, 1000.0), Demand("C", "A", 300.0, 1000.0)]
    problem = Problem(ports=ports, services=[], demands=demands, distance_matrix=dm, fleet=fleet)
    pools = {"First": [{"id": "f1", "ports": ["A", "B"], "vessel_class": "V"},
                       {"id": "f2", "ports": ["A", "C"], "vessel_class": "V"}],
             "Second": [{"id": "s1", "ports": ["B", "A"], "vessel_class": "V"}],
             "Third": [{"id": "t1", "ports": ["C", "A"], "vessel_class": "V"}]}
    region_of_od = {("A", "B"): "First", ("B", "A"): "Second", ("A", "C"): "First", ("C", "A"): "Third"}
    names = ["First", "Second", "Third"]
    out = reconcile(problem, pools, region_of_od, names, time_limit_sec=30)
    assert out.ok, out.message
    upd = out.region_updates
    led = out.network_ledger["weekly_usd"]

    def total(key):
        return sum(float(upd[r][key]) for r in names)

    tight = dict(rel=1e-9, abs=1e-6)
    assert total("revenue") == pytest.approx(led["revenue"], **tight)
    assert total("operating_cost") == pytest.approx(led["vessel_cost"], **tight)
    assert total("fuel_cost") == pytest.approx(led["fuel_cost"], **tight)
    assert total("transship_cost") == pytest.approx(led["transshipment_cost"], **tight)
    assert total("port_cost") == pytest.approx(
        led["port_call_fixed_cost"] + led["handling_cost"] + led["port_variable_cost"], **tight)
    assert total("total_cost") == pytest.approx(led["total_operating_cost"], **tight)
    assert total("weekly_profit") == pytest.approx(led["operating_profit"], **tight)

    # no shared cost is counted twice: each operated service is listed by exactly one region
    listed = [s["id"] for r in names for s in upd[r]["selected_services"]]
    operated = sorted(out.plan.ledger.service_rows)
    assert sorted(listed) == operated and len(listed) == len(set(listed))
    rows = out.plan.ledger.service_rows
    for r in names:
        for s in upd[r]["selected_services"]:
            assert s["vessel_cost"] == pytest.approx(rows[s["id"]]["vessel_cost"], **tight)
            assert s["fuel_cost"] == pytest.approx(rows[s["id"]]["fuel_cost"], **tight)
    assert sum(s["vessel_cost"] + s["fuel_cost"] for r in names for s in upd[r]["selected_services"]) == \
        pytest.approx(led["vessel_cost"] + led["fuel_cost"], **tight)
