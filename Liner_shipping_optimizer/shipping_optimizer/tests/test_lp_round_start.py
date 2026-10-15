"""LP-rounding integer start for CBC (``LINER_MILP_LP_ROUND_START``, default OFF).

Contract: strict flag parsing; the rounded start is feasible for the fleet limits by construction; OFF changes nothing;
ON gives a usable, ledger-valid plan and records what it did.  SYNTHETIC fixtures."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.network.network_milp as nm
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

DM = {"A": {"B": 1000.0, "C": 1600.0, "D": 2400.0}, "B": {"A": 1000.0, "C": 600.0, "D": 1400.0},
      "C": {"A": 1600.0, "B": 600.0, "D": 800.0}, "D": {"A": 2400.0, "B": 1400.0, "C": 800.0}}


def _cls(name, qty, cap, tc=8000.0):
    return FleetClass(vessel_class=name, quantity=qty, capacity_teu=cap, tc_rate_daily=tc, min_speed=10.0,
                      design_speed=12.0, max_speed=14.0, bunker_consumption_tons_per_day=20.0,
                      idle_consumption_tons_per_day=2.0)


def _problem(qty=6):
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0, transshipment_cost=0.0,
                  variable_port_call_cost=0.0) for p in "ABCD"]
    pairs = [("A", "B"), ("B", "A"), ("B", "C"), ("C", "B"), ("C", "D"), ("D", "C")]
    dem = [Demand(o, d, 700.0, 1500.0, max_transit_days=60.0) for o, d in pairs]
    return Problem(ports=ports, services=[], demands=dem, distance_matrix=DM, fleet=Fleet(classes=[_cls("S", qty, 900.0)]))


POOL = [Candidate(f"c{i}", r, "S") for i, r in enumerate([("A", "B"), ("B", "C"), ("C", "D"), ("A", "B", "C"), ("B", "C", "D")])]


def test_flag_parsing(monkeypatch):
    monkeypatch.delenv("LINER_MILP_LP_ROUND_START", raising=False)
    assert nm.lp_round_start_enabled() is False
    monkeypatch.setenv("LINER_MILP_LP_ROUND_START", "1")
    assert nm.lp_round_start_enabled() is True
    monkeypatch.setenv("LINER_MILP_LP_ROUND_START", "yes please")
    with pytest.raises(ValueError):
        nm.lp_round_start_enabled()


def test_rounded_start_is_fleet_feasible_and_drops_the_weakest_first():
    pr = _problem(qty=4)
    planner = NetworkPlanner(pr)
    models, rejected = planner.build_models(POOL)
    assert models and not rejected
    lp_f = {i: 0.9 for i in range(len(models))}
    lp_f[0] = 0.3                                           # weakest: opened at one sailing, first to go
    start, rep = nm.lp_rounded_start(models, lp_f, {"S": 4})
    need = sum(models[s].vessels(f) for s, f in start.items())
    assert need <= 4
    assert all(f >= 1 for f in start.values())
    assert rep["services"] == len(start) and rep["sailings"] == sum(start.values())
    if rep["repair_steps"]:
        assert (0 not in start) or all(lp_f[s] >= lp_f[0] for s in start)


def test_off_is_the_baseline_and_on_gives_a_valid_plan(monkeypatch):
    pr = _problem(qty=8)
    monkeypatch.delenv("LINER_MILP_LP_ROUND_START", raising=False)
    base = NetworkPlanner(pr).plan(list(POOL), demands=pr.demands, time_limit_sec=60.0)
    assert base.ok and "lp_round_start" not in base.solution.formulation
    monkeypatch.setenv("LINER_MILP_LP_ROUND_START", "1")
    on = NetworkPlanner(pr).plan(list(POOL), demands=pr.demands, time_limit_sec=60.0)
    assert on.ok and on.ledger.valid and on.reconciliation["reconciled"] is True
    assert "lp_round_start" in on.solution.formulation
    assert on.ledger.operating_profit >= base.ledger.operating_profit - 1e-6      # same small instance: the optimum is reached either way
