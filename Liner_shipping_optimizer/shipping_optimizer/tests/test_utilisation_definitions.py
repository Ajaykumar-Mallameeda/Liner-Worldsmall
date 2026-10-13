"""Utilisation definitions (decision phase, addendum item 3).

leg load factor        = carried TEU-legs / offered TEU-legs, offered = capacity_per_departure x frequency x legs
vessel utilisation     = vessels assigned / vessels owned (per class)       [fleet block of the plan]
weekly cargo / per-departure capacity is NOT a utilisation (exceeds 1 with several legs or departures)
Independent recomputation: the expectations below are derived from the routed flows and path geometry only.
"""
import sys
from collections import defaultdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

DM = {"A": {"B": 1000.0, "C": 1600.0}, "B": {"A": 1000.0, "C": 600.0}, "C": {"A": 1600.0, "B": 600.0}}


def _plan():
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0, transshipment_cost=0.0,
                  variable_port_call_cost=0.0) for p in "ABC"]
    v = FleetClass(vessel_class="V", quantity=12, capacity_teu=500.0, tc_rate_daily=3000.0, min_speed=10.0,
                   design_speed=14.0, max_speed=16.0, bunker_consumption_tons_per_day=10.0,
                   idle_consumption_tons_per_day=1.0)
    dem = [Demand("A", "B", 700.0, 1500.0), Demand("B", "A", 650.0, 1500.0), Demand("B", "C", 300.0, 1200.0),
           Demand("A", "C", 200.0, 1800.0)]
    pr = Problem(ports=ports, services=[], demands=dem, distance_matrix=DM, fleet=Fleet(classes=[v]))
    res = NetworkPlanner(pr).plan([Candidate("abc", ("A", "B", "C"), "V"), Candidate("ab", ("A", "B"), "V")],
                                  time_limit_sec=20.0)
    assert res.ok
    return pr, res


def test_leg_load_factor_matches_an_independent_recomputation():
    pr, res = _plan()
    carried = defaultdict(float)
    for di, k, teu in res.solution.flows:
        for seg in res.paths[di][k].segments:
            carried[res.models[seg.service].service_id] += teu * len(seg.legs)
    assert res.ledger.service_rows
    for sid, row in res.ledger.service_rows.items():
        m = next(x for x in res.models if x.service_id == sid)
        offered = m.capacity_teu * row["frequency"] * len(m.legs)
        assert row["offered_teu_legs"] == pytest.approx(offered)
        assert row["carried_teu_legs"] == pytest.approx(carried[sid], rel=1e-6, abs=1e-6)
        assert row["leg_load_factor"] == pytest.approx(carried[sid] / offered, rel=1e-6, abs=1e-9)
        assert 0.0 <= row["leg_load_factor"] <= 1.0 + 1e-9
        assert row["weekly_capacity_per_leg"] == pytest.approx(m.capacity_teu * row["frequency"])


def test_leg_load_factor_is_bounded_by_one_by_construction():
    """The ledger rejects any leg above capacity x frequency, so the load factor cannot exceed 1."""
    pr, res = _plan()
    assert res.ledger.valid
    for r in res.ledger.service_rows.values():
        assert r["leg_load_factor"] <= 1.0 + 1e-9


def test_vessel_utilisation_is_assigned_over_owned():
    pr, res = _plan()
    assigned = sum(r["vessels"] for r in res.ledger.service_rows.values())
    assert assigned == sum(res.ledger.vessels_by_class.values())
    assert assigned <= 12
