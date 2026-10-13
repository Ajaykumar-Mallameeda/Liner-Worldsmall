"""Issue 3 hardening: a time-limited CBC run without any integer solution must be reported as
``not_solved`` - never as an empty ``feasible`` plan (observed on WorldSmall seed 10 with the
15 s local-search reserve: solver status "Optimal", objective 0, no service, and an
``invalid_plan`` verdict from the independent ledger).

The conservation rows are equalities (``sum_p q_p + u_d == weekly_teu_d``), so every genuine
solution conserves every OD; all-zero values do not.
"""
import sys
from pathlib import Path

import pulp
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.network.network_milp as nm
from src.network.paths import build_paths
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

DM = {"A": {"B": 1000.0, "C": 1600.0}, "B": {"A": 1200.0, "C": 600.0}, "C": {"A": 1600.0, "B": 600.0}}
CANDS = [Candidate("ab", ("A", "B"), "V"), Candidate("bc", ("B", "C"), "V")]


def _instance():
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0,
                  transshipment_cost=0.0, variable_port_call_cost=0.0) for p in "ABC"]
    v = FleetClass(vessel_class="V", quantity=5, capacity_teu=1000.0, tc_rate_daily=8000.0,
                   min_speed=10.0, design_speed=12.0, max_speed=14.0,
                   bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0)
    pr = Problem(ports=ports, services=[], demands=[Demand("A", "B", 400.0, 1000.0), Demand("B", "C", 300.0, 900.0)],
                 distance_matrix=DM, fleet=Fleet(classes=[v]))
    planner = NetworkPlanner(pr)
    models, rej = planner.build_models(CANDS)
    assert models and not rej
    paths, _ = build_paths(pr.demands, models, planner.port_lookup, planner.assumptions,
                           max_paths_per_od=10, config=planner.path_config)
    return pr, models, paths, {"V": 5}


def _force_empty(monkeypatch, sol_status):
    """Make the integer phase return what CBC returns on a timeout without incumbent."""
    real = nm._build_and_solve

    def fake(*a, **kw):
        solve_flag = kw.get("solve", True)
        if not kw.get("integer", False) or not solve_flag:
            return real(*a, **kw)
        kw = dict(kw, solve=False)
        res = real(*a, **kw)
        for var in res["prob"].variables():
            var.varValue = 0.0
        res["prob"].status = pulp.LpStatusOptimal
        res["prob"].sol_status = sol_status
        return res
    monkeypatch.setattr(nm, "_build_and_solve", fake)


def test_empty_values_with_no_solution_status_are_not_solved(monkeypatch):
    pr, models, paths, limits = _instance()
    _force_empty(monkeypatch, pulp.LpSolutionNoSolutionFound)
    sol = nm.solve_network(models, pr.demands, paths, limits, time_limit_sec=20.0, lp_guided=False)
    assert sol.status == "not_solved" and not sol.usable
    assert "no incumbent" in sol.message


def test_empty_values_reported_feasible_are_still_not_solved(monkeypatch):
    """Even when the solution status looks fine, all-zero values break demand conservation."""
    pr, models, paths, limits = _instance()
    _force_empty(monkeypatch, pulp.LpSolutionIntegerFeasible)
    sol = nm.solve_network(models, pr.demands, paths, limits, time_limit_sec=20.0, lp_guided=False)
    assert sol.status == "not_solved" and not sol.usable
    assert "conserve" in sol.message


def test_a_real_solution_is_unaffected():
    pr, models, paths, limits = _instance()
    sol = nm.solve_network(models, pr.demands, paths, limits, time_limit_sec=20.0, lp_guided=False)
    assert sol.status in ("optimal", "feasible") and sol.usable
    served = sum(f for (_di, _k, f) in sol.flows)
    assert served == pytest.approx(700.0, rel=1e-6)
    for di, d in enumerate(pr.demands):
        got = sum(f for (o, _k, f) in sol.flows if o == di) + sol.unserved.get(di, 0.0)
        assert got == pytest.approx(d.weekly_teu, rel=1e-6, abs=1e-3)
