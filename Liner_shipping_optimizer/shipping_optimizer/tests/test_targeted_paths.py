"""Targeted path additions (``LINER_PATH_TARGETED=K,M``, default OFF): LP duals, selection rule, caps, integration.

Duals: PuLP/CBC returns, for the maximisation LP, d objective / d right-hand side.  The tests check that by finite
differences on the solved LP itself (not by assumption), then check the selection rule on a synthetic network in which a
cheaper path is excluded by the per-OD path cap.  All fixtures are SYNTHETIC."""
import sys
from pathlib import Path

import pulp
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.network.network_milp as nm
import src.network.targeted_paths as tp
from src.network.paths import PathConfig, build_paths
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

PORTS = "ABCD"
DM = {"A": {"B": 1000.0, "C": 1400.0, "D": 2300.0}, "B": {"A": 1000.0, "C": 900.0, "D": 1000.0},
      "C": {"A": 1400.0, "B": 900.0, "D": 900.0}, "D": {"A": 2300.0, "B": 1000.0, "C": 900.0}}


def _vessel(qty=20, cap=1000.0):
    return FleetClass(vessel_class="V", quantity=qty, capacity_teu=cap, tc_rate_daily=8000.0, min_speed=10.0, design_speed=12.0,
                      max_speed=14.0, bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0)


def _problem(extra_demands=(), hub_cost=None):
    hub_cost = hub_cost or {"B": 900.0, "C": 50.0}
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0, transshipment_cost=hub_cost.get(p, 0.0),
                  variable_port_call_cost=0.0, draft=12.0) for p in PORTS]
    dem = [Demand("A", "D", 400.0, 1000.0, max_transit_days=80.0), Demand("A", "B", 300.0, 800.0, max_transit_days=80.0),
           Demand("C", "D", 300.0, 800.0, max_transit_days=80.0), Demand("A", "C", 300.0, 800.0, max_transit_days=80.0)] + list(extra_demands)
    return Problem(ports=ports, services=[], demands=dem, distance_matrix=DM, fleet=Fleet(classes=[_vessel()]))


CANDS = [Candidate("s0", ("A", "B"), "V"), Candidate("s1", ("B", "D"), "V"), Candidate("s2", ("A", "C"), "V"),
         Candidate("s3", ("C", "D"), "V")]


def _lp(problem, cap_paths=1):
    pl = NetworkPlanner(problem)
    models, _rej = pl.build_models(CANDS)
    cfg = PathConfig()
    paths, _ = build_paths(problem.demands, models, pl.port_lookup, pl.assumptions, max_paths_per_od=cap_paths, config=cfg)
    full, _ = build_paths(problem.demands, models, pl.port_lookup, pl.assumptions, max_paths_per_od=10 ** 9, config=cfg)
    lim = {"V": 20}
    lp = nm._build_and_solve(models, problem.demands, paths, lim, list(range(len(models))), integer=False, penalty=0.0, fixed=None,
                             initial=None, max_departures_cap=None, time_limit_sec=30, threads=None, vub=False)
    return pl, models, paths, full, lp


# ---------------------------------------------------------------- flag
class TestFlag:
    def test_parse(self, monkeypatch):
        monkeypatch.delenv("LINER_PATH_TARGETED", raising=False)
        assert tp.targeted_from_environment() is None
        monkeypatch.setenv("LINER_PATH_TARGETED", "30, 3")
        assert tp.targeted_from_environment() == (30, 3)
        monkeypatch.setenv("LINER_PATH_TARGETED", "30:3")
        assert tp.targeted_from_environment() == (30, 3)
        monkeypatch.setenv("LINER_PATH_TARGETED", "0")
        assert tp.targeted_from_environment() is None
        for bad in ("30", "a,b", "0,3", "30,0", "30,9", "500,2", "1,2,3,4"):
            monkeypatch.setenv("LINER_PATH_TARGETED", bad)
            with pytest.raises(ValueError):
                tp.targeted_from_environment()


# ---------------------------------------------------------------- duals: sign and unit by finite differences
class TestDuals:
    def _objective_after(self, lp, name, delta):
        prob = lp["prob"]
        con = prob.constraints[name]
        con.constant -= delta                         # right-hand side + delta
        try:
            prob.solve(pulp.PULP_CBC_CMD(msg=False))
            return float(pulp.value(prob.objective))
        finally:
            con.constant += delta

    def test_demand_dual_is_profit_per_extra_teu(self):
        _pl, _m, _p, _f, lp = _lp(_problem(), cap_paths=10)
        base = float(pulp.value(lp["prob"].objective))
        duals = tp.lp_duals(lp)
        for di in (1, 2, 3):                                    # demands that are served (a positive dual)
            assert duals["dem"][di] > 0
            after = self._objective_after(lp, f"dem_{di}", 1.0)
            assert after - base == pytest.approx(duals["dem"][di], rel=1e-5, abs=1e-4)
            lp["prob"].solve(pulp.PULP_CBC_CMD(msg=False))

    def test_capacity_dual_is_profit_per_extra_teu_of_leg_capacity_and_non_negative(self):
        _pl, _m, _p, _f, lp = _lp(_problem(), cap_paths=10)
        duals = tp.lp_duals(lp)
        assert duals["cap"] and all(v >= -1e-9 for v in duals["cap"].values())
        base = float(pulp.value(lp["prob"].objective))
        name, pi = next((f"cap_{s}_{l}", v) for (s, l), v in sorted(duals["cap"].items()) if v > 1.0)
        after = self._objective_after(lp, name, 1.0)
        assert after - base == pytest.approx(pi, rel=1e-5, abs=1e-4)   # CBC prints duals with 6 digits


# ---------------------------------------------------------------- selection
class TestSelection:
    def test_a_cheaper_excluded_path_is_selected_and_improves_the_lp(self):
        pr = _problem()
        pl, models, paths, full, lp = _lp(pr, cap_paths=1)
        # A->D keeps only the fastest path (via B, transshipment 900 per TEU: unprofitable); the path via C is excluded
        d_idx = 0
        assert len(paths[d_idx]) == 1 and len(full[d_idx]) >= 2
        assert float(lp["u"][d_idx].varValue) > 1e-6                          # unserved in the relaxation
        extra, rep = tp.select_targeted_paths(lp, pr.demands, paths, full, k_ods=3, m_paths=2)
        assert d_idx in extra and rep["paths_added"] >= 1
        assert rep["additions"][0]["reduced_profit_usd_per_teu"][0] > 0
        merged = tp.merge_paths(paths, extra)
        assert len(merged[d_idx]) == len(paths[d_idx]) + len(extra[d_idx])
        assert [id(p) for p in merged[d_idx][:len(paths[d_idx])]] == [id(p) for p in paths[d_idx]]   # indices of old paths unchanged
        lim = {"V": 20}
        lp2 = nm._build_and_solve(models, pr.demands, merged, lim, list(range(len(models))), integer=False, penalty=0.0, fixed=None,
                                  initial=None, max_departures_cap=None, time_limit_sec=30, threads=None, vub=False)
        assert pulp.value(lp2["prob"].objective) > pulp.value(lp["prob"].objective) + 1.0     # the priced column is worth adding

    def test_caps_are_respected(self):
        pr = _problem()
        _pl, _m, paths, full, lp = _lp(pr, cap_paths=1)
        extra, rep = tp.select_targeted_paths(lp, pr.demands, paths, full, k_ods=1, m_paths=1)
        assert len(extra) <= 1 and all(len(v) <= 1 for v in extra.values())
        assert rep["ods_selected"] <= 1 and rep["paths_added"] <= 1

    def test_od_without_valid_path_is_not_selected(self):
        blocked = Demand("A", "D", 500.0, 2000.0, max_transit_days=3.0)         # no path fits 3 days
        pr = _problem(extra_demands=[blocked])
        _pl, _m, paths, full, lp = _lp(pr, cap_paths=1)
        extra, _rep = tp.select_targeted_paths(lp, pr.demands, paths, full, k_ods=10, m_paths=3)
        assert len(pr.demands) - 1 not in extra

    def test_fully_served_demand_is_not_selected(self):
        pr = _problem(hub_cost={"B": 0.0, "C": 0.0})                               # everything profitable: nothing unserved
        _pl, _m, paths, full, lp = _lp(pr, cap_paths=1)
        assert float(lp["u"][0].varValue) <= 1e-6
        extra, _rep = tp.select_targeted_paths(lp, pr.demands, paths, full, k_ods=10, m_paths=3)
        assert 0 not in extra


# ---------------------------------------------------------------- integration
class TestIntegration:
    def _plan(self, monkeypatch, flag):
        for k in ("LINER_PATH_TARGETED",):
            monkeypatch.delenv(k, raising=False)
        if flag:
            monkeypatch.setenv("LINER_PATH_TARGETED", flag)
        monkeypatch.setenv("LINER_MAX_TRANSFERS", "1")
        pr = _problem()
        planner = NetworkPlanner(pr, max_paths_per_od=1)
        return planner.plan(CANDS, time_limit_sec=30)

    def test_off_leaves_the_formulation_untouched(self, monkeypatch):
        res = self._plan(monkeypatch, None)
        assert res.ok and "targeted_paths" not in res.solution.formulation

    def test_on_applies_one_round_and_the_plan_passes_the_ledger(self, monkeypatch):
        off = self._plan(monkeypatch, None)
        on = self._plan(monkeypatch, "5,2")
        rep = on.solution.formulation["targeted_paths"]
        assert on.ok and on.ledger.valid and not on.ledger.violations
        assert rep["applied"] and rep["paths_added"] >= 1 and rep["lp_bound_after"] >= rep["lp_bound_before"] - 1e-6
        assert rep["q_columns_after"] == rep["q_columns_before"] + rep["paths_added"]
        assert on.ledger.operating_profit >= off.ledger.operating_profit - 1e-6         # the toy case benefits
        assert on.solution.n_paths == off.solution.n_paths + rep["paths_added"]

    def test_failure_of_the_round_keeps_the_original_plan(self, monkeypatch):
        import src.network.targeted_paths as t

        def boom(*a, **k):
            raise RuntimeError("synthetic failure")
        monkeypatch.setattr("src.network.plan.select_targeted_paths", boom)
        res = self._plan(monkeypatch, "5,2")
        rep = res.solution.formulation["targeted_paths"]
        assert res.ok and not rep["applied"] and "synthetic failure" in rep["error"]


class TestNoResolveVariant:
    """``LINER_PATH_TARGETED=K:M:0``: no second LP; only paths of services already in the LP support are added."""

    def test_parse(self, monkeypatch):
        monkeypatch.setenv("LINER_PATH_TARGETED", "30:3:0")
        assert tp.targeted_from_environment() == (30, 3) and tp.targeted_resolve_from_environment() is False
        monkeypatch.setenv("LINER_PATH_TARGETED", "30:3:1")
        assert tp.targeted_resolve_from_environment() is True
        monkeypatch.setenv("LINER_PATH_TARGETED", "30:3")
        assert tp.targeted_resolve_from_environment() is True
        monkeypatch.setenv("LINER_PATH_TARGETED", "30:3:2")
        with pytest.raises(ValueError):
            tp.targeted_resolve_from_environment()

    def test_integration_without_a_second_lp(self, monkeypatch):
        monkeypatch.setenv("LINER_PATH_TARGETED", "5:2:0")
        monkeypatch.setenv("LINER_MAX_TRANSFERS", "1")
        res = NetworkPlanner(_problem(), max_paths_per_od=1).plan(CANDS, time_limit_sec=30)
        rep = res.solution.formulation["targeted_paths"]
        assert res.ok and res.ledger.valid and not res.ledger.violations
        assert rep["applied"] and rep["resolve_lp"] is False and rep["paths_added"] >= 1
        assert res.solution.n_paths >= rep["paths_added"]
