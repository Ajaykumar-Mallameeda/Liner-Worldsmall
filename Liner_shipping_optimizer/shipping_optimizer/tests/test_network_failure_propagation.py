"""Failure propagation: a stage that cannot produce a verified plan says so.

Nothing here reaches an LLM or the network. The contract under test:

* an input that cannot be modelled is a reasoned ``Invalid Input``, never a zero cost;
* a global stage with nothing to plan, or whose candidates were all rejected, fails
  explicitly (it is never a "complete" empty network);
* the orchestrator marks every regional result ``Unverified (<status>)`` and returns a
  ledger block with ``verified = False`` when the global stage fails;
* the final ``status`` is ``complete`` only for a verified ledger.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.reconcile import GlobalStageResult, reconcile
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem, Service
from src.optimization.hub_milp import HubMILP


def _fleet():
    return Fleet(classes=[FleetClass(
        vessel_class="V", quantity=20, capacity_teu=1000.0, tc_rate_daily=8000.0, min_speed=10.0,
        design_speed=12.0, max_speed=14.0, bunker_consumption_tons_per_day=20.0,
        idle_consumption_tons_per_day=2.0)])


def _problem(fleet=True):
    ports = [Port("A", "A", 0, 0, port_call_cost=1000.0), Port("B", "B", 0, 0, port_call_cost=1000.0)]
    return Problem(
        ports=ports,
        services=[Service(id="s", ports=["A", "B"], capacity=1000.0, weekly_cost=0.0, vessel_class="V")],
        demands=[Demand("A", "B", 500.0, 1000.0)],
        distance_matrix={"A": {"B": 1000.0}, "B": {"A": 1200.0}},
        fleet=_fleet() if fleet else None,
    )


# ----------------------------------------------------------------------- HubMILP
def test_hubmilp_without_a_fleet_is_a_reasoned_invalid_input():
    res = HubMILP(_problem(fleet=False), {"services": [1], "frequencies": [1]}, time_limit=10).solve()
    assert res["status"] == "Invalid Input"
    assert res["valid"] is False
    assert "missing_fleet" in res["reasons"]
    assert res["message"]


def test_hubmilp_selected_service_without_a_frequency_is_invalid_input():
    res = HubMILP(_problem(), {"services": [1], "frequencies": []}, time_limit=10).solve()
    assert res["status"] == "Invalid Input" and "missing_frequency" in res["reasons"]


@pytest.mark.parametrize("bad", [-1, 1.5, float("nan")])
def test_hubmilp_invalid_frequency_is_invalid_input(bad):
    res = HubMILP(_problem(), {"services": [1], "frequencies": [bad]}, time_limit=10).solve()
    assert res["status"] == "Invalid Input" and "invalid_frequency" in res["reasons"]


def test_hubmilp_missing_distance_is_invalid_input_not_zero_cost():
    p = _problem()
    p.distance_matrix = {"A": {"B": 1000.0}, "B": {}}               # return leg unknown
    res = HubMILP(p, {"services": [1], "frequencies": [1]}, time_limit=10).solve()
    assert res["status"] == "Invalid Input" and res["valid"] is False
    assert "missing_directed_distance" in res["reasons"]
    assert res["total_cost"] == 0.0 and res["satisfied_demand"] == 0.0


# ---------------------------------------------------------------- global stage
def test_global_stage_with_no_candidates_fails_explicitly():
    out = reconcile(_problem(), {}, {}, ["R"])
    assert isinstance(out, GlobalStageResult)
    assert out.ok is False and out.status == "invalid_input" and out.message


def test_global_stage_where_every_candidate_is_rejected_fails_explicitly():
    pools = {"R": [{"id": "x", "ports": ["A", "B"], "vessel_class": "NoSuchClass"}]}
    out = reconcile(_problem(), pools, {("A", "B"): "R"}, ["R"])
    assert out.ok is False, "an all-rejected pool must not become a 'complete' empty network"
    assert out.status == "invalid_input"
    assert "rejected" in out.message.lower()


def test_global_stage_verified_plan_is_additive_and_flagged_verified():
    pools = {"R": [{"id": "s", "ports": ["A", "B"], "vessel_class": "V"}]}
    out = reconcile(_problem(), pools, {("A", "B"): "R"}, ["R"], time_limit_sec=30)
    assert out.ok and out.network_ledger["verified"] is True
    upd = out.region_updates["R"]
    led = out.network_ledger["weekly_usd"]
    assert upd["weekly_profit"] == pytest.approx(led["operating_profit"], rel=1e-9)
    assert upd["total_cost"] == pytest.approx(led["total_operating_cost"], rel=1e-9)
    assert out.network_ledger["violations"] == []


# ------------------------------------------------------------------ orchestrator
def _fake_agents(problem):
    agent = SimpleNamespace(
        region="R",
        last_candidate_pool=[{"id": "s", "ports": ["A", "B"], "vessel_class": "V"}],
        last_milp_result={"frequencies": {"s": 1}},
    )
    return [agent], {0: SimpleNamespace(demands=problem.demands)}


def test_orchestrator_marks_regions_unverified_when_the_global_stage_fails(monkeypatch):
    import src.agents.orchestrator_agent as oa

    orch = oa.OrchestratorAgent()
    problem = _problem()
    agents, regional_problems = _fake_agents(problem)
    results = [{"region": "R", "status": "Optimal", "weekly_profit": 123.0}]

    monkeypatch.setattr(oa, "reconcile_global_network",
                        lambda *a, **k: GlobalStageResult(False, "solver_error", "boom"))
    block = orch._reconcile_iteration(problem, regional_problems, agents, results, 0)

    assert block["verified"] is False
    assert block["status"] == "solver_error" and block["message"] == "boom"
    assert results[0]["status"] == "Unverified (solver_error)"


def test_orchestrator_survives_a_global_stage_exception(monkeypatch):
    import src.agents.orchestrator_agent as oa

    orch = oa.OrchestratorAgent()
    problem = _problem()
    agents, regional_problems = _fake_agents(problem)
    results = [{"region": "R", "status": "Optimal"}]

    def _raise(*a, **k):
        raise RuntimeError("solver exploded")

    monkeypatch.setattr(oa, "reconcile_global_network", _raise)
    block = orch._reconcile_iteration(problem, regional_problems, agents, results, 0)
    assert block["verified"] is False and block["status"] == "solver_error"
    assert "solver exploded" in block["message"]
    assert results[0]["status"].startswith("Unverified")


def test_orchestrator_overwrites_regions_with_the_verified_partition():
    import src.agents.orchestrator_agent as oa

    orch = oa.OrchestratorAgent()
    problem = _problem()
    agents, regional_problems = _fake_agents(problem)
    results = [{"region": "R", "status": "Optimal", "weekly_profit": -999.0}]
    block = orch._reconcile_iteration(problem, regional_problems, agents, results, 0)

    assert block["verified"] is True
    assert results[0]["weekly_profit"] == pytest.approx(block["weekly_usd"]["operating_profit"], rel=1e-9)
    assert results[0]["satisfied_demand"] == pytest.approx(500.0, rel=1e-9) or results[0]["satisfied_demand"] > 0
