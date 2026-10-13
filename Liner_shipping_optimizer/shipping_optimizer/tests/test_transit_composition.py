"""Transit-time composition (decision phase D-06): port stay and transfer dwell are different processes.

  transit = sailing days of the ridden legs
          + one port stay (24 h) at every INTERMEDIATE port of a ridden service (not at origin / destination)
          + one transfer dwell (48 h minimum + expected wait) per transfer, charged once per transfer.
Values are the provisional model conventions (see the assumption register); the tests pin the COMPOSITION,
not the numbers' truth.  The independent ledger recomputes the same quantity from the raw records.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.economics import EconomicsAssumptions
from src.network.ledger import LedgerFlow, LedgerService, compute_ledger
from src.network.paths import build_paths
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

SPEED_NM_PER_DAY = 14.0 * 24.0
DM = {"A": {"B": 1000.0, "C": 3000.0, "D": 4000.0}, "B": {"A": 1000.0, "C": 1000.0, "D": 2000.0},
      "C": {"A": 3000.0, "B": 1000.0, "D": 1000.0}, "D": {"A": 4000.0, "B": 2000.0, "C": 1000.0}}


def _problem(demands):
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=0.0, transshipment_cost=0.0,
                  variable_port_call_cost=0.0, draft=20.0) for p in "ABCD"]
    v = FleetClass(vessel_class="V", quantity=50, capacity_teu=1000.0, tc_rate_daily=1000.0, draft=10.0,
                   min_speed=10.0, design_speed=14.0, max_speed=18.0, bunker_consumption_tons_per_day=1.0,
                   idle_consumption_tons_per_day=1.0)
    return Problem(ports=ports, services=[], demands=demands, distance_matrix=DM, fleet=Fleet(classes=[v]))


def _paths(demands, cands, assumptions=None, max_transfers=2):
    pr = _problem(demands)
    from src.network.paths import PathConfig
    pl = NetworkPlanner(pr, assumptions=assumptions or EconomicsAssumptions(),
                        path_config=PathConfig(max_transfers=max_transfers, multi_hop_min_alternatives=10 ** 6))
    models, rej = pl.build_models(cands)
    assert not rej
    paths, _ = build_paths(pr.demands, models, pl.port_lookup, pl.assumptions, max_paths_per_od=50, config=pl.path_config)
    return pr, pl, models, paths


def _the(paths, di, kind):
    return [p for p in paths[di] if p.kind == kind]


def test_direct_ride_has_no_port_stay_at_origin_or_destination():
    pr, pl, models, paths = _paths([Demand("A", "B", 10.0, 100.0)], [Candidate("ab", ("A", "B"), "V")])
    (p,) = _the(paths, 0, "direct")
    assert p.transit_days == pytest.approx(1000.0 / SPEED_NM_PER_DAY)


def test_intermediate_port_of_a_ridden_service_adds_one_port_stay():
    pr, pl, models, paths = _paths([Demand("A", "C", 10.0, 100.0)], [Candidate("abc", ("A", "B", "C"), "V")])
    (p,) = _the(paths, 0, "direct")
    assert p.transit_days == pytest.approx(2000.0 / SPEED_NM_PER_DAY + 1.0)          # + 24 h at B


def test_transfer_adds_dwell_once_not_a_port_stay_per_service():
    a = EconomicsAssumptions()
    pr, pl, models, paths = _paths([Demand("A", "C", 10.0, 100.0)],
                                   [Candidate("ab", ("A", "B"), "V"), Candidate("bc", ("B", "C"), "V")], a)
    (p,) = _the(paths, 0, "transfer")
    dwell = a.transshipment_min_hours / 24.0 + a.transfer_wait_days                  # 2 d + 3.5 d
    assert dwell == pytest.approx(5.5)
    assert p.transit_days == pytest.approx(2000.0 / SPEED_NM_PER_DAY + dwell)


def test_two_transfers_add_two_dwells():
    a = EconomicsAssumptions()
    pr, pl, models, paths = _paths([Demand("A", "D", 10.0, 100.0)],
                                   [Candidate("ab", ("A", "B"), "V"), Candidate("bc", ("B", "C"), "V"),
                                    Candidate("cd", ("C", "D"), "V")], a)
    (p,) = _the(paths, 0, "transfer2")
    dwell = a.transshipment_min_hours / 24.0 + a.transfer_wait_days
    assert p.transit_days == pytest.approx(3000.0 / SPEED_NM_PER_DAY + 2 * dwell)


@pytest.mark.parametrize("wait, stay_h", [(1.75, 24.0), (7.0, 24.0), (3.5, 12.0), (3.5, 48.0)])
def test_dwell_and_port_stay_are_independent_parameters(wait, stay_h):
    a = EconomicsAssumptions(transfer_wait_days=wait, port_stay_hours=stay_h)
    # one transfer at B plus one intermediate port stay inside the second service (B-C-D ridden B->D)
    pr, pl, models, paths = _paths([Demand("A", "D", 10.0, 100.0)],
                                   [Candidate("ab", ("A", "B"), "V"), Candidate("bcd", ("B", "C", "D"), "V")], a)
    (p,) = _the(paths, 0, "transfer")
    expected = 3000.0 / SPEED_NM_PER_DAY + (48.0 / 24.0 + wait) + stay_h / 24.0          # dwell + stay at C
    assert p.transit_days == pytest.approx(expected)


def test_ledger_recomputes_the_same_transit_time_and_enforces_the_limit():
    a = EconomicsAssumptions()
    pr, pl, models, paths = _paths([Demand("A", "C", 10.0, 100.0)],
                                   [Candidate("ab", ("A", "B"), "V"), Candidate("bc", ("B", "C"), "V")], a)
    (p,) = _the(paths, 0, "transfer")
    need = p.transit_days
    svcs = [LedgerService("ab", ("A", "B"), "V", 1), LedgerService("bc", ("B", "C"), "V", 1)]
    flow = [LedgerFlow(0, (("ab", "A", "B"), ("bc", "B", "C")), 10.0)]

    def led(limit):
        d = Demand("A", "C", 10.0, 100.0, max_transit_days=limit)
        return compute_ledger(svcs, flow, [d], pr.fleet, DM, pl.port_lookup,
                              port_stay_hours=a.port_stay_hours, transshipment_min_hours=a.transshipment_min_hours,
                              transfer_wait_days=a.transfer_wait_days, bunker_price_usd_per_t=600.0, max_transfers=1)

    assert not [v for v in led(need + 1e-6).violations if v["type"] == "transit_exceeded"]
    assert [v for v in led(need - 0.01).violations if v["type"].startswith("transit")]
