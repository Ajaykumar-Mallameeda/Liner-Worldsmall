"""Trunk-rotation candidates for under-subscribed classes (``LINER_TRUNK_CANDIDATES``, default OFF).

Contract: flag parsing is strict; OFF adds nothing and leaves the pool untouched; only UNDER-subscribed classes get
rotations; every addition has a positive stand-alone profit, >= 3 ports, is no duplicate of an existing (rotation,
class), carries its provenance and respects the class inventory; the augmented pool plans and passes the independent
ledger.  All fixtures are SYNTHETIC."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.network.trunk_candidates as tk
from src.network.economics import assumptions_for_problem
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

DM = {
    "A": {"B": 1000.0, "C": 1600.0, "D": 2400.0},
    "B": {"A": 1000.0, "C": 600.0, "D": 1400.0},
    "C": {"A": 1600.0, "B": 600.0, "D": 800.0},
    "D": {"A": 2400.0, "B": 1400.0, "C": 800.0},
}


def _cls(name, qty, cap, tc=8000.0, design=12.0, bunker=20.0, draft=9.0):
    return FleetClass(vessel_class=name, quantity=qty, capacity_teu=cap, tc_rate_daily=tc, draft=draft,
                      min_speed=design - 2.0, design_speed=design, max_speed=design + 2.0,
                      bunker_consumption_tons_per_day=bunker, idle_consumption_tons_per_day=2.0)


def _problem(classes, scale=1.0):
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0, transshipment_cost=0.0,
                  variable_port_call_cost=0.0, draft=12.0) for p in "ABCD"]
    pairs = [("A", "B"), ("B", "A"), ("B", "C"), ("C", "B"), ("C", "D"), ("D", "C"), ("A", "C"), ("C", "A")]
    dem = [Demand(o, d, 900.0 * scale, 1500.0, max_transit_days=60.0) for o, d in pairs]
    return Problem(ports=ports, services=[], demands=dem, distance_matrix=DM, fleet=Fleet(classes=classes))


CLASSES = [_cls("S", 2, 400.0), _cls("L", 30, 3000.0, tc=12000.0, bunker=40.0)]
POOL = [Candidate(f"c{i}", r, "S") for i, r in enumerate([("A", "B"), ("B", "C"), ("C", "D"), ("A", "B", "C"), ("B", "C", "D")])]


class TestFlags:
    def test_count(self, monkeypatch):
        monkeypatch.delenv("LINER_TRUNK_CANDIDATES", raising=False)
        assert tk.count_from_environment() == 0
        monkeypatch.setenv("LINER_TRUNK_CANDIDATES", "6")
        assert tk.count_from_environment() == 6
        for bad in ("-1", "x", "1.5", "500"):
            monkeypatch.setenv("LINER_TRUNK_CANDIDATES", bad)
            with pytest.raises(ValueError):
                tk.count_from_environment()

    def test_max_ports(self, monkeypatch):
        monkeypatch.delenv("LINER_TRUNK_MAX_PORTS", raising=False)
        assert tk.max_ports_from_environment() == 8
        for bad in ("2", "99", "x"):
            monkeypatch.setenv("LINER_TRUNK_MAX_PORTS", bad)
            with pytest.raises(ValueError):
                tk.max_ports_from_environment()


class TestAugment:
    def _run(self, per_class=3, classes=None, pool=POOL, scale=1.0, max_ports=4):
        pr = _problem(classes or CLASSES, scale)
        return pr, tk.augment_trunk_candidates(pr, assumptions_for_problem(pr), pool, per_class=per_class, max_ports=max_ports)

    def test_off_adds_nothing_and_pool_is_untouched(self):
        before = [(c.service_id, c.ports, c.vessel_class) for c in POOL]
        _pr, (extra, rep) = self._run(per_class=0)
        assert extra == [] and rep["added"] == 0
        assert before == [(c.service_id, c.ports, c.vessel_class) for c in POOL]

    def test_only_under_subscribed_classes_are_targeted(self):
        _pr, (extra, rep) = self._run()
        assert set(rep["target_classes"]) == {"L"}                  # S: 5 candidates / 2 vessels is over-subscribed
        assert extra and all(c.vessel_class == "L" for c in extra)

    def test_every_addition_is_profitable_valid_and_documented(self):
        _pr, (extra, rep) = self._run()
        keys = {(tuple(c.ports), c.vessel_class) for c in POOL}
        assert len(extra) <= 3
        for c, a in zip(extra, rep["additions"]):
            assert len(c.ports) >= 3 and len(set(c.ports)) == len(c.ports)
            assert (tuple(c.ports), c.vessel_class) not in keys
            assert a["standalone_profit_usd_per_week"] > 0
            assert a["vessels_at_f1"] <= 30
            assert a["reason"] and a["service_id"] == c.service_id
        assert rep["added"] == len(extra)

    def test_no_loss_making_rotation_is_added(self):
        classes = [_cls("S", 2, 400.0), _cls("L", 30, 3000.0, tc=9_000_000.0)]
        _pr, (extra, rep) = self._run(classes=classes)
        assert extra == []

    def test_class_whose_draft_exceeds_every_port_gets_nothing(self):
        classes = [_cls("S", 2, 400.0), _cls("L", 30, 3000.0, draft=20.0)]
        _pr, (extra, rep) = self._run(classes=classes)
        assert extra == []

    def test_deterministic(self):
        _p1, (e1, _r1) = self._run()
        _p2, (e2, _r2) = self._run()
        assert [(c.ports, c.vessel_class) for c in e1] == [(c.ports, c.vessel_class) for c in e2]

    def test_augmented_pool_plans_and_passes_the_ledger(self):
        pr, (extra, rep) = self._run()
        plan = NetworkPlanner(pr).plan(list(POOL) + list(extra), demands=pr.demands, time_limit_sec=60.0)
        assert plan.ok and plan.ledger.valid and plan.reconciliation["reconciled"] is True
        assert not [r for r in plan.rejected_candidates if str(r.get("service", "")).startswith("tk")]
