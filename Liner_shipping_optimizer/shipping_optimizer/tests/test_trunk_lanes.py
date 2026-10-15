"""Trans-Pacific / Atlantic trunk-lane family (``LINER_TRUNK_LANES``, default OFF).

Contract: strict flag parsing; OFF adds nothing; every addition joins the two port groups of its lane, calls only at
lane ports the class can enter (draft), has a positive stand-alone profit, is no duplicate, respects the per-lane per-class
cap, and the per-constraint rejection counters add up.  The lane port lists agree with the ``D_Region`` column of the
canonical ``ports.csv``.  Fixtures for the generator are SYNTHETIC."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.network.trunk_lanes as tl
from src.network.economics import assumptions_for_problem
from src.network.plan import Candidate
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem


# ---------------------------------------------------------------- flags
class TestFlags:
    def test_lanes(self, monkeypatch):
        monkeypatch.delenv("LINER_TRUNK_LANES", raising=False)
        assert tl.lanes_from_environment() == []
        monkeypatch.setenv("LINER_TRUNK_LANES", "transpacific, atlantic,transpacific")
        assert tl.lanes_from_environment() == ["transpacific", "atlantic"]
        monkeypatch.setenv("LINER_TRUNK_LANES", "all")
        assert tl.lanes_from_environment() == sorted(tl.LANE_GROUPS)
        monkeypatch.setenv("LINER_TRUNK_LANES", "0")
        assert tl.lanes_from_environment() == []
        monkeypatch.setenv("LINER_TRUNK_LANES", "indian")
        with pytest.raises(ValueError):
            tl.lanes_from_environment()

    def test_count_and_ports(self, monkeypatch):
        monkeypatch.delenv("LINER_TRUNK_LANE_COUNT", raising=False)
        assert tl.count_from_environment() == 2
        for bad in ("0", "7", "x"):
            monkeypatch.setenv("LINER_TRUNK_LANE_COUNT", bad)
            with pytest.raises(ValueError):
                tl.count_from_environment()
        monkeypatch.delenv("LINER_TRUNK_LANE_MAX_PORTS", raising=False)
        assert tl.max_ports_from_environment() == 8
        monkeypatch.setenv("LINER_TRUNK_LANE_MAX_PORTS", "2")
        with pytest.raises(ValueError):
            tl.max_ports_from_environment()

    def test_classes_default(self, monkeypatch):
        monkeypatch.delenv("LINER_TRUNK_LANE_CLASSES", raising=False)
        assert tl.classes_from_environment() == ("Post_panamax", "Super_panamax")
        monkeypatch.setenv("LINER_TRUNK_LANE_CLASSES", "Panamax_2400, Post_panamax")
        assert tl.classes_from_environment() == ("Panamax_2400", "Post_panamax")


# ---------------------------------------------------------------- lane groups agree with the canonical ports file
def test_lane_groups_match_ports_csv_regions():
    p = pd.read_csv(ROOT / "data" / "raw" / "WorldSmall" / "ports.csv", sep="\t").set_index("UNLocode")
    for lane, spec in tl.LANE_GROUPS.items():
        for side in ("a", "b"):
            for port in spec[side]["ports"]:
                assert port in p.index, (lane, port)
                assert p.loc[port, "D_Region"] in spec[side]["d_regions"] or port in ("PABLB", "PAMIT"), (lane, port)
        assert not set(spec["a"]["ports"]) & set(spec["b"]["ports"])
    # every port of a listed D_Region is in the group (no silently dropped port) except documented exclusions:
    # the two Panama split ports (placed by position) and the two East-Mediterranean ports labelled "West Med"
    # (Ambarli, Port Said), which are not Atlantic-lane ports
    for lane, spec in tl.LANE_GROUPS.items():
        for side in ("a", "b"):
            expected = set(p.index[p.D_Region.isin(spec[side]["d_regions"])]) - {"PABLB", "PAMIT", "TRAMB", "EGPSD"}
            assert expected <= set(spec[side]["ports"]), (lane, side, expected - set(spec[side]["ports"]))


# ---------------------------------------------------------------- generator on a synthetic problem
PORTS = ["E1", "E2", "E3", "A1", "A2", "A3", "X"]       # E = Europe group, A = Americas group, X = outside any lane


def _cls(name, qty, cap, tc, bunker, draft):
    return FleetClass(vessel_class=name, quantity=qty, capacity_teu=cap, tc_rate_daily=tc, draft=draft,
                      min_speed=10.0, design_speed=14.0, max_speed=16.0,
                      bunker_consumption_tons_per_day=bunker, idle_consumption_tons_per_day=2.0)


def _problem(draft_a3=12.0):
    dm = {a: {b: (0.0 if a == b else 3000.0 + 100.0 * abs(PORTS.index(a) - PORTS.index(b))) for b in PORTS} for a in PORTS}
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=2000.0, transshipment_cost=0.0,
                  variable_port_call_cost=0.0, draft=(draft_a3 if p == "A3" else 12.0)) for p in PORTS]
    pairs = [("E1", "A1"), ("A1", "E1"), ("E2", "A2"), ("A2", "E2"), ("E3", "A3"), ("A3", "E3"), ("E1", "A2"), ("A2", "E1"),
             ("E1", "E2"), ("E2", "E1"), ("A1", "A2"), ("A2", "A1"), ("X", "E1"), ("E1", "X")]
    dem = [Demand(o, d, 1500.0, 1800.0, max_transit_days=90.0) for o, d in pairs]
    fleet = Fleet(classes=[_cls("S", 4, 400.0, 6000.0, 20.0, 9.0), _cls("L", 20, 6000.0, 20000.0, 60.0, 11.0)])
    return Problem(ports=ports, services=[], demands=dem, distance_matrix=dm, fleet=fleet)


GROUPS_PATCH = {"transpacific": {"a": {"ports": ("E1", "E2", "E3")}, "b": {"ports": ("A1", "A2", "A3")}, "id_prefix": "tp"}}


@pytest.fixture()
def patched_groups(monkeypatch):
    monkeypatch.setattr(tl, "LANE_GROUPS", GROUPS_PATCH)


def _run(problem, count=3, classes=("L",), max_ports=5):
    pool = [Candidate("c0", ("E1", "E2"), "S")]
    return tl.augment_lane_candidates(problem, assumptions_for_problem(problem), pool, lanes=["transpacific"],
                                      per_class=count, classes=classes, max_ports=max_ports)


def test_additions_join_both_groups_and_stay_on_lane_ports(patched_groups):
    extra, rep = _run(_problem())
    assert extra, rep
    lane_ports = {"E1", "E2", "E3", "A1", "A2", "A3"}
    for c in extra:
        assert c.vessel_class == "L" and len(c.ports) >= 3
        assert set(c.ports) <= lane_ports and "X" not in c.ports
        assert set(c.ports) & {"E1", "E2", "E3"} and set(c.ports) & {"A1", "A2", "A3"}
        assert c.service_id.startswith("tp")


def test_cap_and_counters_add_up(patched_groups):
    extra, rep = _run(_problem(), count=1)
    pc = rep["by_lane"]["transpacific"]["per_class"]["L"]
    assert len(extra) == 1 == pc["retained"]
    assert pc["grown_rotations"] == (pc["retained"] + pc["rejected_nonpositive_standalone"] + pc["rejected_existing_in_pool"]
                                     + pc["rejected_near_duplicate"] + pc["rejected_by_cap"])
    assert rep["added"] == 1


def test_draft_excludes_ports_for_the_class(patched_groups):
    extra, rep = _run(_problem(draft_a3=8.0))          # class L draws 11 m: A3 cannot be called
    assert all("A3" not in c.ports for c in extra)
    assert rep["by_lane"]["transpacific"]["per_class"]["L"]["eligible_ports"] == 5      # A3 removed
    assert rep["by_lane"]["transpacific"]["per_class"]["L"]["draft_eligible_ports"] == len(PORTS) - 1


def test_unknown_class_adds_nothing(patched_groups):
    extra, rep = _run(_problem(), classes=("NoSuchClass",))
    assert extra == []
    assert rep["added"] == 0


def test_second_lane_does_not_duplicate_first(monkeypatch):
    groups = dict(GROUPS_PATCH)
    groups["atlantic"] = {"a": {"ports": ("E1", "E2", "E3")}, "b": {"ports": ("A1", "A2", "A3")}, "id_prefix": "at"}
    monkeypatch.setattr(tl, "LANE_GROUPS", groups)
    pr = _problem()
    pool = [Candidate("c0", ("E1", "E2"), "S")]
    extra, rep = tl.augment_lane_candidates(pr, assumptions_for_problem(pr), pool, lanes=["transpacific", "atlantic"],
                                            per_class=3, classes=("L",), max_ports=5)
    from src.services.demand_coherent import _canonical
    keys = [(_canonical(c.ports), c.vessel_class) for c in extra]
    assert len(keys) == len(set(keys))
