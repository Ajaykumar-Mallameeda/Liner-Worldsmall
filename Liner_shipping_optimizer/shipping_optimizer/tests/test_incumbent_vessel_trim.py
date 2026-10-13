"""Task 15 - a time-limited incumbent must not be reported with slack vessels.

Defect found by the Task 15 baseline matrix: at the production 120 s limit CBC returned, on
one of five seeds, a feasible incumbent whose vessel variables ``n_s`` exceeded
``ceil(T f / 7)`` (the vessel constraint is only a lower bound and the solver stopped before
removing the slack).  The independent ledger charges the minimum, so MILP objective
(7.26 M) != ledger profit (8.32 M), ``reconciled`` was False and the whole network was
reported ``verified: False`` although the plan was feasible and its ledger profit correct.

The fix trims ``n_s`` to the minimum the vessel constraint needs.  It cannot weaken a
constraint: ``7 n >= T f`` holds with equality at the minimum and the per-class fleet
constraints only get looser.  Expected values are computed by hand from the fixture of
``test_network_economics`` (vessel V: 1,000 TEU, 8,000 USD/day, 5 vessels).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.network.network_milp as nm
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

DM = {"A": {"B": 1000.0}, "B": {"A": 1200.0}}


def _problem():
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0,
                  transshipment_cost=0.0, variable_port_call_cost=0.0) for p in "AB"]
    v = FleetClass(vessel_class="V", quantity=5, capacity_teu=1000.0, tc_rate_daily=8000.0,
                   min_speed=10.0, design_speed=12.0, max_speed=14.0,
                   bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0)
    demands = [Demand("A", "B", 1500.0, 1000.0), Demand("B", "A", 1500.0, 1000.0)]
    return Problem(ports=ports, services=[], demands=demands, distance_matrix=DM,
                   fleet=Fleet(classes=[v]))


def _inflate(extra):
    """Wrap ``_build_and_solve`` so the INTEGER solve returns ``extra`` slack vessels on
    every active service - exactly what a solver stopped before polishing returns."""
    original = nm._build_and_solve

    def wrapped(*a, **kw):
        res = original(*a, **kw)
        if kw.get("integer"):
            for si in res["active"]:
                res["n"][si].varValue = (res["n"][si].varValue or 0.0) + extra
        return res
    return wrapped


class TestIncumbentVesselTrim:
    def _plan(self, monkeypatch=None, extra=0):
        if extra:
            monkeypatch.setattr(nm, "_build_and_solve", _inflate(extra))
        pr = _problem()
        return NetworkPlanner(pr).plan([Candidate("s", ("A", "B"), "V")], demands=pr.demands)

    def test_clean_incumbent_is_unchanged(self):
        p = self._plan()
        assert p.ok and p.solution.vessel_slack_removed == 0
        assert p.solution.vessel_slack_cost_usd == 0.0
        assert p.reconciliation["reconciled"] is True

    def test_slack_vessels_are_trimmed_and_the_plan_reconciles(self, monkeypatch):
        clean = self._plan()
        slack = self._plan(monkeypatch, extra=2)
        sol = slack.solution
        # the same plan: frequencies and flows are untouched
        assert sol.frequencies == clean.solution.frequencies
        assert sorted(sol.flows) == sorted(clean.solution.flows)
        # vessels are the minimum ceil(T f / 7)
        m = slack.models[0]
        f = sol.frequencies[0]
        assert sol.vessels[0] == m.vessels(f)
        # the slack that was removed is reported, with its cost (2 vessels x 56,000)
        assert sol.vessel_slack_removed == 2
        assert sol.vessel_slack_cost_usd == pytest.approx(2 * m.vessel_week_cost)
        # MILP objective == independent ledger profit again; the plan is verified
        assert slack.reconciliation["reconciled"] is True
        assert slack.ledger.valid and slack.ok
        assert sol.objective_value == pytest.approx(slack.ledger.operating_profit, abs=1e-6)
        assert sol.objective_value == pytest.approx(clean.solution.objective_value, abs=1e-6)
        assert slack.reconciliation["vessel_slack_removed"] == 2

    def test_trimming_never_touches_revenue_or_the_other_cost_terms(self, monkeypatch):
        clean = self._plan().solution.objective_components
        slack = self._plan(monkeypatch, extra=3).solution.objective_components
        for k in ("revenue", "per_teu_port_cost", "fuel_cost", "port_fixed_cost",
                  "unserved_penalty", "vessel_cost"):
            assert slack[k] == pytest.approx(clean[k]), k

    def test_trim_helper_is_a_noop_without_slack_and_never_adds_vessels(self):
        pr = _problem()
        planner = NetworkPlanner(pr)
        models, _ = planner.build_models([Candidate("s", ("A", "B"), "V")])
        sol = nm.NetworkSolution(status="feasible")
        sol.frequencies = {0: 2}
        sol.vessels = {0: models[0].vessels(2)}
        sol.objective_components = {"vessel_cost": 3 * models[0].vessel_week_cost}
        sol.objective_value = -1.0
        nm._trim_slack_vessels(models, sol, [0])
        assert sol.vessels == {0: 3} and sol.vessel_slack_removed == 0 and sol.objective_value == -1.0
        # below the minimum is never "repaired" upward by the trim (the constraint forbids it)
        sol.vessels = {0: 1}
        nm._trim_slack_vessels(models, sol, [0])
        assert sol.vessels == {0: 1} and sol.vessel_slack_removed == 0
