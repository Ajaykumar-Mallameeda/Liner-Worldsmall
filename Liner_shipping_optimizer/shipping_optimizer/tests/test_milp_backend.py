"""Task 15 - the opt-in HiGHS backend of the global network MILP.

``NETWORK_MILP_BACKEND`` unset / ``cbc`` is the production path and must be untouched;
``highs`` solves the UNRESTRICTED integer problem through ``scipy.optimize.milp`` (scipy is a
pinned requirement already) for free-frequency solves only.  It must never be a silent
substitution: an unsupported value is a ``solver_error`` and a fixed-frequency solve stays on
CBC.  Statuses are honest: ``optimal`` only when HiGHS proved it, otherwise ``feasible`` with
the MIP dual bound reported.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.network.network_milp as nm
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

DM = {"A": {"B": 1000.0, "C": 1600.0}, "B": {"A": 1200.0, "C": 600.0},
      "C": {"A": 1600.0, "B": 600.0}}


def _problem():
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0,
                  transshipment_cost=0.0, variable_port_call_cost=0.0) for p in "ABC"]
    v = FleetClass(vessel_class="V", quantity=5, capacity_teu=1000.0, tc_rate_daily=8000.0,
                   min_speed=10.0, design_speed=12.0, max_speed=14.0,
                   bunker_consumption_tons_per_day=20.0, idle_consumption_tons_per_day=2.0)
    demands = [Demand("A", "B", 1500.0, 1000.0), Demand("B", "A", 1200.0, 1000.0),
               Demand("B", "C", 800.0, 900.0)]
    return Problem(ports=ports, services=[], demands=demands, distance_matrix=DM,
                   fleet=Fleet(classes=[v]))


CANDS = [Candidate("ab", ("A", "B"), "V"), Candidate("abc", ("A", "B", "C"), "V"),
         Candidate("bc", ("B", "C"), "V")]


def _plan(**kw):
    pr = _problem()
    return NetworkPlanner(pr).plan(CANDS, demands=pr.demands, **kw)


class TestBackendSelection:
    def test_default_is_cbc(self, monkeypatch):
        monkeypatch.delenv("NETWORK_MILP_BACKEND", raising=False)
        p = _plan()
        assert p.solution.solver_backend == "cbc" and p.ok

    def test_highs_matches_cbc_on_a_problem_both_can_close(self, monkeypatch):
        monkeypatch.delenv("NETWORK_MILP_BACKEND", raising=False)
        cbc = _plan(lp_guided=False)
        monkeypatch.setenv("NETWORK_MILP_BACKEND", "highs")
        hi = _plan()
        assert cbc.status == "optimal" and hi.status == "optimal"
        s = hi.solution
        assert s.solver_backend == "highs"
        assert s.objective_value == pytest.approx(cbc.solution.objective_value, rel=1e-9)
        # the independent ledger agrees with the HiGHS plan: verified, reconciled
        assert hi.ok and hi.reconciliation["reconciled"] is True
        assert hi.ledger.operating_profit == pytest.approx(s.objective_value, abs=1e-6)
        assert s.relaxation_bound is not None and s.relaxation_bound >= s.objective_value - 1e-6
        assert s.n_services_restricted_to == s.n_services_considered      # unrestricted

    def test_unknown_backend_is_an_error_not_a_silent_cbc(self, monkeypatch):
        monkeypatch.setenv("NETWORK_MILP_BACKEND", "gurobi")
        p = _plan()
        assert p.status == "solver_error" and not p.ok
        assert "NETWORK_MILP_BACKEND" in p.solution.message and "gurobi" in p.solution.message

    def test_fixed_frequency_solves_stay_on_cbc(self, monkeypatch):
        monkeypatch.setenv("NETWORK_MILP_BACKEND", "highs")
        p = _plan(fixed_frequencies={"ab": 1})
        assert p.solution.solver_backend == "cbc"


class TestHighsStatusMapping:
    def _fake(self, monkeypatch, overrides):
        import scipy.optimize as so
        real = so.milp

        def fake(c, **kw):
            r = real(c, **kw)
            data = dict(x=r.x, status=r.status, message=str(r.message),
                        mip_gap=getattr(r, "mip_gap", None),
                        mip_dual_bound=getattr(r, "mip_dual_bound", None), fun=r.fun)
            data.update(overrides(data) if callable(overrides) else overrides)
            return SimpleNamespace(**data)
        monkeypatch.setattr(so, "milp", fake)

    def test_time_limit_incumbent_is_feasible_with_the_dual_bound(self, monkeypatch):
        monkeypatch.setenv("NETWORK_MILP_BACKEND", "highs")
        self._fake(monkeypatch, lambda d: dict(status=1, message="Time limit reached",
                                               mip_gap=0.05, mip_dual_bound=d["fun"] - 1234.0))
        p = _plan()
        s = p.solution
        assert s.status == "feasible"                       # not proven optimal
        assert s.mip_gap == pytest.approx(0.05)
        assert s.relaxation_bound == pytest.approx(s.objective_value + 1234.0, abs=1e-6)
        assert p.ok                                          # the incumbent is kept and verified

    def test_optimal_with_a_loose_gap_is_not_called_optimal(self, monkeypatch):
        # HiGHS's own tolerance is 1e-4; a reported gap above it is only a feasible incumbent
        monkeypatch.setenv("NETWORK_MILP_BACKEND", "highs")
        self._fake(monkeypatch, dict(status=0, mip_gap=1e-3))
        assert _plan().solution.status == "feasible"

    def test_no_incumbent_is_not_solved_with_the_backend_message(self, monkeypatch):
        monkeypatch.setenv("NETWORK_MILP_BACKEND", "highs")
        self._fake(monkeypatch, dict(x=None, status=1, message="Time limit reached"))
        p = _plan()
        assert p.status == "not_solved" and not p.ok
        assert "Time limit reached" in p.solution.message

    def test_infeasible(self, monkeypatch):
        monkeypatch.setenv("NETWORK_MILP_BACKEND", "highs")
        self._fake(monkeypatch, dict(x=None, status=2, message="infeasible"))
        assert _plan().status == "infeasible"

    def test_solver_noise_is_not_reported_as_a_flow_on_an_inactive_service(self, monkeypatch):
        """Gate finding (orchestrator run T15_orch_highs_run3, 341/342): HiGHS returned
        ~1e-9 TEU on paths through services with frequency 0 (constraint tolerance); the
        test's independent recomputation rightly flagged ``flow_on_inactive_service``.
        Noise below FLOW_NOISE_TEU must not become a plan flow."""
        import numpy as np
        import scipy.optimize as so
        real = so.milp
        monkeypatch.setenv("NETWORK_MILP_BACKEND", "highs")

        def noisy(c, **kw):
            r = real(c, **kw)
            x = np.where(np.abs(r.x) < 1e-12, 1.5e-9, r.x)       # every zero becomes 1.5e-9
            return SimpleNamespace(x=x, status=r.status, message=str(r.message),
                                   mip_gap=getattr(r, "mip_gap", None),
                                   mip_dual_bound=getattr(r, "mip_dual_bound", None), fun=r.fun)
        monkeypatch.setattr(so, "milp", noisy)
        p = _plan()
        assert p.ok and p.ledger.valid and not p.ledger.violations
        assert all(teu > 1e-6 for _, _, teu in p.solution.flows)   # no noise-level flow
        assert nm.FLOW_NOISE_TEU == 1e-6
        operated = {m.service_id for m in p.models
                    if p.solution.frequencies.get(p.models.index(m), 0) > 0}
        assert operated                                          # something is operated
        assert p.reconciliation["reconciled"] is True

    def test_exception_is_a_solver_error(self, monkeypatch):
        import scipy.optimize as so
        monkeypatch.setenv("NETWORK_MILP_BACKEND", "highs")

        def boom(*a, **k):
            raise RuntimeError("highs unavailable")
        monkeypatch.setattr(so, "milp", boom)
        p = _plan()
        assert p.status == "solver_error" and "highs unavailable" in p.solution.message
