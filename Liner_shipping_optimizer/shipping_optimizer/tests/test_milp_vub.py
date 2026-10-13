"""C1 - the optional valid inequality  q[od, p] <= weekly_teu[od] * f[s]  (``LINER_MILP_VUB``).

Contract
  * default OFF: the model is exactly the baseline model (no extra rows, formulation flag false);
  * valid: it removes no integer-feasible point - checked by enumerating every integer
    frequency vector of small instances and comparing the optimum of the baseline and of the
    strengthened model point by point, and by comparing the unrestricted integer optima;
  * stronger: the LP relaxation bound is never weaker (maximisation: never larger) and is
    strictly smaller when demand is far below one vessel's capacity;
  * covers multi-service (transfer) paths: one row per service of the path;
  * skipped when frequencies are imposed (redundant there), and the skip is reported.
"""
import itertools
import sys
from pathlib import Path

import pulp
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.network.network_milp as nm
from src.network.paths import build_paths
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

DM = {"A": {"B": 1000.0, "C": 1600.0}, "B": {"A": 1200.0, "C": 600.0},
      "C": {"A": 1600.0, "B": 600.0}}
CANDS = [Candidate("ab", ("A", "B"), "V"), Candidate("abc", ("A", "B", "C"), "V"),
         Candidate("bc", ("B", "C"), "V")]


def _problem(demands, capacity=1000.0, quantity=5, port_call=1000.0):
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=port_call,
                  transshipment_cost=0.0, variable_port_call_cost=0.0) for p in "ABC"]
    v = FleetClass(vessel_class="V", quantity=quantity, capacity_teu=capacity, tc_rate_daily=8000.0,
                   min_speed=10.0, design_speed=12.0, max_speed=14.0,
                   bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0)
    return Problem(ports=ports, services=[], demands=demands, distance_matrix=DM,
                   fleet=Fleet(classes=[v]))


INSTANCES = {
    # demand >> capacity per sailing: several weekly departures are needed
    "heavy": lambda: _problem([Demand("A", "B", 2500.0, 1000.0), Demand("B", "A", 1800.0, 1000.0),
                               Demand("B", "C", 1200.0, 900.0)]),
    # demand far below one vessel's capacity: the LP can run services at a tiny fraction
    "light": lambda: _problem([Demand("A", "B", 120.0, 1000.0), Demand("B", "A", 90.0, 1000.0),
                               Demand("B", "C", 60.0, 900.0), Demand("A", "C", 80.0, 1500.0)]),
    # includes an A->C transfer path (two services)
    "transfer": lambda: _problem([Demand("A", "B", 400.0, 1000.0), Demand("B", "C", 300.0, 900.0),
                                  Demand("A", "C", 350.0, 1600.0)], capacity=600.0),
}


def _model(name):
    pr = INSTANCES[name]()
    planner = NetworkPlanner(pr)
    models, rejected = planner.build_models(CANDS)
    assert models and not rejected
    paths, _ = build_paths(pr.demands, models, planner.port_lookup, planner.assumptions,
                           max_paths_per_od=10, config=planner.path_config)
    limits = {c.vessel_class: c.quantity for c in pr.fleet.classes}
    return pr, planner, models, paths, limits


def _build(name, vub, *, integer=True, fixed=None):
    pr, _pl, models, paths, limits = _model(name)
    res = nm._build_and_solve(models, pr.demands, paths, limits, list(range(len(models))),
                              integer=integer, penalty=0.0, fixed=fixed, initial=None,
                              max_departures_cap=None, time_limit_sec=30.0, threads=None,
                              solve=False, vub=vub)
    return res, models, pr, paths


class TestFlag:
    def test_default_off_and_parsing(self, monkeypatch):
        monkeypatch.delenv("LINER_MILP_VUB", raising=False)
        assert nm.vub_enabled() is False
        for v, want in (("1", True), ("true", True), ("ON", True), ("0", False), ("off", False), ("", False)):
            monkeypatch.setenv("LINER_MILP_VUB", v)
            assert nm.vub_enabled() is want
        monkeypatch.setenv("LINER_MILP_VUB", "maybe")
        with pytest.raises(ValueError, match="LINER_MILP_VUB"):
            nm.vub_enabled()

    def test_default_model_is_the_baseline_model(self, monkeypatch):
        monkeypatch.delenv("LINER_MILP_VUB", raising=False)
        pr, planner, models, paths, limits = _model("light")
        base = nm.solve_network(models, pr.demands, paths, limits, time_limit_sec=30.0)
        assert base.formulation["vub_applied"] is False
        assert base.formulation["vub_rows_integer_problem"] == 0
        res, *_ = _build("light", vub=False)
        assert res["vub_rows"] == 0 and not any(k.startswith("vub_") for k in res["prob"].constraints)


class TestRowsAndSkips:
    def test_one_row_per_service_of_each_path(self):
        res, models, pr, paths = _build("transfer", vub=True)
        expect = sum(len(set(p.services)) for plist in paths.values() for p in plist)
        assert res["vub_rows"] == expect > 0
        # a transfer path (two services) contributes two rows
        n_transfer = sum(1 for plist in paths.values() for p in plist if len(set(p.services)) == 2)
        assert n_transfer >= 1
        names = [k for k in res["prob"].constraints if k.startswith("vub_")]
        assert len(names) == expect

    def test_rows_use_the_od_demand(self):
        res, models, pr, paths = _build("light", vub=True)
        prob = res["prob"]
        for name, con in prob.constraints.items():
            if not name.startswith("vub_"):
                continue
            _, di, k, si = name.split("_")
            coeffs = {v.name: c for v, c in con.items()}
            assert coeffs[f"q_{di}_{k}"] == pytest.approx(1.0)
            assert coeffs[f"f_{si}"] == pytest.approx(-pr.demands[int(di)].weekly_teu)
            assert con.sense == pulp.LpConstraintLE and con.constant == 0

    def test_skipped_with_imposed_frequencies(self, monkeypatch):
        monkeypatch.setenv("LINER_MILP_VUB", "1")
        pr, planner, models, paths, limits = _model("light")
        sol = nm.solve_network(models, pr.demands, paths, limits, time_limit_sec=30.0,
                               fixed_frequencies={0: 1, 1: 1, 2: 1})
        assert sol.formulation["vub_requested"] is True
        assert sol.formulation["vub_applied"] is False
        assert sol.formulation["vub_rows_integer_problem"] == 0
        res, *_ = _build("light", vub=True, fixed={0: 1, 1: 1, 2: 1})
        assert res["vub_rows"] == 0


class TestValidity:
    @pytest.mark.parametrize("name", ["heavy", "light", "transfer"])
    def test_unrestricted_integer_optimum_is_unchanged(self, name, monkeypatch):
        monkeypatch.delenv("LINER_MILP_VUB", raising=False)
        pr, planner, models, paths, limits = _model(name)
        base = nm.solve_network(models, pr.demands, paths, limits, time_limit_sec=60.0, lp_guided=False)
        monkeypatch.setenv("LINER_MILP_VUB", "1")
        vub = nm.solve_network(models, pr.demands, paths, limits, time_limit_sec=60.0, lp_guided=False)
        assert base.status == "optimal" and vub.status == "optimal"
        assert vub.formulation["vub_applied"] is True and vub.formulation["vub_rows_integer_problem"] > 0
        assert vub.objective_value == pytest.approx(base.objective_value, rel=1e-9, abs=1e-6)

    @pytest.mark.parametrize("name", ["heavy", "transfer"])
    def test_no_integer_point_is_cut(self, name):
        """Fix every integer frequency vector (f in {0,1,2}^services) and compare the optimum of the
        baseline and of the strengthened model: they must be equal at EVERY point (feasible or not)."""
        base, models, *_ = _build(name, vub=False)
        strong, *_ = _build(name, vub=True)
        assert strong["vub_rows"] > 0
        idx = base["active"]
        assert idx == strong["active"]

        def optimum(res, point):
            for si, val in zip(idx, point):
                res["f"][si].lowBound = res["f"][si].upBound = float(val)
            res["prob"].solve(nm._solver(30.0, None, False))
            st = res["prob"].status
            return st, (pulp.value(res["prob"].objective) if st == pulp.LpStatusOptimal else None)

        checked = 0
        for point in itertools.product((0, 1, 2), repeat=len(idx)):
            ub = [models[si].max_departures(5) for si in idx]
            if any(p > u for p, u in zip(point, ub)):
                continue
            s0, o0 = optimum(base, point)
            s1, o1 = optimum(strong, point)
            assert s0 == s1, f"feasibility differs at f={point}"
            if o0 is not None:
                assert o1 == pytest.approx(o0, rel=1e-9, abs=1e-6), f"optimum differs at f={point}"
            checked += 1
        assert checked >= 8


class TestBound:
    @pytest.mark.parametrize("name", ["heavy", "light", "transfer"])
    def test_lp_bound_is_not_weaker(self, name, monkeypatch):
        pr, planner, models, paths, limits = _model(name)
        monkeypatch.delenv("LINER_MILP_VUB", raising=False)
        b0 = nm.solve_network(models, pr.demands, paths, limits, time_limit_sec=60.0).relaxation_bound
        monkeypatch.setenv("LINER_MILP_VUB", "1")
        b1 = nm.solve_network(models, pr.demands, paths, limits, time_limit_sec=60.0).relaxation_bound
        assert b0 is not None and b1 is not None
        assert b1 <= b0 + 1e-6 * max(1.0, abs(b0))              # maximisation: a stronger bound is smaller

    def test_lp_bound_is_strictly_stronger_when_demand_is_far_below_capacity(self, monkeypatch):
        pr, planner, models, paths, limits = _model("light")
        monkeypatch.delenv("LINER_MILP_VUB", raising=False)
        b0 = nm.solve_network(models, pr.demands, paths, limits, time_limit_sec=60.0).relaxation_bound
        monkeypatch.setenv("LINER_MILP_VUB", "1")
        s1 = nm.solve_network(models, pr.demands, paths, limits, time_limit_sec=60.0)
        assert s1.relaxation_bound < b0 - 1.0
        # and the bound is still a valid upper bound of the plan it produced
        assert s1.relaxation_bound >= s1.objective_value - 1e-6


class TestPlanIsLedgerVerified:
    @pytest.mark.parametrize("name", ["heavy", "light", "transfer"])
    def test_strengthened_plan_passes_the_independent_ledger(self, name, monkeypatch):
        monkeypatch.setenv("LINER_MILP_VUB", "1")
        pr = INSTANCES[name]()
        plan = NetworkPlanner(pr).plan(CANDS, demands=pr.demands, time_limit_sec=60.0)
        assert plan.ok and plan.ledger.valid and plan.reconciliation["reconciled"] is True
        assert plan.reconciliation["formulation"]["vub_applied"] is True
        assert plan.ledger.operating_profit == pytest.approx(plan.solution.objective_value, abs=1e-3)
