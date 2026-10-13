"""Reporting contract of the solver bound (decision phase, addendum item 2).

The relaxation bound belongs to the CAPPED MILP model.  The final plan - after local search, flow
re-optimisation over the full valid path set and repair - may lie outside that model, so
(a) the gap is computed from the MILP incumbent as the solver returned it, never from the final plan;
(b) a final plan above the bound is reported as ``exceeds_capped_model_bound``, not as a negative gap and
    never as evidence of optimality.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.plan import Candidate, NetworkPlanner
from src.network.reconcile import _capped_gap, _capped_model_block, _final_plan_block
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

DM = {"A": {"B": 1000.0, "C": 1600.0}, "B": {"A": 1200.0, "C": 600.0}, "C": {"A": 1600.0, "B": 600.0}}


def _plan(inc, bound, final, reopt=True, ls=False):
    return SimpleNamespace(
        milp_stage={"incumbent_profit_usd_per_week": inc, "relaxation_bound_usd_per_week": bound, "status": "feasible"},
        flow_reopt={"applied": reopt}, local_search={"applied": ls}), SimpleNamespace(operating_profit=final)


def test_gap_uses_the_milp_incumbent_not_the_final_plan():
    plan, led = _plan(inc=30.0e6, bound=40.0e6, final=45.0e6)
    usd, pct = _capped_gap(plan)
    assert usd == pytest.approx(10.0e6) and pct == pytest.approx(25.0)
    blk = _capped_model_block(plan, led)
    assert blk["gap_usd_per_week"] == pytest.approx(10.0e6) and "capped" in blk["scope"]


def test_final_plan_above_the_bound_is_flagged_not_a_negative_gap():
    plan, led = _plan(inc=30.0e6, bound=40.0e6, final=45.0e6)
    fp = _final_plan_block(plan, led)
    assert fp["exceeds_capped_model_bound"] is True
    assert fp["post_solve_change_usd_per_week"] == pytest.approx(15.0e6)
    assert "does not prove optimality" in fp["scope"]
    assert _capped_gap(plan)[0] >= 0                      # the model-scope gap is never negative here


def test_final_plan_inside_the_bound_is_not_flagged():
    plan, led = _plan(inc=30.0e6, bound=40.0e6, final=31.0e6)
    assert _final_plan_block(plan, led)["exceeds_capped_model_bound"] is False


def test_missing_incumbent_or_bound_gives_none_not_zero():
    plan, led = _plan(inc=None, bound=None, final=1.0)
    assert _capped_gap(plan) == (None, None)
    assert _final_plan_block(plan, led)["post_solve_change_usd_per_week"] is None


def test_planner_records_the_milp_stage_before_post_solve_steps():
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0, transshipment_cost=0.0,
                  variable_port_call_cost=0.0) for p in "ABC"]
    v = FleetClass(vessel_class="V", quantity=6, capacity_teu=1000.0, tc_rate_daily=8000.0, min_speed=10.0,
                   design_speed=12.0, max_speed=14.0, bunker_consumption_tons_per_day=20.0,
                   idle_consumption_tons_per_day=2.0)
    pr = Problem(ports=ports, services=[], demands=[Demand("A", "B", 900.0, 1000.0), Demand("B", "C", 700.0, 900.0),
                                                    Demand("A", "C", 400.0, 1500.0)],
                 distance_matrix=DM, fleet=Fleet(classes=[v]))
    res = NetworkPlanner(pr).plan([Candidate("ab", ("A", "B"), "V"), Candidate("bc", ("B", "C"), "V")],
                                  time_limit_sec=20.0)
    ms = res.milp_stage
    assert ms["incumbent_profit_usd_per_week"] is not None and ms["status"] in ("optimal", "feasible")
    # re-routing over the full path set never lowers the profit of the solved plan
    assert res.ledger.operating_profit >= ms["incumbent_profit_usd_per_week"] - 1e-3
