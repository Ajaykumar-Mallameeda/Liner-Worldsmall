"""Canal fees (D-08) and draft feasibility (found in the decision phase) - the LINERLIB physical rules.

Evidence: the benchmark authors' reference code (include/bm_rotation.h: canal cost = traversals x class fee for one
round trip; is_draft_feasible) and their own best WorldSmall solution log, which this file reproduces when the
LINERLIB checkout is present (skipped otherwise).
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.data.network_loader import NetworkLoader
from src.network.economics import ServiceModelError, build_service_model
from src.network.ledger import LedgerFlow, LedgerService, compute_ledger
from src.network.physical_rules import LinerDistanceMatrix, check_rotation
from src.optimization.data import Demand, FleetClass, Fleet, Port

LINERLIB_LOG = Path(r"C:\Users\WINDOWS\Downloads\LINERLIB-master (1)\LINERLIB-master\results"
                    r"\BrouerDesaulniersPisinger2014\WorldSmall_Best_Base.log")


def _ports(draft=14.0):
    return {p: Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0, transshipment_cost=0.0,
                    variable_port_call_cost=0.0, draft=draft) for p in "ABC"}


def _dm(flags=None, edge=None):
    d = LinerDistanceMatrix({"A": {"B": 1000.0, "C": 3000.0}, "B": {"A": 1000.0, "C": 2000.0},
                             "C": {"A": 3000.0, "B": 2000.0}},
                            canal_flags=flags or {}, edge_draft=edge or {})
    return d


def _vessel(draft=10.0, panama=50_000.0, suez=200_000.0):
    return FleetClass(vessel_class="V", quantity=20, capacity_teu=1000.0, tc_rate_daily=8000.0, draft=draft,
                      min_speed=10.0, design_speed=14.0, max_speed=18.0, bunker_consumption_tons_per_day=20.0,
                      idle_consumption_tons_per_day=2.0, panama_fee=panama, suez_fee=suez)


def test_canal_fee_is_traversals_of_the_closed_rotation_times_the_class_fee():
    dm = _dm(flags={("A", "B"): (0, 1), ("B", "A"): (0, 1), ("B", "C"): (1, 0)})
    # rotation A-B-C-A: legs A->B (Suez), B->C (Panama), C->A (none)  ->  1 Suez + 1 Panama
    r = check_rotation(["A", "B", "C"], _vessel(), dm, _ports())
    assert (r.panama_traversals, r.suez_traversals) == (1, 1)
    assert r.canal_fee_per_rotation == pytest.approx(50_000.0 + 200_000.0)
    # rotation A-B: A->B and B->A both Suez-flagged: the return passage is charged too
    r2 = check_rotation(["A", "B"], _vessel(), dm, _ports())
    assert (r2.panama_traversals, r2.suez_traversals) == (0, 2)
    assert r2.canal_fee_per_rotation == pytest.approx(400_000.0)


def test_service_model_charges_the_fee_once_per_weekly_departure():
    dm = _dm(flags={("A", "B"): (0, 1), ("B", "A"): (0, 1)})
    m = build_service_model("s", ["A", "B"], _vessel(), dm, _ports())
    assert m.canal_fee_per_rotation == pytest.approx(400_000.0)
    assert m.port_fixed_per_rotation == pytest.approx(2 * 1000.0 + 400_000.0)
    assert m.weekly_port_fixed_cost(2) == pytest.approx(2 * (2000.0 + 400_000.0))


def test_blank_fee_means_the_class_cannot_pass_never_zero():
    dm = _dm(flags={("A", "B"): (1, 0), ("B", "A"): (1, 0)})
    with pytest.raises(ServiceModelError) as e:
        build_service_model("s", ["A", "B"], _vessel(panama=None), dm, _ports())
    assert "canal_not_passable_for_class" in e.value.reasons


def test_draft_limits_are_hard():
    with pytest.raises(ServiceModelError) as e:
        build_service_model("s", ["A", "B"], _vessel(draft=12.0), _dm(), _ports(draft=11.0))
    assert "draft_exceeds_port_limit" in e.value.reasons
    build_service_model("s", ["A", "B"], _vessel(draft=11.0), _dm(), _ports(draft=11.0))     # equal is allowed
    with pytest.raises(ServiceModelError) as e2:
        build_service_model("s", ["A", "B"], _vessel(draft=12.5), _dm(edge={("A", "B"): 12.0}), _ports())
    assert "draft_exceeds_leg_limit" in e2.value.reasons


def test_plain_matrix_has_no_canal_or_leg_information():
    """A plain dict (synthetic instance) carries no canal flags / leg drafts: no fee, no leg restriction.
    Port drafts are still enforced whenever the port records carry them."""
    plain = {"A": {"B": 1000.0}, "B": {"A": 1000.0}}
    m = build_service_model("s", ["A", "B"], _vessel(draft=10.0), plain, _ports(draft=14.0))
    assert m.canal_fee_per_rotation == 0.0 and m.canal_traversals == (0, 0)
    with pytest.raises(ServiceModelError):
        build_service_model("s", ["A", "B"], _vessel(draft=10.0), plain, _ports(draft=5.0))


def _ledger(dm, vessel, ports, f=1):
    fleet = Fleet(classes=[vessel])
    d = Demand("A", "B", 100.0, 1000.0)
    return compute_ledger([LedgerService("s", ("A", "B"), "V", f)],
                          [LedgerFlow(0, (("s", "A", "B"),), 100.0)], [d], fleet, dm, ports,
                          port_stay_hours=24.0, transshipment_min_hours=48.0, transfer_wait_days=3.5,
                          bunker_price_usd_per_t=600.0)


def test_ledger_recomputes_the_canal_fee_independently_and_matches_the_model():
    dm = _dm(flags={("A", "B"): (0, 1), ("B", "A"): (0, 1)})
    v = _vessel()
    m = build_service_model("s", ["A", "B"], v, dm, _ports())
    led = _ledger(dm, v, _ports(), f=1)
    assert led.valid, led.violations
    assert led.canal_fee_cost == pytest.approx(400_000.0)
    assert led.port_call_fixed_cost == pytest.approx(m.weekly_port_fixed_cost(1))


def test_ledger_rejects_draft_and_canal_violations():
    led = _ledger(_dm(), _vessel(draft=12.0), _ports(draft=11.0))
    assert not led.valid and any(x["type"] == "draft_infeasible" for x in led.violations)
    dm = _dm(flags={("A", "B"): (1, 0), ("B", "A"): (1, 0)})
    led2 = _ledger(dm, _vessel(panama=None), _ports())
    assert not led2.valid and any(x["type"] == "canal_not_passable" for x in led2.violations)


def test_canonical_post_panamax_cannot_serve_a_shallow_port():
    ld = NetworkLoader()
    pr = ld.load_problem()
    ports = {p.id: p for p in pr.ports}
    post = pr.fleet.get_class("Post_panamax")
    shallow = next(p for p in pr.ports if 0 < p.draft < post.draft)
    deep = next(p for p in pr.ports if p.draft >= post.draft and p.id != shallow.id)
    with pytest.raises(ServiceModelError):
        build_service_model("s", [shallow.id, deep.id], post, pr.distance_matrix, ports)


@pytest.mark.skipif(not LINERLIB_LOG.exists(), reason="LINERLIB reference results not present")
def test_rule_reproduces_the_authors_best_worldsmall_solution():
    pr = NetworkLoader().load_problem()
    dm = pr.distance_matrix
    fleet = pr.fleet
    by_cap = {int(c.capacity_teu / 2): c for c in fleet.classes}            # Capacity FFE -> class
    t = LINERLIB_LOG.read_text(encoding="utf8", errors="replace")
    blocks = re.split(r"\nservice \d+ service id \d+\n", t)[1:]
    assert len(blocks) == 34
    total_log = total_rule = 0.0
    for b in blocks:
        cap = int(re.search(r"capacity (\d+)", b).group(1))
        ports = re.findall(r"^\d+\t(\w+)\t", b, flags=re.M)
        cls = by_cap[cap]
        r = check_rotation(ports, cls, dm, {p.id: p for p in pr.ports})
        lp = re.search(r"Panama canal traversed (\d+)", b)
        ls = re.search(r"Suez canal traversed (\d+)", b)
        assert r.panama_traversals == (int(lp.group(1)) if lp else 0)
        assert r.suez_traversals == (int(ls.group(1)) if ls else 0)
        lc = re.search(r"Canal Cost ([\d.e+]+)", b)
        log_cost = float(lc.group(1)) if lc else 0.0
        assert r.canal_fee_per_rotation == pytest.approx(log_cost, rel=2e-6, abs=20.0)   # log prints 6 digits
        assert not r.reasons, (cap, r.reasons)        # the authors' solution has no draft / canal violation
        total_log += log_cost
        total_rule += r.canal_fee_per_rotation
    assert total_rule == pytest.approx(total_log, rel=1e-5)
    assert total_rule == pytest.approx(1.39351e7, rel=1e-4)                  # "Canal costs" of the objective
