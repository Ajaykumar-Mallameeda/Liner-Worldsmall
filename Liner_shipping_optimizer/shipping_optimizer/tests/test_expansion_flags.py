"""Phase 4 flags (default OFF): targeted alternative-class candidates (``LINER_CLASS_VARIANTS``) and the
restriction-aware path set (``LINER_PATH_INCLUDE``).

Contract
  class variants   - only for rotations of an OVER-SUBSCRIBED class, only into classes that are not,
                     only with a positive stand-alone profit, at most one per rotation, never a
                     duplicate of an existing (rotation, class); the original candidates are untouched;
                     every addition carries its provenance; off = no change at all.
  path include     - after the LP relaxation chose the services, the per-OD path set is rebuilt from
                     the paths that ride ONLY those services (K fastest per OD); the integer plan is
                     feasible, ledger-verified, and never worse than the plan of the capped set on the
                     instances below (the rebuilt set contains the capped set's usable paths).
All fixtures are SYNTHETIC.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.network.class_variants as cv
import src.network.network_milp as nm
from src.network.paths import build_paths, path_include_from_environment
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

DM = {
    "A": {"B": 1000.0, "C": 1600.0, "D": 2400.0},
    "B": {"A": 1000.0, "C": 600.0, "D": 1400.0},
    "C": {"A": 1600.0, "B": 600.0, "D": 800.0},
    "D": {"A": 2400.0, "B": 1400.0, "C": 800.0},
}


def _cls(name, qty, cap, tc=8000.0, design=12.0, bunker=20.0):
    return FleetClass(vessel_class=name, quantity=qty, capacity_teu=cap, tc_rate_daily=tc,
                      min_speed=design - 2.0, design_speed=design, max_speed=design + 2.0,
                      bunker_consumption_tons_per_day=bunker, idle_consumption_tons_per_day=2.0)


def _problem(demands, classes):
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0, transshipment_cost=0.0,
                  variable_port_call_cost=0.0) for p in "ABCD"]
    return Problem(ports=ports, services=[], demands=demands, distance_matrix=DM, fleet=Fleet(classes=classes))


DEMANDS = [Demand("A", "B", 800.0, 1500.0), Demand("B", "A", 700.0, 1500.0), Demand("B", "C", 600.0, 1200.0),
           Demand("C", "B", 500.0, 1200.0), Demand("C", "D", 400.0, 1300.0), Demand("D", "C", 300.0, 1300.0)]
# class S: 2 vessels (scarce); class M: 20 vessels (plenty)
CLASSES = [_cls("S", 2, 1000.0), _cls("M", 20, 1500.0, tc=9000.0)]


def _pool(cls_of):
    routes = [("A", "B"), ("B", "C"), ("C", "D"), ("A", "B", "C"), ("B", "C", "D")]
    return [Candidate(f"c{i}", r, cls_of) for i, r in enumerate(routes)]


class TestFlagParsing:
    def test_class_variants(self, monkeypatch):
        monkeypatch.delenv("LINER_CLASS_VARIANTS", raising=False)
        assert cv.fraction_from_environment() == 0.0
        monkeypatch.setenv("LINER_CLASS_VARIANTS", "0.1")
        assert cv.fraction_from_environment() == pytest.approx(0.1)
        for bad in ("-0.1", "1.5", "x", "nan"):
            monkeypatch.setenv("LINER_CLASS_VARIANTS", bad)
            with pytest.raises(ValueError):
                cv.fraction_from_environment()

    def test_path_include(self, monkeypatch):
        monkeypatch.delenv("LINER_PATH_INCLUDE", raising=False)
        assert path_include_from_environment() == 0
        monkeypatch.setenv("LINER_PATH_INCLUDE", "20")
        assert path_include_from_environment() == 20
        for bad in ("-1", "x", "5000", "1.5"):
            monkeypatch.setenv("LINER_PATH_INCLUDE", bad)
            with pytest.raises(ValueError):
                path_include_from_environment()


class TestClassVariants:
    def _augment(self, fraction, base_class="S", n_extra_scarce=0):
        pr = _problem(DEMANDS, CLASSES)
        from src.network.economics import assumptions_for_problem
        cands = _pool(base_class)
        return pr, cands, cv.augment_candidates(pr, assumptions_for_problem(pr), cands, fraction=fraction)

    def test_adds_only_into_non_over_subscribed_classes_with_provenance(self):
        pr, cands, (extra, rep) = self._augment(1.0)
        # 5 candidates of S against 2 vessels: ratio 2.5 >= 2 -> over-subscribed; M: 0 candidates / 20 vessels
        assert rep["over_subscribed_classes"]["S"]["ratio"] >= cv.PRESSURE_RATIO
        assert rep["target_classes"] == ["M"]
        assert extra, "no variant was produced although class M has idle vessels and demand to carry"
        for c in extra:
            assert c.vessel_class == "M"
        keys = {(tuple(c.ports), c.vessel_class) for c in cands}
        for c in extra:
            assert (tuple(c.ports), c.vessel_class) not in keys             # no duplicate of an existing pair
        rotations = [tuple(c.ports) for c in extra]
        assert len(rotations) == len(set(rotations))                         # at most one variant per rotation
        for a in rep["additions"]:
            assert a["standalone_profit_usd_per_week"] > 0
            assert a["rotation_of"] in {c.service_id for c in cands}
            assert a["vessels_at_best"] <= 20
            assert a["reason"]
        assert rep["added"] == len(extra) <= len(cands)

    def test_fraction_bounds_the_number_of_additions(self):
        _pr, cands, (extra, rep) = self._augment(0.2)                        # round(0.2 * 5) = 1
        assert len(extra) == 1
        assert rep["scored_variants_available"] >= 1

    def test_originals_are_untouched_and_off_adds_nothing(self):
        pr, cands, _ = self._augment(0.0)
        from src.network.economics import assumptions_for_problem
        before = [(c.service_id, c.ports, c.vessel_class) for c in cands]
        extra, rep = cv.augment_candidates(pr, assumptions_for_problem(pr), cands, fraction=0.0)
        assert extra == [] and rep["added"] == 0
        assert before == [(c.service_id, c.ports, c.vessel_class) for c in cands]

    def test_nothing_is_added_when_no_class_is_over_subscribed(self):
        pr = _problem(DEMANDS, [_cls("S", 40, 1000.0), _cls("M", 20, 1500.0, tc=9000.0)])
        from src.network.economics import assumptions_for_problem
        extra, rep = cv.augment_candidates(pr, assumptions_for_problem(pr), _pool("S"), fraction=1.0)
        assert extra == [] and rep.get("reason") == "no over-subscribed class"

    def test_a_loss_making_variant_is_never_added(self):
        # class M with an absurd hire rate: every M variant has a negative stand-alone profit
        pr = _problem(DEMANDS, [_cls("S", 2, 1000.0), _cls("M", 20, 1500.0, tc=5_000_000.0)])
        from src.network.economics import assumptions_for_problem
        extra, rep = cv.augment_candidates(pr, assumptions_for_problem(pr), _pool("S"), fraction=1.0)
        assert extra == []
        assert rep["variants_positive_standalone"] == 0

    def test_augmented_pool_plans_and_passes_the_ledger(self):
        pr, cands, (extra, rep) = self._augment(1.0)
        plan = NetworkPlanner(pr).plan(cands + extra, demands=pr.demands, time_limit_sec=60.0)
        assert plan.ok and plan.ledger.valid and plan.reconciliation["reconciled"] is True
        # (c3 of the base pool needs 3 vessels of the 2-vessel class and is rejected by the canonical
        # model with or without variants; no VARIANT may be rejected: they are built from the same model)
        assert not [r for r in plan.rejected_candidates if str(r.get("service", "")).startswith("cv")]
        assert any(m.service_id.startswith("cv") for m in plan.models)


class TestPathInclude:
    def _models(self):
        pr = _problem(DEMANDS, [_cls("S", 40, 1000.0)])
        planner = NetworkPlanner(pr)
        cands = [Candidate(f"c{i}", r, "S") for i, r in enumerate(
            [("A", "B"), ("B", "C"), ("C", "D"), ("A", "B", "C"), ("B", "C", "D"), ("A", "B", "C", "D")])]
        models, rejected = planner.build_models(cands)
        assert models and not rejected
        return pr, planner, models

    def test_rebuilt_set_rides_only_the_chosen_services(self, monkeypatch):
        pr, planner, models = self._models()
        used_seen = {}

        def rebuild(used):
            used_seen["used"] = set(used)
            return build_paths(pr.demands, models, planner.port_lookup, planner.assumptions,
                               max_paths_per_od=10, config=planner.path_config, only_services=sorted(used))[0]

        paths, _ = build_paths(pr.demands, models, planner.port_lookup, planner.assumptions,
                               max_paths_per_od=1, config=planner.path_config)       # a deliberately tight cap
        limits = {c.vessel_class: c.quantity for c in pr.fleet.classes}
        sol = nm.solve_network(models, pr.demands, paths, limits, time_limit_sec=30.0, path_rebuild=rebuild)
        assert sol.usable
        assert sol.paths_by_od is not None
        for plist in sol.paths_by_od.values():
            for p in plist:
                assert set(p.services) <= used_seen["used"]
        assert sol.formulation["path_include_paths_integer_problem"] == sum(len(v) for v in sol.paths_by_od.values())

    def test_never_worse_than_the_tight_cap_and_ledger_verified(self, monkeypatch):
        monkeypatch.delenv("LINER_PATH_INCLUDE", raising=False)
        pr, planner, _ = self._models()
        cands = [Candidate(f"c{i}", r, "S") for i, r in enumerate(
            [("A", "B"), ("B", "C"), ("C", "D"), ("A", "B", "C"), ("B", "C", "D"), ("A", "B", "C", "D")])]
        base = NetworkPlanner(pr, max_paths_per_od=1).plan(cands, demands=pr.demands, time_limit_sec=60.0)
        monkeypatch.setenv("LINER_PATH_INCLUDE", "10")
        inc = NetworkPlanner(pr, max_paths_per_od=1).plan(cands, demands=pr.demands, time_limit_sec=60.0)
        assert base.ok and inc.ok and inc.ledger.valid and inc.reconciliation["reconciled"] is True
        assert inc.ledger.operating_profit >= base.ledger.operating_profit - 1e-6
        assert inc.reconciliation["formulation"]["path_include_k"] == 10

    def test_off_by_default(self, monkeypatch):
        monkeypatch.delenv("LINER_PATH_INCLUDE", raising=False)
        pr, planner, _ = self._models()
        cands = [Candidate("c0", ("A", "B"), "S"), Candidate("c1", ("B", "C"), "S")]
        plan = planner.plan(cands, demands=pr.demands, time_limit_sec=30.0)
        assert plan.solution.paths_by_od is None
        assert "path_include_k" not in plan.reconciliation["formulation"]
